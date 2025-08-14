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

    # API returns {"status": bool, "message": str, "result": null}
    # If status is True, signature is valid
    return bool(data.get("status", False))


# # ────────────── Example usage ──────────────
# if __name__ == "__main__":
#     # Example parameters
#     signer = "bafybmicjf5eulsyudab2a7fcfo5nh2ajhtupid5xx4fzr72m3tcysztyoi"
#     message = "hello"
#     sig = "304402203ed035ead8950366231f0aac14c7aba8fdcd529eeba8734eb00dd98ed7bbf5530220448587e47c36a33de8ed9546fe4927acf26bdd4014a33006ad00c4d5f34efa8c"

#     try:
#         valid = verify_signature(signer, message, sig)
#         print(f"Signature valid? {valid}")
#     except APIError as err:
#         print(f"Error verifying signature: {err}")