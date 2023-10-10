import argparse
import json
import logging
import subprocess
import sys
import uuid
import random
import string
import requests


from billing_profiles import list_managed_apps, create_billing_profile
from mrg import deploy_managed_application
from utils import auth, poll, cli
from utils.conf import Configuration

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

DEFINITIONS = {
    "standard": "CromwellBaseResourcesFactory",
    "protected": "ProtectedDataResourcesFactory",
}


def create_landing_zone(lz_host: str, billing_profile_id: str, definition: str):
    postgres_credentials = _read_postgres_credentials()

    body = {
        "landingZoneId": f"{uuid.uuid4()}",
        "definition": definition,
        "version": "v1",
        "parameters": [
            {"key": "VNET_ADDRESS_SPACE", "value": "10.1.0.0/18"},
            {"key": "AKS_SUBNET", "value": "10.1.0.0/22"},
            {"key": "BATCH_SUBNET", "value": "10.1.4.0/22"},
            {"key": "POSTGRESQL_SUBNET", "value": "10.1.8.0/22"},
            {"key": "COMPUTE_SUBNET", "value": "10.1.12.0/22"},
            {
                "key": "POSTGRES_DB_ADMIN",
                "value": postgres_credentials["username"],
            },
            {
                "key": "POSTGRES_DB_PASSWORD",
                "value": postgres_credentials["password"],
            },
            {"key": "AKS_AUTOSCALING_ENABLED", "value": "true"},
            {"key": "AKS_AUTOSCALING_MIN", "value": "1"},
            {"key": "AKS_AUTOSCALING_MAX", "value": "100"},
            {"key": "AKS_MACHINE_TYPE", "value": "Standard_D4as_v5"},
        ],
        "billingProfileId": billing_profile_id,
        "jobControl": {"id": f"{uuid.uuid4()}"},
    }

    url = f"{lz_host}/api/landingzones/v1/azure"

    logging.info(
        f"Creating landing zone..[landing_zone_id={body['landingZoneId']}, job_control_id={body['jobControl']['id']}]"
    )

    result = requests.post(
        url,
        headers=auth.build_auth_headers(auth.get_gcp_token()),
        data=json.dumps(body),
    )
    result.raise_for_status()

    return result.json()


def create_job_status(lz_host: str, job_id: str):
    token = auth.get_gcp_token()

    url = f"{lz_host}/api/landingzones/v1/azure/create-result/{job_id}"

    result = requests.get(url, headers=auth.build_auth_headers(token))
    result.raise_for_status()

    return result.json()


def id_generator(size=6, chars=string.ascii_lowercase + string.digits):
    return "".join(random.choice(chars) for _ in range(size))


def create_lz_e2e(
    subscription_id: str,
    resource_group: str,
    authed_user: str,
    env: str,
    definition: str,
    lz_prefix: str = "test",
):
    bpm_host = Configuration.get_config()["bpm_host"]
    lz_host = Configuration.get_config()["lz_host"]
    deployment_name = f"{lz_prefix}-{id_generator()}"
    logging.info(
        f"Creating Azure landing zone [subscription_id={subscription_id}, resource_group={resource_group}, authed_user={authed_user}, deployment_name={deployment_name}]"
    )

    deploy_managed_application(
        subscription_id,
        deployment_name,
        resource_group,
        [authed_user],
        Configuration.get_config()["plan"],
    )

    def bpm_poller():
        managed_apps = list_managed_apps(bpm_host, subscription_id)["managedApps"]
        for app in managed_apps:
            if app["applicationDeploymentName"] == deployment_name:
                return True, app
        return False, None

    bpm_status, app = poll.poll_predicate("managed app creation", 120, 5, bpm_poller)
    created_bp = create_billing_profile(
        bpm_host,
        subscription_id,
        app["managedResourceGroupId"],
        app["tenantId"],
    )

    lz_create_result = create_landing_zone(lz_host, created_bp["id"], definition)

    job_id = lz_create_result["jobReport"]["id"]

    def lz_poller():
        result = create_job_status(lz_host, job_id)
        if result["jobReport"]["status"] == "RUNNING":
            return False, None
        if result["jobReport"]["status"] != "SUCCEEDED":
            logging.error(result)
            raise Exception("lz creation failed")
        if result["jobReport"]["status"] == "SUCCEEDED":
            return True, result

    poll.poll_predicate("landing zone creation", 1200, 5, lz_poller)

    logging.info(f"Created landing zone")


def _read_postgres_credentials():
    vault_path = Configuration.get_config()["lz_postgres_credentials_vault_path"]
    read_credentials_process = subprocess.run(
        f"vault read -format=json {vault_path}".split(" "), capture_output=True
    )
    if read_credentials_process.returncode != 0:
        print(
            "Unable to read postgres credentials.\nExit code: {}.\nStderr: {}".format(
                read_credentials_process.returncode, read_credentials_process.stderr
            )
        )
        sys.exit(1)

    return json.loads(read_credentials_process.stdout)["data"]


def _create_job_status_cmd(args):
    create_job_status(Configuration.get_config()["lz_host"], args.job_id)


def _lz_create_cmd(args):
    _verify_lz_definition(args.definition)

    create_landing_zone(
        Configuration.get_config()["lz_host"],
        args.billing_profile_id,
        DEFINITIONS[args.definition],
    )


def _e2e_cmd(args):
    _verify_lz_definition(args.definition)
    create_lz_e2e(
        args.subscription_id,
        args.resource_group,
        args.authed_user,
        args.env,
        DEFINITIONS[args.definition],
        args.lz_prefix,
    )


def _verify_lz_definition(definition: str):
    if definition not in DEFINITIONS:
        logging.info(
            f"Definition must one of {DEFINITIONS.keys()}, {args.definition} not found"
        )
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-e", "--env", choices=Configuration.get_environments(), required=True
    )
    parser.add_argument("-b", "--bee", required=False)
    subparsers = parser.add_subparsers()
    subparsers.required = True

    create_subparser = subparsers.add_parser("create")
    create_subparser.set_defaults(func=_lz_create_cmd)
    create_subparser.add_argument("-b", "--billing_profile_id")
    create_subparser.add_argument("-d", "--definition")

    create_job_status_subparser = subparsers.add_parser("create_job_status")
    create_job_status_subparser.set_defaults(func=_create_job_status_cmd)
    create_job_status_subparser.add_argument("-j", "--job_id")

    e2e_subparser = subparsers.add_parser("e2e")
    e2e_subparser.add_argument("-s", "--subscription_id", required=True)
    e2e_subparser.add_argument("-r", "--resource_group", required=True)
    e2e_subparser.add_argument("-u", "--authed_user", required=True)
    e2e_subparser.add_argument("-d", "--definition", required=True)
    e2e_subparser.add_argument("-p", "--lz_prefix", required=False, default="test")
    e2e_subparser.set_defaults(func=_e2e_cmd)

    args = cli.parse_args_and_init_config(parser)

    args.func(args)
