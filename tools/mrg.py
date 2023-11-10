"""
Utility for creating a Terra development MRG deployment
"""

import argparse
import json
import logging
import sys

import requests

from utils import auth, poll, cli
from utils.conf import Configuration

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(message)s", stream=sys.stdout
)

MRG_NOT_READY_STATES = ["Accepted", "Creating"]
MRG_FAILED_STATES = ["Failed", "Deleted", "Deleting"]
MRG_READY_STATES = ["Succeeded", "Running", "Ready"]


def deploy_managed_application(
    subscription_id: str,
    deployment_name: str,
    resource_group: str,
    authorized_terra_users: list[str],
    plan: str,
    location: str = "southcentralus",
):
    access_token = auth.get_azure_access_token()
    body = {
        "location": location,
        "plan": plan,
        "kind": "MarketPlace",
        "properties": {
            "managedResourceGroupId": f"/subscriptions/{subscription_id}/resourceGroups/{deployment_name}",
            "parameters": {
                "authorizedTerraUser": {"value": ",".join(authorized_terra_users)},
                "location": {"value": location},
            },
        },
    }

    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Solutions/applications/{deployment_name}?api-version=2018-06-01"
    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {access_token.token}",
    }

    logging.info(
        f"Creating MRG [subscription={subscription_id}, resource_group={resource_group}, users={authorized_terra_users}]"
    )
    result = requests.put(url, headers=headers, data=json.dumps(body))
    result.raise_for_status()

    def app_state_poller():
        check_url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Solutions/applications/{deployment_name}?api-version=2018-06-01"
        app_result = requests.get(check_url, headers=headers)
        app_result.raise_for_status()
        data = app_result.json()

        provisioning_state = data["properties"]["provisioningState"]
        if provisioning_state in MRG_NOT_READY_STATES:
            return False, data
        elif provisioning_state in MRG_FAILED_STATES:
            raise Exception(f"MRG creation failed => {data}")
        elif provisioning_state in MRG_READY_STATES:
            return True, data
        else:
            raise Exception(f"Unknown MRG state => {provisioning_state}")

    poll.poll_predicate("MRG creation", 300, 5, app_state_poller)

    return result.json()


def delete_managed_application(
    subscription_id: str, deployment_name: str, resource_group: str
):
    access_token = auth.get_azure_access_token()
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Solutions/applications/{deployment_name}?api-version=2019-07-01"
    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {access_token.token}",
    }
    logging.info(
        f"Deleting MRG [subscription={subscription_id}, resource_group={resource_group}, deployment_name={deployment_name}]"
    )

    result = requests.delete(url, headers=headers)
    result.raise_for_status()

    logging.info("Deletion complete")


def _delete_mrg_cmd(args):
    delete_managed_application(
        args.subscription_id, args.deployment_name, args.resource_group
    )


def _mrg_cmd(args):
    result = deploy_managed_application(
        args.subscription_id,
        args.deployment_name,
        args.resource_group,
        args.users,
        Configuration.get_config()["plan"],
        args.location,
    )

    logging.info(json.dumps(result, indent=4))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers()

    create_subparser = subparsers.add_parser("create")
    create_subparser.add_argument("-d", "--deployment_name", required=True)
    create_subparser.add_argument("-s", "--subscription_id", required=True)
    create_subparser.add_argument("-r", "--resource_group", required=True)
    create_subparser.add_argument("-u", "--users", nargs="+", required=True)
    create_subparser.add_argument(
        "-l", "--location", required=False, default="southcentralus"
    )
    create_subparser.set_defaults(func=_mrg_cmd)

    delete_subparser = subparsers.add_parser("delete")
    delete_subparser.add_argument("-d", "--deployment_name", required=True)
    delete_subparser.add_argument("-s", "--subscription_id", required=True)
    delete_subparser.add_argument("-r", "--resource_group", required=True)
    delete_subparser.set_defaults(func=_delete_mrg_cmd)

    cli.setup_parser_terra_env_args(parser)
    args = cli.parse_args_and_init_config(parser)

    args.func(args)
