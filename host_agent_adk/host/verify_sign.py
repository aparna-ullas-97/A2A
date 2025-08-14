import json
import os
from pathlib import Path
import requests
from typing import Optional

from utils.node_client import NodeClient


class APIError(Exception):
    """Raised when an external API call fails or returns invalid data."""
    pass


node = NodeClient(framework="host")
default_base_url = node.get_base_url()  


def verify_signature(
    signer_did: str,
    signed_msg: str,
    signature: str,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> bool:
    """
    Calls GET /api/verify-signature to verify a signature for a given DID and signed message.
    Returns True if verification passed, False otherwise.
    """
    url = (default_base_url).rstrip("/") + "/api/verify-signature"
    params = {
        "signer_did": signer_did,
        "signed_msg": signed_msg,
        "signature": signature,
    }

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise APIError(f"HTTP error during verify_signature: {e}") from e
    except ValueError as e:
        raise APIError(f"Invalid JSON in verify_signature response: {e}") from e

    
    return bool(data.get("status", False))

