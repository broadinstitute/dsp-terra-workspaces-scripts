"""
Utility for working with Terra Azure Landing Zones.
"""
import argparse
import json
import logging
import random
import string
import sys
import uuid
import io
import csv

import requests
from azure.mgmt.resource import ResourceManagementClient
from tabulate import tabulate

from billing_profiles import list_managed_apps, create_billing_profile
from mrg import deploy_managed_application
from utils import auth, poll, cli
from utils.conf import Configuration

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(message)s", stream=sys.stdout
)

DEFINITIONS = {
    "standard": "CromwellBaseResourcesFactory",
    "protected": "ProtectedDataResourcesFactory",
}


def create_landing_zone(lz_host: str, billing_profile_id: str, definition: str):
    """
    Creates a landing zone, calling the LZ APIs against the supplied host and
    deploying the resources into the Azure managed application from the supplied billing profile.
    :param lz_host: Hostname of the LZ API
    :param billing_profile_id: ID of the billing profile which will hold the landing zone resources
    :param definition:  Type of landing zone to deploy, must be one of DEFINITIONS
    """

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


def inspect_lz(subscription_id: str, managed_resource_group_id: str):
    """
    Inspects the contents of a landing zone at the supplied Azure coordinates. Uses the default azure credential
    from the environment. For local dev usage, this is usually setup by invoking `az login` and logging in as
    an identity that is authorized to access the given MRG.
    :param subscription_id: Subscription in which the landing zone resides
    :param managed_resource_group_id: Managed resource group containing the Terra deployment
    :return: List of azure resources in the MRG
    """
    logging.info(
        f"Inspecting lz at coordinates [subscription_id={subscription_id}, managed_resource_group_id={managed_resource_group_id}]"
    )
    cred = auth.get_azure_credential()
    resource_client = ResourceManagementClient(cred, subscription_id)

    resource_list = resource_client.resources.list_by_resource_group(
        managed_resource_group_id, expand="createdTime,changedTime"
    )
    return resource_list


def _render_resource_list(resource_list: list, output_format="csv"):
    objs = [
        {"Name": r.name, "Type": r.type, "Created Time": r.created_time}
        for r in resource_list
    ]
    if "pretty" == output_format:
        logging.info(tabulate(objs, headers="keys"))
    else:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=objs[0].keys())
        writer.writeheader()
        writer.writerows(objs)
        logging.info(output.getvalue())


def _inspect_cmd(args):
    resources = inspect_lz(args.subscription_id, args.managed_resource_group_id)
    _render_resource_list(resources, args.output_format)


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
    parser.add_argument("-u", "--user_token", required=False)

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

    inspect_subparser = subparsers.add_parser("inspect")
    inspect_subparser.add_argument("-s", "--subscription_id", required=True)
    inspect_subparser.add_argument("-m", "--managed_resource_group_id", required=True)
    inspect_subparser.add_argument(
        "-o", "--output_format", default="pretty", required=False
    )
    inspect_subparser.set_defaults(func=_inspect_cmd)

    cli.setup_parser_terra_env_args(parser)
    args = cli.parse_args_and_init_config(parser)

    args.func(args)
