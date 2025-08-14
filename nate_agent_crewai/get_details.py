from pathlib import Path
import sys
import requests

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.node_client import NodeClient

node = NodeClient(framework="crew")
default_base_url = node.get_base_url()  
default_did = node.get_did()

print("✅ Details Using DID for details:", default_did)
print("✅ Details Using base URL:", default_base_url)

endpoint = "/api/get-account-info"
params   = {
    "did": default_did
}

headers = {
    "Accept":        "application/json",
}

resp = requests.get(f"{default_base_url}{endpoint}", headers=headers, params=params)

try:
    resp.raise_for_status()
    data = resp.json()
    print("Full response payload:", data)
    print("Account balance for DID", params["did"], "→", data.get("balance"))
except requests.exceptions.HTTPError as e:
    print(f"HTTP {resp.status_code} error:", resp.text)