import json
import os
from pathlib import Path
import sys
import requests
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.node_client import NodeClient

class APIError(Exception):
    """Raised when the external API call fails or returns invalid data."""
    pass

node = NodeClient(framework="crew")
default_base_url = node.get_base_url() 
default_did = node.get_did()
default_password = "mypassword"

print("✅ Sign Using DID for details:", default_did)
print("✅ Sign Using base URL:", default_base_url)


def sign_message(msg_hash: str, did: str | None = None, password: str | None = None) -> str:
    """
    Send a SHA-256 hex digest to the `/api/sign` endpoint to get back either:
      - A direct signature, or
      - An ID+mode that requires a password exchange.

    If the latter, it will automatically POST that to `/api/signature-response`
    (with the given password) and return the real signature.

    Args:
        msg_hash: hex-encoded SHA-256 digest of the message to sign
        did: the DID to sign with (falls back to default_did)
        password: the password to use for the second call (falls back to default_password)

    Returns:
        The hex signature string.

    Raises:
        APIError: on network/HTTP errors, bad JSON, or any API-level failure.
    """
    target_did = default_did
    pw = default_password
    base = default_base_url.rstrip('/')

    try:
        resp = requests.post(
            f"{default_base_url}/api/sign",
            json={"signer_did": target_did, "msg_to_sign": msg_hash},
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise APIError(f"HTTP error during initial sign: {e}") from e

    try:
        data = resp.json()
    except ValueError as e:
        raise APIError(f"Invalid JSON in initial sign response: {e}") from e

    if data.get("status") and isinstance(data.get("result"), str):
        return data["result"]

    if not data.get("status") or not isinstance(data.get("result"), dict):
        raise APIError(f"Unexpected sign response: {data}")

    result = data["result"]
    sign_id = result.get("id")

    if sign_id is None:
        raise APIError(f"Sign API returned no id/mode for password flow: {result}")

    try:
        resp2 = requests.post(
            f"{base}/api/signature-response",
            json={"id": sign_id, "mode": 0, "password": pw},
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        resp2.raise_for_status()
    except requests.RequestException as e:
        raise APIError(f"HTTP error during signature-response: {e}") from e

    try:
        data2 = resp2.json()
    except ValueError as e:
        raise APIError(f"Invalid JSON in signature-response: {e}") from e

    if not data2.get("status"):
        raise APIError(f"Signature-response API returned error: {data2.get('message', '<no message>')}")

    sig = data2.get("result", {}).get("signature")
    if not sig:
        raise APIError("Signature-response API succeeded but no `signature` in result")
    print("SIGNNNNN", sig)

    return sig