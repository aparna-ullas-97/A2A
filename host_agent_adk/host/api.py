import os
import requests

# 1) Configuration
BASE_URL   = os.getenv("API_BASE_URL", "http://localhost:20000")

# 2) Endpoint + query params
endpoint = "/api/get-account-info"
params   = {
    "did": "bafybmigkmdklseni5ynibyyy5yp67rfn7tx2k2j7gdkulefy5cbhh7jnii"
}

# 3) Headers (adjust or omit as your API requires)
headers = {
    "Accept":        "application/json",
}

# 4) Make the GET request
resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params)

# 5) Check for errors & parse
try:
    resp.raise_for_status()
    data = resp.json()
    print("Full response payload:", data)
    print("Account balance for DID", params["did"], "→", data.get("balance"))
except requests.exceptions.HTTPError as e:
    print(f"HTTP {resp.status_code} error:", resp.text)