"""
Simple tool for working with Rawls Azure billing projects
"""

import argparse
import json
import logging
import sys
import requests
from requests import HTTPError

import mrg
from utils import auth, poll, cli
from utils.conf import Configuration

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s", stream=sys.stdout)


def create_billing_project(
    billing_project_name: str,
    subscription_id: str,
    resource_group: str,
    authorized_terra_users: list[str],
    tenant_id: str,
    protected_data: bool,
):
    mrg.deploy_managed_application(
        subscription_id,
        billing_project_name,
        resource_group,
        authorized_terra_users,
        Configuration.get_config()["plan"],
    )

    body = {
        "projectName": billing_project_name,
        "managedAppCoordinates": {
            "tenantId": tenant_id,
            "subscriptionId": subscription_id,
            "managedResourceGroupId": billing_project_name,
        },
        "protectedData": protected_data,
    }

    billing_url = _get_rawls_billing_url()
    result = requests.post(
        billing_url,
        headers=auth.build_auth_headers(auth.get_gcp_token()),
        data=json.dumps(body),
    )
    result.raise_for_status()

    def bp_poller():
        polling_url = f"{billing_url}/{billing_project_name}"

        bp_result = requests.get(
            polling_url, headers=auth.build_auth_headers(auth.get_gcp_token())
        )
        bp_result.raise_for_status()
        data = bp_result.json()

        status = data["status"]
        if status == "CreatingLandingZone":
            return False, data
        elif status == "Creating":
            return False, data
        elif status == "Ready":
            return True, data
        else:
            raise Exception(f"Error creating billing project => {status}")

    poll.poll_predicate("Billing project creation", 1800, 5, bp_poller)


def list_billing_projects():
    billing_url = _get_rawls_billing_url()
    result = requests.get(
        billing_url, headers=auth.build_auth_headers(auth.get_gcp_token())
    )
    result.raise_for_status()

    project_names = [p["projectName"] for p in result.json()]
    [logging.info(project_name) for project_name in sorted(project_names)]


def _get_rawls_billing_url():
    rawls_host = Configuration.get_config()["rawls_host"]
    url = f"{rawls_host}/api/billing/v2"
    return url


def _create_billing_project_cmd(args):
    create_billing_project(
        args.billing_project_name,
        args.subscription_id,
        args.resource_group,
        args.users,
        args.tenant_id,
        args.protected_data,
    )


def delete_billing_project(billing_project_name: str):
    billing_url = _get_rawls_billing_url()

    result = requests.delete(
        f"{billing_url}/{billing_project_name}",
        headers=auth.build_auth_headers(auth.get_gcp_token()),
    )
    result.raise_for_status()

    def _billing_deletion_poller():
        raw_status = requests.get(
            f"{billing_url}/{billing_project_name}",
            headers=auth.build_auth_headers(auth.get_gcp_token()),
        )
        try:
            raw_status.raise_for_status()
        except HTTPError as e:
            if e.response.status_code == 404:
                return True, None
            raise e

        status = raw_status.json()["status"]
        if status in ["DeletionFailed"]:
            raise Exception(
                f"Billing project deletion failed, billing project status = {status}"
            )

        return False, status

    poll.poll_predicate("Billing project deletion", 1200, 5, _billing_deletion_poller)

    logging.info("Deleted billing project")


def _delete_billing_project_cmd(args):
    delete_billing_project(args.billing_project_name)


def _list_billing_projects_cmd(args):
    list_billing_projects()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-e", "--env", choices=Configuration.get_environments(), required=True
    )
    parser.add_argument("-b", "--bee", required=False)
    parser.add_argument("-u", "--user_token", required=False)

    subparsers = parser.add_subparsers()
    subparsers.required = True

    create_subparser = subparsers.add_parser("create")
    create_subparser.add_argument("-s", "--subscription_id", required=True)
    create_subparser.add_argument("-t", "--tenant_id", required=True)
    create_subparser.add_argument("-r", "--resource_group", required=True)
    create_subparser.add_argument("-u", "--users", nargs="+", required=True)
    create_subparser.add_argument("-bp", "--billing_project_name", required=True)
    create_subparser.add_argument(
        "-p", "--protected_data", required=False, default=False, action="store_true"
    )
    create_subparser.set_defaults(func=_create_billing_project_cmd)

    delete_subparser = subparsers.add_parser("delete")
    delete_subparser.add_argument("-bp", "--billing_project_name", required=True)
    delete_subparser.set_defaults(func=_delete_billing_project_cmd)

    list_subparser = subparsers.add_parser("list")
    list_subparser.set_defaults(func=_list_billing_projects_cmd)

    args = cli.parse_args_and_init_config(parser)

    args.func(args)
