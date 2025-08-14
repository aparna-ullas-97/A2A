import json
import logging
from pathlib import Path
import sys

# Add repo root (A2A) to sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.node_client import NodeClient



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

node = NodeClient(framework="crew")
default_base_url = node.get_base_url()  # http://localhost:20007
default_did = node.get_did()

print("✅ Agent Using DID for details:", default_did)
print("✅ Agent Using base URL:", default_base_url)

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

        parts = [Part(root=TextPart(text=result))]

        signature = "nates_signature"
        try:
            did = default_did
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
        await updater.add_artifact(parts)
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Handles task cancellation."""
        raise ServerError(error=UnsupportedOperationError())

    def _validate_request(self, context: RequestContext) -> bool:
        """Validates the request context."""
        return False