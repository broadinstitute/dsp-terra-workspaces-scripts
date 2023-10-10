from enum import StrEnum


class TerraEnvs(StrEnum):
    BEE = "bee"
    DEV = "dev"
    ALPHA = "alpha"
    STAGING = "staging"
    PROD = "prod"


_environments = {
    TerraEnvs.BEE: {
        "rawls_host": f"https://rawls.{{bee}}.bee.envs-terra.bio",
        "bpm_host": f"https://bpm.{{bee}}.bee.envs-terra.bio",
        "lz_host": f"https://workspace.{{bee}}.bee.envs-terra.bio",
        "plan": {
            "name": "terra-dev",
            "publisher": "thebroadinstituteinc1615909626976",
            "product": "terra-dev-preview",
            "version": "0.0.8",
        },
        "lz_postgres_credentials_vault_path": "secret/dsde/terra/azure/dev/workspacemanager/azure-postgres-credential",
    },
    TerraEnvs.ALPHA: {
        "rawls_host": "https://rawls.dsde-alpha.broadinstitute.org",
        "bpm_host": "https://bpm.dsde-alpha.broadinstitute.org",
        "lz_host": "https://workspace.dsde-alpha.broadinstitute.org",
        "plan": {
            "name": "terra-dev",
            "publisher": "thebroadinstituteinc1615909626976",
            "product": "terra-dev-preview",
            "version": "0.0.8",
        },
        "lz_postgres_credentials_vault_path": "secret/dsde/terra/azure/dev/workspacemanager/azure-postgres-credential",
    },
    TerraEnvs.STAGING: {
        "rawls_host": "https://rawls.dsde-staging.broadinstitute.org",
        "bpm_host": "https://bpm.dsde-staging.broadinstitute.org",
        "lz_host": "https://workspace.dsde-staging.broadinstitute.org",
        "plan": {
            "name": "terra-dev",
            "publisher": "thebroadinstituteinc1615909626976",
            "product": "terra-dev-preview",
            "version": "0.0.8",
        },
        "lz_postgres_credentials_vault_path": "secret/dsde/terra/azure/dev/workspacemanager/azure-postgres-credential",
    },
    TerraEnvs.DEV: {
        "rawls_host": "https://rawls.dsde-dev.broadinstitute.org",
        "bpm_host": "https://bpm.dsde-dev.broadinstitute.org",
        "lz_host": "https://workspace.dsde-dev.broadinstitute.org",
        "plan": {
            "name": "terra-dev",
            "publisher": "thebroadinstituteinc1615909626976",
            "product": "terra-dev-preview",
            "version": "0.0.8",
        },
        "lz_postgres_credentials_vault_path": "secret/dsde/terra/azure/dev/workspacemanager/azure-postgres-credential",
    },
    TerraEnvs.PROD: {
        "rawls_host": "https://rawls.dsde-prod.broadinstitute.org",
        "bpm_host": "https://bpm.dsde-prod.broadinstitute.org",
        "lz_host": "https://workspace.dsde-prod.broadinstitute.org",
        "plan": {
            "name": "terra-prod",
            "publisher": "thebroadinstituteinc1615909626976",
            "product": "terra-prod",
            "version": "1.0.2",
        },
        "lz_postgres_credentials_vault_path": "secret/suitable/terra/azure/prod/workspacemanager/azure-postgres-credential",
    },
}


class Configuration:
    """
    Basic configuration class that allows runtime string interpolation of values from a supplied dictionary.
    """

    __config = None

    @staticmethod
    def initialize(env: TerraEnvs, overrides=None):
        if overrides is None:
            overrides = {}

        Configuration.__config = Configuration._render_conf(env, overrides)

    @staticmethod
    def get_environments():
        return [env.value for env in TerraEnvs]

    @staticmethod
    def get_config():
        if not Configuration.__config:
            raise Exception("Configuration not initialized")

        return Configuration.__config

    @staticmethod
    def _render_conf(env: TerraEnvs, overrides):
        c = _environments[env]
        for k, v in c.items():
            if isinstance(v, str):
                c[k] = v.format(**overrides)

        return c
