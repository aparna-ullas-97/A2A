import os
import requests
import json
from typing import Optional, Dict

class APIError(Exception):
    """Raised when an external API call fails or returns invalid data."""
    pass

# Base URL for the service (can override via env var)
default_base_url = "http://localhost:20007"
# Default DID for executor if not provided
default_did = "bafybmicjf5eulsyudab2a7fcfo5nh2ajhtupid5xx4fzr72m3tcysztyoi"

def execute_nft(
    comment: str,
    executor: Optional[str],
    nft: str,
    nft_data: str,
    nft_value: int,
    quorum_type: int,
    receiver: str = "",
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict:
    """
    Calls POST /api/execute-nft to transfer ownership or trigger a self-execution block.
    Returns the parsed `result` object containing id, mode, etc.
    """
    url = (base_url or default_base_url).rstrip("/") + "/api/execute-nft"
    payload = {
        "comment": comment,
        "executor": default_did,
        "nft": nft,
        "nft_data": nft_data,
        "nft_value": nft_value,
        "quorum_type": quorum_type,
        "receiver": receiver,
    }
    print("payload", payload)
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        print("resp", resp)
        resp.raise_for_status()
        data = resp.json()
        print("data", data)
    except requests.RequestException as e:
        raise APIError(f"HTTP error during execute_nft: {e}") from e
    except ValueError as e:
        raise APIError(f"Invalid JSON in execute_nft response: {e}") from e

    if not data.get("status", False):
        raise APIError(f"Execute-NFT API returned error: {data.get('message', '<no message>')}")
    result = data.get("result")
    if not isinstance(result, dict) or "id" not in result or "mode" not in result:
        raise APIError(f"Unexpected result field in execute_nft: {result!r}")
    return result


def signature_response(
    deploy_id: str,
    mode: int,
    password: str,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> str:
    """
    Calls POST /api/signature-response to sign a prior execute-nft or deploy-nft operation.
    Returns the raw signature message from the API.
    """
    url = (base_url or default_base_url).rstrip("/") + "/api/signature-response"
    payload = {
        "id": deploy_id,
        "mode": mode,
        "password": password,
    }
    print("payload", payload)
    try:
        # Send it directly, not wrapped in {"input": ...}
        print("Executing NFT...")
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        print("SIGNATURE-RESPONSE >", data)
    except requests.RequestException as e:
        raise APIError(f"HTTP error during signature_response: {e}") from e
    except ValueError as e:
        raise APIError(f"Invalid JSON in signature_response: {e}") from e
    if not data.get("status", False):
        raise APIError(f"Signature-Response API returned error: {data.get('message', '<no message>')}")

    message = data["message"]
    print("message", message)
    return message


def execute_and_sign(
    comment: str,
    nft: str,
    password: str,
    executor: Optional[str] = None,
    nft_data: str = "",
    nft_value: int = 1,
    quorum_type: int = 2,
    receiver: str = "",
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict[str, str]:
    """
    Full end-to-end for NFT execution:
      1) call execute-nft
      2) call signature-response on the returned id/mode
    Returns a dict with id, mode, and signature.
    """
    # 1) initiate execution
    result = execute_nft(
        comment=comment,
        executor=executor,
        nft=nft,
        nft_data=nft_data,
        nft_value=nft_value,
        quorum_type=quorum_type,
        receiver=receiver,
        base_url=base_url,
        timeout=timeout,
    )

    # 2) sign the execution
    sig = signature_response(
        deploy_id=result["id"],
        mode=result["mode"],
        password=password,
        base_url=base_url,
        timeout=timeout,
    )

    return {
        "id": result["id"],
        "mode": result["mode"],
        "signature": sig,
    }


# ────────────── Example usage ──────────────
if __name__ == "__main__":
    out = execute_and_sign(
        comment="new response",
        nft="QmagiNcz23HVMzMeRp9VrGYHCJAMsbujEHJ2Q5QPZzeWEq",
        password="mypassword",
        executor="bafybmicjf5eulsyudab2a7fcfo5nh2ajhtupid5xx4fzr72m3tcysztyoi",
        nft_data="string",
        nft_value=1,
        quorum_type=2,
        receiver="",
    )
    print("Execute-NFT ID:", out["id"])
    print("Signature:", out["signature"])
