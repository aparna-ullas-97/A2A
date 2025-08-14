import json
import os
from pathlib import Path
import requests

from utils.node_client import NodeClient

node = NodeClient(framework="adk")
default_base_url = node.get_base_url()  
default_did = node.get_did()
print("✅ Using BASE URL:", default_base_url)


print("✅ Using DID for details:", default_did)

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