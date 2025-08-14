# file: host/utils/node_client.py
from __future__ import annotations
from pathlib import Path
import os, json, requests
from typing import Optional, Union

class NodeClient:
    """
    Minimal client for your local node.
    Resolve base_url from (in order): explicit base_url -> framework name -> port -> config.json -> ENV.
    """

    def __init__(
        self,
        framework: Optional[str] = None,       # e.g., "host", "langgraph", "crew", "adk"
        port: Optional[int] = None,
        base_url: Optional[str] = None,
        config_path: Optional[Union[str, Path]] = None,
    ):
        # If config_path not provided, set it to repo root/config.json
        if not config_path:
            # utils is in A2A/utils, so config.json is one level up from utils
            config_path = Path(__file__).resolve().parent.parent / "config.json"

        print("config path:", config_path)

        # If framework is provided, look for "{framework}_port" in config
        framework_port = self._read_framework_port(framework, config_path)

        self.base_url = (
            base_url
            or os.getenv("BASE_URL")
            or f"http://localhost:{framework_port or port or self._read_port_from_config(config_path)}"
        )

    # --- public API ---
    def get_base_url(self) -> str:
        return self.base_url

    def get_did(self, index: int = 0, timeout: int = 5) -> str:
        try:
            resp = requests.get(f"{self.base_url}/api/get-by-node", timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            txns = data.get("TxnCount") or []
            if len(txns) > index and "DID" in txns[index]:
                return txns[index]["DID"]
            print("⚠️ No DID found in API response, using fallback.")
        except Exception as e:
            print(f"⚠️ Failed to fetch DID from API: {e}")

    # --- helpers ---
    @staticmethod
    def _read_framework_port(framework: str, config_path: Optional[Union[str, Path]]) -> Optional[int]:
        """
        Reads the port from config.json for the given framework name.
        Example: framework="host" → key="host_port"
        """
        path = Path(os.getenv("CONFIG_PATH") or (config_path or NodeClient._default_config_path()))
        try:
            with Path(path).open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            key = f"{framework.lower()}_port"
            return int(cfg.get(key))
        except Exception:
            return None

    @staticmethod
    def _read_port_from_config(config_path: Optional[Union[str, Path]]) -> Optional[int]:
        """
        Fallback to reading generic port or langgraph_port if no framework given.
        """
        path = Path(os.getenv("CONFIG_PATH") or (config_path or NodeClient._default_config_path()))
        try:
            with Path(path).open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            return int(cfg.get("port") or cfg.get("langgraph_port"))
        except Exception:
            return None

    @staticmethod
    def _default_config_path() -> Path:
        # repo root = two levels up from this file (…/A2A)
        here = Path(__file__).resolve()
        return here.parents[2] / "config.json"