import json
import logging
import os
from pathlib import Path
import requests

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils.errors import ServerError
from sign_api import sign_message
from agent import SchedulingAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

class SchedulingAgentExecutor(AgentExecutor):
    """AgentExecutor for the scheduling agent."""

    def __init__(self):
        """Initializes the SchedulingAgentExecutor."""
        self.agent = SchedulingAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Executes the scheduling agent."""
        if not context.task_id or not context.context_id:
            raise ValueError("RequestContext must have task_id and context_id")
        if not context.message:
            raise ValueError("RequestContext must have a message")

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.submit()
        await updater.start_work()

        if self._validate_request(context):
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()
        print("📨 Incoming from Host – full context:", context)
        print("📨 Incoming from Host – user input   :", context.get_user_input())
        try:
            result = self.agent.invoke(query)
            print(f"Final Result ===> {result}")
        except Exception as e:
            print(f"Error invoking agent: {e}")
            raise ServerError(error=InternalError()) from e
        
        envelope = {
            "response": result,
            "original_message": context.get_user_input()
        }

        envelope_json = json.dumps(envelope, sort_keys=True)

        # Build the response parts
        parts = [Part(root=TextPart(text=result))]

        # Add a custom message to the host
        signature = "nates_signature"
        try:
            did = "bafybmicdjf4zsw4w4kff4wuw7jdle3s7yzk22eanh5hovqvrtjpbwim6bq"
            signature = sign_message(envelope_json, did)
            print("signature", signature)
                        
        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
       
        parts = [
            Part(root=TextPart(text=result)),
            Part(root=TextPart(text=json.dumps({
                "agent": did,
                "envelope": envelope,
                "signature": signature
            })))
        ]

        # Send back the combined response
        await updater.add_artifact(parts)
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Handles task cancellation."""
        raise ServerError(error=UnsupportedOperationError())

    def _validate_request(self, context: RequestContext) -> bool:
        """Validates the request context."""
        return False