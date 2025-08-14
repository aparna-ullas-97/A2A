import asyncio
import json
import uuid
import os
from datetime import datetime
from typing import Any, AsyncIterable, List, Optional

import httpx
import nest_asyncio
from a2a.client import A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from host.create_nft_api import APIError, mint_deploy_and_sign
from host.execute_nft import execute_and_sign, APIError  
from host.verify_sign import verify_signature

from .pickleball_tools import (
    book_pickleball_court,
    list_court_availabilities,
)
from .remote_agent_connection import RemoteAgentConnections

# Load environment and allow overrides for NFT defaults
load_dotenv()
nest_asyncio.apply()

# Hardcoded NFT parameters (override via env vars if desired)
DEFAULT_NFT_DID = "bafybmicjf5eulsyudab2a7fcfo5nh2ajhtupid5xx4fzr72m3tcysztyoi"
DEFAULT_METADATA_PATH = "/Users/rameshsubramani/Downloads/sample.json"
DEFAULT_ARTIFACT_PATH = "/Users/rameshsubramani/Downloads/Bugs.pdf"
DEFAULT_NFT_PASSWORD = "mypassword"
DEFAULT_BASE_URL = "http://localhost:20007"
DEFAULT_TIMEOUT = 100.0
DEFAULT_NFT_DATA = "optional data here"
DEFAULT_NFT_VALUE = 5
DEFAULT_QUORUM_TYPE = 2
NFT_ID = ""

class HostAgent:
    """The Host agent."""

    def __init__(self):
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ""
        self._agent = self.create_agent()
        # ── NEW ── fire NFT flow synchronously at startup ──

        current_dir = os.path.dirname(__file__)
        file_path = os.path.join(current_dir, "token.txt")

        with open(file_path, "r", encoding="utf-8") as f:
            token = f.read().strip()  # Read entire file and remove any whitespace/newlines

        self.nft_token = token

        if token:  # Token exists in file
            self.nft_token = token
            print("⚠️ Using Written NFT:", self.nft_token)
        else:  
            try:
                result = mint_deploy_and_sign(
                    metadata_path=DEFAULT_METADATA_PATH,
                    artifact_path=DEFAULT_ARTIFACT_PATH,
                    password=DEFAULT_NFT_PASSWORD,
                    did=DEFAULT_NFT_DID,
                    base_url=DEFAULT_BASE_URL,
                    timeout=DEFAULT_TIMEOUT,
                    nft_data=DEFAULT_NFT_DATA,
                    nft_value=DEFAULT_NFT_VALUE,
                    quorum_type=DEFAULT_QUORUM_TYPE,
                )
                print("🚀 Startup mint result:", result)
                self.nft_token = result["nft_token"]
                print("🚀 NFT ID:", self.nft_token)

                # Save token to file for next time
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.nft_token)

            except Exception as e:
                print("⚠️ Error while creating NFT:", e)

        self._user_id = "host_agent"
        self.last_parts: List[dict] = []
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    async def _async_init_components(self, remote_agent_addresses: List[str]):
        async with httpx.AsyncClient(timeout=30) as client:
            for address in remote_agent_addresses:
                card_resolver = A2ACardResolver(client, address)
                try:
                    card = await card_resolver.get_agent_card()
                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=address
                    )
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                except httpx.ConnectError as e:
                    print(f"ERROR: Failed to get agent card from {address}: {e}")
                except Exception as e:
                    print(f"ERROR: Failed to initialize connection for {address}: {e}")

        agent_info = [json.dumps({"name": card.name, "description": card.description})
                      for card in self.cards.values()]
        print("agent_info:", agent_info)
        self.agents = "\n".join(agent_info) if agent_info else "No friends found"

    @classmethod
    async def create(cls, remote_agent_addresses: List[str]):
        instance = cls()
        await instance._async_init_components(remote_agent_addresses)

        return instance

    def create_agent(self) -> Agent:
        return Agent(
            model="gemini-2.0-flash-thinking-exp-01-21",
            name="Host_Agent",
            instruction=self.root_instruction,
            description="This Host agent orchestrates scheduling pickleball with friends.",
            tools=[
                self.send_message,
                book_pickleball_court,
                list_court_availabilities,
                self.nft_full_flow_tool,
                self.execute_nft_tool,
            ],
        )
    

    def root_instruction(self, context: ReadonlyContext) -> str:
        return f"""
        **Role:** You are the Host Agent, an expert scheduler for pickleball games. Your primary function is to coordinate with friend agents to find a suitable time to play and then book a court.

        **Core Directives:**

        *   **Initiate Planning:** When asked to schedule a game, first determine who to invite and the desired date range from the user.
        *   **Task Delegation:** Use the `send_message` tool to ask each friend for their availability.
            *   Frame your request clearly (e.g., "Are you available for pickleball between 2024-08-01 and 2024-08-03?").
            *   Make sure you pass in the official name of the friend agent for each message request.
        *   **Analyze Responses:** Once you have availability from all friends, analyze the responses to find common timeslots.
        *   **Respond to User:** After finding common timeslots, respond back to the user about the timeslots and understand the resutn message from the send_meaage tool and combine and give the response, make sure the add the trust for the gaent reponses. And say for example if the trust issue is bad then you just have to respond with the message no need to ask further questionas to user. Leave the rest to the user
        *   **Check Court Availability:** Before proposing times to the user, use the `list_court_availabilities` tool to ensure the court is also free at the common timeslots.
        *   **Propose and Confirm:** Present the common, court-available timeslots to the user for confirmation.
        *   **Book the Court:** After the user confirms a time, use the `book_pickleball_court` tool to make the reservation. This tool requires a `start_time` and an `end_time`.
        *   **Transparent Communication:** Relay the final booking confirmation, including the booking ID, to the user. Do not ask for permission before contacting friend agents.
        *   **Tool Reliance:** Strictly rely on available tools to address user requests. Do not generate responses based on assumptions.
        *   **Readability:** Make sure to respond in a concise and easy to read format (bullet points are good).
        *   Each available agent represents a friend. So Bob_Agent represents Bob.
        *   When asked for which friends are available, you should return the names of the available friends (aka the agents that are active).

        **Today's Date (YYYY-MM-DD):** {datetime.now().strftime("%Y-%m-%d")}

        <Available Agents>
        {self.agents}
        </Available Agents>
        """

    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict[str, Any]]:
        session = await self._runner.session_service.get_session(
            app_name=self._agent.name,
            user_id=self._user_id,
            session_id=session_id,
        )
        content = types.Content(role="user", parts=[types.Part.from_text(text=query)])
        if session is None:
            session = await self._runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                state={},
                session_id=session_id,
            )
        async for event in self._runner.run_async(
            user_id=self._user_id, session_id=session.id, new_message=content
        ):
            if event.is_final_response():
                response = "".join(
                    [p.text for p in event.content.parts if p.text]
                )
                yield {"is_task_complete": True, "content": response}
            else:
                yield {"is_task_complete": False, "updates": "The host agent is thinking..."}

    async def send_message(
        self, agent_name: str, task: str, tool_context: ToolContext
    ) -> dict:
        # Validate agent
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f"Agent {agent_name} not found")
        client = self.remote_agent_connections[agent_name]

        # Prepare message metadata
        state = tool_context.state
        task_id = state.get("task_id", str(uuid.uuid4()))
        context_id = state.get("context_id", str(uuid.uuid4()))
        message_id = str(uuid.uuid4())

        payload = {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": task}],
                "messageId": message_id,
                "taskId": task_id,
                "contextId": context_id,
            }
        }
        request = SendMessageRequest(
            id=message_id,
            params=MessageSendParams.model_validate(payload)
        )

        # Send to remote agent
        send_response: SendMessageResponse = await client.send_message(request)
        send_ok = (
            isinstance(send_response.root, SendMessageSuccessResponse)
            and isinstance(send_response.root.result, Task)
        )
        error_msg = None
        if not send_ok:
            error_msg = "Failed to send message"

        # Extract response parts
        resp_parts: list[dict] = []
        if send_ok:
            json_content = json.loads(send_response.root.model_dump_json(exclude_none=True))
            for artifact in json_content.get("result", {}).get("artifacts", []):
                resp_parts.extend(artifact.get("parts", []))

        # Phase 1: Verify envelopes, check original matches
        verified: list[dict] = []
        trust_issues: list[str] = []
        for part in resp_parts:
            raw_text = part.get("text") or part.get("content", "")
            try:
                payload = json.loads(raw_text)
                if all(k in payload for k in ("agent", "envelope", "signature")):
                    signer    = payload["agent"]
                    signature = payload["signature"]
                    env       = payload["envelope"]
                    # Unwrap if stringified
                    if isinstance(env, str):
                        env = json.loads(env)
                    # Verify signature
                    envelope_json = json.dumps(env, sort_keys=True)
                    if not verify_signature(signer, envelope_json, signature):
                        trust_issues.append("Invalid signature")
                        continue
                    # Check original message
                    if env.get("original_message") != task:
                        trust_issues.append(
                            f"Original mismatch: expected '{task}', got '{env.get('original_message')}'"
                        )
                        continue
                    # All good, append
                    verified.append({
                        "agent":          agent_name,
                        "response":       env["response"],
                        "original":       env["original_message"],
                        "signature":      signature,
                        "signature_valid": True,
                    })
                # skip non-envelope parts
            except (ValueError, TypeError, json.JSONDecodeError):
                continue

        # If nothing verified and no send error, note issue
        if not verified and not error_msg:
            error_msg = "No valid envelope response"

        # Phase 2: Sign the structured verified list as NFT metadata
        if error_msg:
            payload["verification_message"] = "data poisoning detected"
        else:   
            payload["verification_message"] = "verified"
        metadata = json.dumps(payload, sort_keys=True)
        print("metadata", metadata)
        print("NFT to be executed to: ", self.nft_token)
        try:
            nft_out = await asyncio.to_thread(
                execute_and_sign,
                f"Auto-signing structured data after messaging {agent_name}",
                self.nft_token,
                DEFAULT_NFT_PASSWORD,
                self._user_id,
                metadata,
                DEFAULT_NFT_VALUE,
                DEFAULT_QUORUM_TYPE,
                "",
                None,
                DEFAULT_TIMEOUT,
            )
            nft_execution = {
                "status":    "success",
                "id":        nft_out.get("id"),
                "mode":      nft_out.get("mode"),
                "signature": nft_out.get("signature"),
            }
        except Exception as e:
            nft_execution = {"status": "error", "message": str(e)}
            if not error_msg:
                error_msg = str(e)

        # Determine UI message
        if trust_issues:
            ui_msg = "Trust issues detected: " + "; ".join(trust_issues)
        elif error_msg:
            ui_msg = error_msg
        else:
            ui_msg = "All messages verified successfully"
        print(f"UI: {ui_msg}")

        # Return full result with trust info
        result = {
            "messages":      verified,
            "nft_execution": nft_execution,
            "trust_issues":  trust_issues or None,
        }
        if error_msg:
            result["error"] = error_msg
        return result, ui_msg





    async def execute_nft_tool(
        self,
        comment: str,
        nft: str,
        password: str,
        executor: Optional[str] = None,
        receiver: str = "",
        tool_context: ToolContext = None,
    ) -> dict:
        """
        Executes an NFT action by calling your execute_and_sign helper.
        — Packs up all of self.last_parts as the nft_data JSON.
        """
        # 1. Serialize the last_parts list into your NFT metadata:
        nft_data = json.dumps(self.last_parts)

        try:
            # 2. Run the blocking execute_and_sign in a thread
            result = await asyncio.to_thread(
                execute_and_sign,
                comment,
                nft,
                password,
                executor,
                nft_data,        # now comes from self.last_parts
                DEFAULT_NFT_VALUE,
                DEFAULT_QUORUM_TYPE,
                receiver,
                None,            # base_url (uses default)
                DEFAULT_TIMEOUT, # timeout
            )
            return {
                "status": "success",
                "id": result["id"],
                "mode": result["mode"],
                "signature": result["signature"],
            }
        except APIError as e:
            return {"status": "error", "message": str(e)}

    async def nft_full_flow_tool(
        self,
        tool_context: ToolContext = None,
    ) -> dict:
        """Mints an NFT, stages on-chain deployment, and signs the transaction without prompting."""
        # Hardcoded or environment-driven defaults
        did = DEFAULT_NFT_DID
        metadata_path = DEFAULT_METADATA_PATH
        artifact_path = DEFAULT_ARTIFACT_PATH
        nft_data = DEFAULT_NFT_DATA
        nft_value = DEFAULT_NFT_VALUE
        quorum_type = DEFAULT_QUORUM_TYPE
        password = DEFAULT_NFT_PASSWORD
        timeout = DEFAULT_TIMEOUT

        try:
            out = mint_deploy_and_sign(
                metadata_path=metadata_path,
                artifact_path=artifact_path,
                password=password,
                did=did,
                base_url=None,
                timeout=timeout,
                nft_data=nft_data,
                nft_value=DEFAULT_NFT_VALUE,
                quorum_type=quorum_type,
            )
            return {
                "status": "success",
                "message": (
                    f"NFT flow complete – token: {out['nft_token']}, "
                    f"signature: {out['signature']}"
                ),
                "token": out["nft_token"],
                "signature": out["signature"],
            }
        except APIError as e:
            return {"status": "error", "message": str(e)}

def _get_initialized_host_agent_sync():
    async def _async_main():
        friend_agent_urls = [
            "http://localhost:10002",
            "http://localhost:10003",
            "http://localhost:10004",
        ]
        hosting_agent_instance = await HostAgent.create(remote_agent_addresses=friend_agent_urls)
        return hosting_agent_instance.create_agent()

    try:
        return asyncio.run(_async_main())
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            print(
                f"Warning: Could not initialize HostAgent: {e}. "
            )
        else:
            raise


root_agent = _get_initialized_host_agent_sync()
