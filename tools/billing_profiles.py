"""
Utility for working with Terra Billing Profiles
"""

import argparse
import json
import logging

import requests
import sys

from utils import auth, cli
from utils.conf import Configuration
import uuid

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(message)s", stream=sys.stdout
)


def list_managed_apps(host: str, subscription_id: str):
    token = auth.get_gcp_token()
    logging.info(f"Getting managed apps from BPM {host}")
    url = f"{host}/api/azure/v1/managedApps?azureSubscriptionId={subscription_id}"

    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    result = requests.get(url, headers=headers)
    return result.json()


def create_billing_profile(
    host: str, subscription_id: str, managed_resource_group_id: str, tenant_id: str
):
    token = auth.get_gcp_token()
    logging.info("Creating billing profile...")

    url = f"{host}/api/profiles/v1"

    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    body = {
        "id": f"{uuid.uuid4()}",
        "biller": "direct",
        "displayName": "string",
        "description": "string",
        "cloudPlatform": "AZURE",
        "tenantId": tenant_id,
        "subscriptionId": subscription_id,
        "managedResourceGroupId": managed_resource_group_id,
    }

    result = requests.post(url, headers=headers, data=json.dumps(body))
    result.raise_for_status()

    return result.json()


def _bpm_managed_apps_cmd(args):
    result = list_managed_apps(
        Configuration.get_config()["bpm_host"], args.subscription_id
    )
    logging.info(json.dumps(result, indent=4))


def _bpm_create_cmd(args):
    result = create_billing_profile(
        Configuration.get_config()["bpm_host"],
        args.subscription_id,
        args.mrg_id,
        args.tenant_id,
    )

    logging.info(json.dumps(result, indent=4))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-u", "--user_token", required=False)

    subparsers = parser.add_subparsers()
    subparsers.required = True

    mrg_subparser = subparsers.add_parser("mrg")
    mrg_subparser.add_argument("-s", "--subscription_id", required=True)
    mrg_subparser.set_defaults(func=_bpm_managed_apps_cmd)

    create_subparser = subparsers.add_parser("create")
    create_subparser.set_defaults(func=_bpm_create_cmd)
    create_subparser.add_argument("-s", "--subscription_id", required=True)
    create_subparser.add_argument("-m", "--mrg_id", required=True)
    create_subparser.add_argument("-t", "--tenant_id", required=True)

    cli.setup_parser_terra_env_args(parser)
    args = cli.parse_args_and_init_config(parser)

    args.func(args)
