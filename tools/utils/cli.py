import argparse
from argparse import Namespace
from typing import Tuple

from utils import auth
from utils.conf import TerraEnvs, Configuration


def setup_parser_terra_env_args(parser: argparse.ArgumentParser):
    """
    Add a case-insensitive, bee-aware terra environment arg
    """

    parser.add_argument(
        "-e",
        "--env",
        choices=Configuration.get_environments(),
        required=True,
        type=str.lower,
    )
    parser.add_argument("-b", "--bee", required=False)


def parse_args_and_init_config(
    parser: argparse.ArgumentParser,
) -> Namespace:
    """
    Parses args and initializes config from the supplied argument parser. Assumes
    an "env" arg on the command line. If the env is "bee", enforces the presence of "bee" arg as well for runtime
    specification of the bee name.
    :param parser:
    :return:
    """
    subs = {}

    args = parser.parse_args()

    if "user_token" in args and args.user_token is not None:
        auth.USER_TOKEN = args.user_token

    if args.env == TerraEnvs.BEE and args.bee is None:
        parser.error("BEE name is required when env is BEE")
    elif args.env == TerraEnvs.BEE and args.bee:
        subs = {"bee": args.bee}

    Configuration.initialize(args.env, overrides=subs)
    return args
