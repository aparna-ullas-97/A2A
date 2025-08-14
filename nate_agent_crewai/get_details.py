import json
import os
from pathlib import Path
import requests


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]                  # .../A2A
cfg_path = Path(os.getenv("CONFIG_PATH", ROOT / "config.json"))

if not cfg_path.exists():
    raise FileNotFoundError(f"config.json not found at: {cfg_path}")

with cfg_path.open("r", encoding="utf-8") as f:
    cfg = json.load(f)

port = int(cfg.get("crew_port"))
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
# # 1) Configuration
# BASE_URL   = os.getenv("API_BASE_URL", "http://localhost:20000")

# 2) Endpoint + query params
endpoint = "/api/get-account-info"
params   = {
    "did": default_did
}

# 3) Headers (adjust or omit as your API requires)
headers = {
    "Accept":        "application/json",
}

# 4) Make the GET request
resp = requests.get(f"{default_base_url}{endpoint}", headers=headers, params=params)

# 5) Check for errors & parse
try:
    resp.raise_for_status()
    data = resp.json()
    print("Full response payload:", data)
    print("Account balance for DID", params["did"], "→", data.get("balance"))
except requests.exceptions.HTTPError as e:
    print(f"HTTP {resp.status_code} error:", resp.text)