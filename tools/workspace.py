"""
Utility functions for working with Terra workspaces.
"""

import argparse
import requests
import logging
import sys

from utils import auth, poll, cli
from utils.conf import Configuration
from utils.http import get_session_with_retry

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(message)s", stream=sys.stdout
)


def get_workspace(
    workspace_name: str, billing_project_name: str, session: requests.Session
):
    """
    Gets the workspace from rawls
    :param workspace_name:
    :param billing_project_name:
    :return:
    """
    rawls_host = Configuration.get_config()["rawls_host"]
    url = f"{rawls_host}/api/workspaces/{billing_project_name}/{workspace_name}"
    token = auth.get_gcp_token()

    headers = auth.build_auth_headers(token)
    raw_status = session.get(url=url, headers=headers)
    return raw_status


def delete_workspace(workspace_name: str, billing_project_name: str):
    """
    Deletes a workspace from the billing project.
    :param workspace_name:
    :param billing_project_name:
    :return:
    """
    token = auth.get_gcp_token()
    headers = auth.build_auth_headers(token)

    session = get_session_with_retry()
    workspace_response = get_workspace(workspace_name, billing_project_name, session)
    if workspace_response.status_code == 404:
        logging.info(
            f"Workspace {billing_project_name}/{workspace_name} is gone, skipping deletion."
        )
        return

    workspace = workspace_response.json()
    workspace_status = workspace["workspace"]["state"]
    if workspace_status in ["Ready", "DeleteFailed"]:
        logging.info(
            f"Workspace {billing_project_name}/{workspace_name} status is {workspace_status}, starting deletion"
        )
        rawls_host = Configuration.get_config()["rawls_host"]
        request = (
            f"{rawls_host}/api/workspaces/v2/{billing_project_name}/{workspace_name}"
        )
        response = session.delete(url=request, headers=headers)
        response.raise_for_status()
    elif workspace_status in ["Deleting"]:
        logging.info(
            f"Workspace {billing_project_name}/{workspace_name} is already being deleted, beginning poll..."
        )

    def deletion_poller():
        raw_status = get_workspace(workspace_name, billing_project_name, session)
        if raw_status.status_code == 404:
            return True, None

        if "workspace" not in raw_status.json():
            logging.info(raw_status.json())
        status = raw_status.json()["workspace"]["state"]
        if status in ["Deleting"]:
            return False, status
        elif status in ["Deleted"]:
            return True, None
        else:
            raise Exception(
                f"Error deleting workspace {billing_project_name}/{workspace_name}, id = {raw_status.json()['workspace']['workspaceId']} status = {status}"
            )

    poll.poll_predicate("Workspace deletion", 1200, 5, deletion_poller)
    logging.info(
        f"Deletion of workspace {billing_project_name}/{workspace_name} complete"
    )


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
