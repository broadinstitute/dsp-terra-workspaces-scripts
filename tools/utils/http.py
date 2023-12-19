import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry


def basic_http_retry() -> Retry:
    return Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])


def get_session_with_retry() -> requests.Session:
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=basic_http_retry()))
    return session
