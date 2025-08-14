import json
import os
from pathlib import Path
import requests

from utils.node_client import NodeClient

defining_error = False
class APIError(Exception):
    """Raised when the external API call fails or returns invalid data."""
    pass

node = NodeClient(framework="langgraph")
default_base_url = node.get_base_url()  
default_did = node.get_did()


def get_account_info(did: str | None = None) -> dict:
    """
    Fetches account information (including balance) for a given DID.

    Args:
        did: Decentralized Identifier to query. If None, uses the default DID from environment.

    Returns:
        A dictionary representing the JSON payload from the API.

    Raises:
        APIError: If the HTTP request fails or the response cannot be parsed.
    """
    target_did = did or default_did

    base_url = default_base_url.rstrip("/")
    endpoint = "/api/get-account-info"
    url = f"{base_url}{endpoint}"
    params = {"did": target_did}
    headers = {"Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise APIError(f"HTTP error during get_account_info: {e}") from e

    try:
        data = response.json()
    except ValueError as e:
        raise APIError(f"Invalid JSON in response: {e}") from e

    return data


