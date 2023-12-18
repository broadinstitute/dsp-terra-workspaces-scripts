"""
Utility functions for working with Terra workspaces.
"""

import argparse
import requests
import logging

from utils import auth, poll, cli
from utils.conf import Configuration


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(message)s", stream=sys.stdout
)


def delete_workspace(workspace_name: str, billing_project_name: str):
    """
    Deletes a workspace from the billing project.
    :param workspace_name:
    :param billing_project_name:
    :return:
    """
    rawls_host = Configuration.get_config()["rawls_host"]
    token = auth.get_gcp_token()
    headers = auth.build_auth_headers(token)
    request = f"{rawls_host}/api/workspaces/v2/{billing_project_name}/{workspace_name}"

    logging.info(f"Start deletion of workspace {billing_project_name}/{workspace_name}")
    response = requests.delete(url=request, headers=headers)
    response.raise_for_status()

    def deletion_poller():
        polling_url = (
            f"{rawls_host}/api/workspaces/{billing_project_name}/{workspace_name}"
        )

        raw_status = requests.get(url=polling_url, headers=headers)
        raw_status.raise_for_status()

        status = raw_status.json()["workspace"]["state"]
        if status in ["Deleting"]:
            return False, status
        elif status in ["Deleted"]:
            return True, None
        else:
            raise Exception(
                f"Error deleting workspace {billing_project_name}/{workspace_name}, id = {raw_status['workspace']['workspaceId']} status = {status}"
            )

    poll.poll_predicate("Workspace deletion", 1200, 5, deletion_poller)


def _delete_workspace_cmd(args):
    delete_workspace(args.workspace_name, args.billing_project_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-u", "--user_token", required=False)

    subparsers = parser.add_subparsers()
    subparsers.required = True

    delete_subparser = subparsers.add_parser("delete")
    delete_subparser.add_argument("-w", "--workspace_name", required=True)
    delete_subparser.add_argument("-bp", "--billing_project_name", required=True)
    delete_subparser.set_defaults(func=_delete_workspace_cmd)

    cli.setup_parser_terra_env_args(parser)
    args = cli.parse_args_and_init_config(parser)

    args.func(args)
