import json
import logging
import os
from pathlib import Path
import requests


from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    Part,
    TextPart,
    TaskState,
    UnsupportedOperationError,
)
from a2a.utils.errors import ServerError
from app.agent import KaitlynAgent
from app.sign_api import sign_message 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]                  # .../A2A
cfg_path = Path(os.getenv("CONFIG_PATH", ROOT / "config.json"))

if not cfg_path.exists():
    raise FileNotFoundError(f"config.json not found at: {cfg_path}")

with cfg_path.open("r", encoding="utf-8") as f:
    cfg = json.load(f)

port = int(cfg.get("langgraph_port"))
default_base_url = os.getenv("BASE_URL", f"http://localhost:{port}")
print("Agent Base URL =>", default_base_url)


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
print("✅ Using DID from Agent file:", default_did)


class KaitlynAgentExecutor(AgentExecutor):
    """Kaitlyn's Scheduling AgentExecutor."""

    def __init__(self):
        self.agent = KaitlynAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        if not context.task_id or not context.context_id:
            raise ValueError("RequestContext must have task_id and context_id")
        if not context.message:
            raise ValueError("RequestContext must have a message")

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.submit()
        await updater.start_work()

        query = context.get_user_input()
        try:
            async for item in self.agent.stream(query, context.context_id):
                is_task_complete = item["is_task_complete"]
                require_user_input = item.get("require_user_input", False)
                parts = [Part(root=TextPart(text=item["content"]))]

                if not is_task_complete and not require_user_input:
                    await updater.update_status(
                        TaskState.working,
                        message=updater.new_agent_message(parts),
                    )
                elif require_user_input:
                    await updater.update_status(
                        TaskState.input_required,
                        message=updater.new_agent_message(parts),
                    )
                    break
                else:
                    # Build envelope with original query and agent response
                    agent_response = item["content"]
                    envelope = {
                        "original_message": query,
                        "response": agent_response,
                    }
                    # Canonicalize and sign the envelope
                    envelope_json = json.dumps(envelope, sort_keys=True)
                    try:
                        did = default_did
                        signature = sign_message(envelope_json, did)
                    except Exception as e:
                        logger.error(f"Error signing envelope: {e}")
                        signature = ""

                    payload = {
                        "agent": did,
                        "envelope": envelope,
                        "signature": signature,
                    }
                    # Append both plain reply and signed envelope
                    parts.append(
                        Part(
                            root=TextPart(
                                text=json.dumps(payload, separators=(',', ':'), sort_keys=True)
                            )
                        )
                    )

                    # Return artifacts and complete
                    await updater.add_artifact(parts, name="scheduling_result")
                    await updater.complete()
                    break
        except Exception as e:
            logger.error(f"Error during execution: {e}")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())