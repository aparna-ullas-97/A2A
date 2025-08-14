import os
import json
from pathlib import Path
import requests
from typing import Optional, Dict

class APIError(Exception):
    """Raised when an external API call fails or returns invalid data."""
    pass

# Base URL for the service (can override via env var)
# default_base_url = os.getenv("API_BASE_URL", "http://localhost:20007")
# default_did = "bafybmicjf5eulsyudab2a7fcfo5nh2ajhtupid5xx4fzr72m3tcysztyoi"

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]                  # .../A2A
cfg_path = Path(os.getenv("CONFIG_PATH", ROOT / "config.json"))

if not cfg_path.exists():
    raise FileNotFoundError(f"config.json not found at: {cfg_path}")

with cfg_path.open("r", encoding="utf-8") as f:
    cfg = json.load(f)

port = int(cfg.get("host_port", 20007))
default_base_url = os.getenv("BASE_URL", f"http://localhost:{port}")
print("Base URL =>", default_base_url)

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
print("✅ Using DID:", default_did)

def create_nft(
    did: Optional[str],
    metadata_path: str,
    artifact_path: str,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> str:
    print("CREATE")
    url = (base_url or default_base_url).rstrip("/") + "/api/create-nft"
    # split out did as a text field, and only metadata+artifact in files
    data = {"did": did or default_did}
    files = {
        "metadata": (
            os.path.basename(metadata_path),
            open(metadata_path, "rb"),
            "application/json",
        ),
        "artifact": (
            os.path.basename(artifact_path),
            open(artifact_path, "rb"),
            "application/octet-stream",
        ),
    }
    

    try:
        resp = requests.post(url, data=data, files=files, timeout=timeout)
        print("resp", resp)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise APIError(f"HTTP error during create_nft: {e}") from e
    except ValueError as e:
        raise APIError(f"Invalid JSON in create_nft response: {e}") from e
    finally:
        for _name, f in files.items():
            # close any file handles
            if hasattr(f[1], "close"):
                f[1].close()

    print("data", data)

    if not data.get("status", False):
        raise APIError(f"Create-NFT API returned error: {data.get('message', '<no message>')}")
    token = data.get("result")
    if not isinstance(token, str):
        raise APIError(f"Unexpected result field in create_nft: {token!r}")
    return token

def deploy_nft(
    did: str,
    nft_token: str,
    nft_data: str,
    nft_file_name: str,
    nft_metadata: str,
    nft_value: int,
    quorum_type: int,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict:
    """
    Calls POST /api/deploy-nft to stage the on‐chain deployment.
    Returns the parsed `result` object (containing id, mode, etc.)
    """
    print("DEPLOY")
    url = (base_url or default_base_url).rstrip("/") + "/api/deploy-nft"
    payload = {
        "did": did,
        "nft": nft_token,
        "nft_data": nft_data,
        "nft_file_name": nft_file_name,
        "nft_metadata": nft_metadata,
        "nft_value": nft_value,
        "quorum_type": quorum_type,
    }
    print("payload", payload)
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise APIError(f"HTTP error during deploy_nft: {e}") from e
    except ValueError as e:
        raise APIError(f"Invalid JSON in deploy_nft response: {e}") from e

    if not data.get("status", False):
        raise APIError(f"Deploy-NFT API returned error: {data.get('message', '<no message>')}")
    result = data.get("result")
    if not isinstance(result, dict) or "id" not in result or "mode" not in result:
        raise APIError(f"Unexpected result field in deploy_nft: {result!r}")
    return result

def signature_response(
    deploy_id: str,
    mode: int,
    password: str,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> str:
    url = (base_url or default_base_url).rstrip("/") + "/api/signature-response"

    # Build the flat payload exactly as Swagger expects:
    payload = {
        "id": deploy_id,
        "mode": mode,
        "password": password,
    }
    print("SIGNATURE-REQUEST >", payload)

    try:
        # Send it directly, not wrapped in {"input": ...}
        print("Here1")
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        print("SIGNATURE-RESPONSE >", data)
    except requests.RequestException as e:
        print("Here2")
        raise APIError(f"HTTP error during signature_response: {e}") from e
    except ValueError as e:
        print("Here3")
        raise APIError(f"Invalid JSON in signature_response: {e}") from e

    if not data.get("status", False):
        print("Here4")
        raise APIError(f"Signature-Response API returned error: {data.get('message', '<no message>')}")

    print("Here5")
    message = data["message"]
    print("message", message)
    return message

def mint_deploy_and_sign(
    metadata_path: str,
    artifact_path: str,
    password: str,
    did: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
    # below args are passed straight to deploy_nft; adjust as you like
    nft_data: str = "",
    nft_value: int = 1,
    quorum_type: int = 2,
) -> Dict[str, str]:
    """
    Full end-to-end:
      1) create NFT
      2) deploy NFT
      3) sign deployment
    Returns a dict:
      {
        "nft_token": "<Qm…>",
        "signature": "3044…"
      }
    """
    # 1) mint
    token = create_nft(did, metadata_path, artifact_path, base_url, timeout)

    # 2) stage deployment
    deploy_info = deploy_nft(
        did or default_did,
        token,
        nft_data=nft_data,
        nft_file_name=os.path.basename(artifact_path),
        nft_metadata=json.dumps(json.load(open(metadata_path, "r"))),
        nft_value=nft_value,
        quorum_type=quorum_type,
        base_url=base_url,
        timeout=timeout,
    )

    # 3) sign it
    sig = signature_response(deploy_info["id"], deploy_info["mode"], password, base_url, timeout)

    return {
        "nft_token": token,
        "signature": sig,
    }

# # ────────────── Example usage ──────────────
# if __name__ == "__main__":
#     out = mint_deploy_and_sign(
#         metadata_path="/Users/rameshsubramani/Downloads/sample.json",
#         artifact_path="/Users/rameshsubramani/Downloads/Bugs.pdf",
#         password="mypassword",
#         did=None,            # or override
#         nft_data="optional data here",
#         nft_value=1,
#         quorum_type=2,
#     )
#     print("Minted NFT:", out["nft_token"])
#     print("Chain signature:", out["signature"])