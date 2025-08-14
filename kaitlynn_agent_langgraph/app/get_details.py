import json
import os
from pathlib import Path
import requests

# Custom exception for API-related errors
defining_error = False
class APIError(Exception):
    """Raised when the external API call fails or returns invalid data."""
    pass

# Base URL for the account-info service
# default_base_url = os.getenv("API_BASE_URL", "http://localhost:20000")
# default_did = "bafybmigkmdklseni5ynibyyy5yp67rfn7tx2k2j7gdkulefy5cbhh7jnii"

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]                  # .../A2A
cfg_path = Path(os.getenv("CONFIG_PATH", ROOT / "config.json"))

if not cfg_path.exists():
    raise FileNotFoundError(f"config.json not found at: {cfg_path}")

with cfg_path.open("r", encoding="utf-8") as f:
    cfg = json.load(f)

port = int(cfg.get("langgraph_port"))
default_base_url = os.getenv("BASE_URL", f"http://localhost:{port}")
print("Details Base URL =>", default_base_url)

def get_default_did():
    try:
        url = f"{default_base_url}/api/get-by-node"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        # Get first DID if available
        if data.get("TxnCount") and len(data["TxnCount"]) > 0:
            return data["TxnCount"][0]["DID"]

        print("⚠️ No DID found in API response, using fallback.")
        return "fallback_did_here"

    except Exception as e:
        print(f"⚠️ Failed to fetch DID from API: {e}")
        return "fallback_did_here"

# Use the API result
default_did = get_default_did()
print("✅ Using DID for details:", default_did)


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
    # Use provided DID or fallback to default
    target_did = did or default_did

    # Construct URL and parameters
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


if __name__ == "__main__":
    # Quick CLI test
    try:
        account = get_account_info()
        print(f"Account payload: {account}")
        balance = account.get("balance")
        print(f"Balance for DID {account.get('did', default_did)}: {balance}")
    except APIError as err:
        print(f"Error fetching account info: {err}")
