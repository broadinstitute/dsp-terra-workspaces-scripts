import logging

from azure.core.credentials import AccessToken
from azure.identity import DefaultAzureCredential

import google.auth
from google.auth.transport.requests import Request

logger = logging.getLogger("azure")

# Set the desired logging level
logger.setLevel(logging.WARN)


def get_azure_access_token() -> AccessToken:
    token_credential = DefaultAzureCredential()
    return token_credential.get_token("https://management.core.windows.net/.default")


def get_gcp_token():
    DEFAULT_SCOPES = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/cloud-platform",
    ]
    credentials, project_id = google.auth.default(scopes=DEFAULT_SCOPES)
    credentials.refresh(Request())
    token = credentials.token
    return token


def build_auth_headers(token: str):
    return {
        "content-type": "application/json",
        "Authorization": f"Bearer {token}",
    }
