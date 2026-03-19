from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from sqlalchemy import text
from ....services.litellm_service import generate_with_messages
from ....services.redis_service import redis_service
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....services.vector_service import vector_service
from ....services.embedding_client import trigger_message_embedding
from ....core.config import settings
from ....core.database import AsyncSessionLocal
from ....models.types import ConversationMessage, HiveMindAccessLevel, Hive
from datetime import datetime
import secrets
import logging
import traceback
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai")

# This log line confirms the module is imported and the router is created
logger.info("Internal AI router loaded")

# Load embedding model once at startup (module level)
try:
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    logger.info("Embedding model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load embedding model: {e}")
    embedding_model = None

class GenerateDeltaRequest(BaseModel):
    agent_id: str
    input: str
    config: Dict[str, Any] = {}
    system_prompt_override: Optional[str] = None

class GenerateResponse(BaseModel):
    response: str

# ==================== NEW: SPAWN AGENT REQUEST ====================
class SpawnAgentRequest(BaseModel):
    hive_id: str
    required_skill_ids: List[str]
    agent_type: str

# ===================================================================

async def verify_internal_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    scheme, token = authorization.split()
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    expected = settings.secrets.get("INTERNAL_API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="Internal API key not configured")
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Invalid token")
    return token

async def get_hive_for_agent(agent_id: str) -> Optional[str]:
    """Direct database query to find the hive containing this agent."""
    async with AsyncSessionLocal() as session:
        # Cast the JSON field to JSONB and use the ? operator to check if agent_id is in the array
        result = await session.execute(
            text("SELECT data FROM hives WHERE (data->'agent_ids')::jsonb ? :agent_id"),
            {"agent_id": agent_id}
        )
        row = result.fetchone()
        if row:
            hive_data = row[0]
            # row[0] is already a dict (deserialized by asyncpg)
            return hive_data.get("id")
    return None

@router.get("/ping")
async def ping():
    """Simple endpoint to check if the internal router is mounted."""
    logger.info("Ping endpoint called")
    return {"status": "ok"}

@router.get("/")
async def root():
    """Root of internal AI router – for debugging."""
    logger.info("Internal AI root called")
    return {"message": "Internal AI router is mounted"}

@router.post("/generate-delta", response_model=GenerateResponse)
async def ai_generate_delta(
    request: GenerateDeltaRequest,
    token: str = Depends(verify_internal_token)
):
    logger.info(f"Generate-delta called for agent {request.agent_id}")

    # Wrap everything in a try/except to catch and log any exception
    try:
        agent_id = request.agent_id
        user_input = request.input
        config = request.config
        system_override = request.system_prompt_override

        # Log before Redis calls
        logger.info(f"Fetching conversation for agent {agent_id} from Redis")
        conversation = await redis_service.get_conversation(agent_id, limit=50)

        user_msg = ConversationMessage(
            role="user",
            content=user_input,
            timestamp=datetime.utcnow()
        )
        await redis_service.push_conversation_message(agent_id, user_msg)
        logger.info(f"Conversation updated for agent {agent_id}")

        # Get agent from DB
        logger.info(f"Fetching agent {agent_id} from database...")
        docker_service = DockerService()
        agent_manager = AgentManager(docker_service)
        agent = await agent_manager.get_agent(agent_id)
        if not agent:
            logger.error(f"Agent {agent_id} not found in database")
            raise HTTPException(status_code=404, detail="Agent not found")
        logger.info(f"Agent {agent_id} found: {agent.name}")

        # Get hive_id for this agent via direct query
        hive_id = await get_hive_for_agent(agent_id)
        if not hive_id:
            logger.error(f"Agent {agent_id} not associated with any hive (direct query)")
            raise HTTPException(status_code=404, detail="Agent not associated with any hive")

        # Fetch hive details for context and config
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT data FROM hives WHERE id = :hive_id"),
                {"hive_id": hive_id}
            )
            row = result.fetchone()
            if not row:
                logger.error(f"Hive {hive_id} not found")
                raise HTTPException(status_code=404, detail="Hive not found")
            hive_data = row[0]
            # Convert to Hive model for easier access
            hive = Hive.model_validate(hive_data)

        hive_config = hive.hive_mind_config

        # --- RAG: retrieve relevant context from hive (files and messages) ---
        context_str = ""
        if embedding_model is not None:
            try:
                query_vector = embedding_model.encode(user_input).tolist()
                # Determine which hive_ids to search
                search_hive_ids = [hive_id]
                if hive_config.accessLevel == HiveMindAccessLevel.SHARED:
                    search_hive_ids.extend(hive_config.sharedHiveIds)
                elif hive_config.accessLevel == HiveMindAccessLevel.GLOBAL:
                    # For global, we need all hives – but that's expensive; for now, just use current hive
                    # We could fetch all hives here, but keep it simple
                    pass

                filter_condition = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="hive_id",
                            match=models.MatchAny(any=search_hive_ids)
                        )
                    ]
                )

                retrieved = await vector_service.search(query_vector, filter_condition, limit=5)
                context_blocks = []
                for item in retrieved:
                    source = item.get("source", "unknown")
                    text = item.get("text", "")
                    if source == "message":
                        context_blocks.append(f"Previous conversation: {text}")
                    elif source == "file":
                        context_blocks.append(f"File excerpt: {text}")
                    else:
                        context_blocks.append(text)
                context_str = "\n\n".join(context_blocks) if context_blocks else ""
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
                context_str = ""

        # --- NEW: Get long‑term memories for this agent ---
        long_term_memories = await agent_manager.get_long_term_memory(agent_id, user_input, limit=3)
        if long_term_memories:
            memory_text = "\n\n".join([f"Past memory: {m}" for m in long_term_memories])
            if context_str:
                context_str += "\n\n" + memory_text
            else:
                context_str = memory_text

        global_user_md = hive.global_user_md

        # Build sub-agents list
        sub_agents_info = []
        if agent.sub_agent_ids:
            for sub_id in agent.sub_agent_ids:
                sub_agent = await agent_manager.get_agent(sub_id)
                if sub_agent:
                    identity_full = sub_agent.identity_md.strip()
                    soul_full = sub_agent.soul_md.strip()
                    sub_agents_info.append(
                        f"- ID: {sub_agent.id}, Name: {sub_agent.name}, Role: {sub_agent.role}\n"
                        f"  Identity:\n{identity_full}\n"
                        f"  Soul:\n{soul_full}"
                    )
        if sub_agents_info:
            sub_agents_text = "CURRENT SUB-AGENTS (full context):\n" + "\n\n".join(sub_agents_info)
        else:
            sub_agents_text = "CURRENT SUB-AGENTS: None."

        communication_instruction = (
            "IMPORTANT: If a user asks you to pass a message to another agent (e.g., 'Give this code to CoS'), "
            "you should forward the message to that agent. Use the following method:\n"
            "- If you have a tool like `send_message` or `outbound-notifier`, use it with destination='agent:<ID>'.\n"
            "- Otherwise, respond with a special prefix 'FORWARD: <target_id> <message>' and the orchestrator will handle it.\n"
            "If you are unsure, ask the user to specify the target agent and the channel (if needed)."
        )

        # Use system override if provided, otherwise build from agent data
        if system_override:
            system_content = system_override
        else:
            system_content = f"""You are an AI agent with the following STRICT IDENTITY. You must follow this identity exactly and not default to generic AI responses.

IDENTITY (MANDATORY):
{agent.identity_md}

SOUL (MANDATORY):
{agent.soul_md}

TOOLS (MANDATORY):
{agent.tools_md}

HIVE CONTEXT (MANDATORY):
{global_user_md}

RELEVANT RETRIEVED KNOWLEDGE:
{context_str}

{sub_agents_text}

{communication_instruction}

IMPORTANT: You are NOT a generic AI assistant. You are the entity described above. Always respond in character. Never say you are ChatGPT or a generic language model. When asked about your sub‑agents, only mention the agents listed above. Do not invent additional agents.
"""

        messages = [{"role": "system", "content": system_content}]
        for msg in conversation:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_input})

        logger.info(f"System message for agent {agent_id}: {system_content[:200]}...")

        try:
            logger.info(f"Calling generate_with_messages for agent {agent_id}")
            response = await generate_with_messages(messages, config)
            logger.info(f"AI generation successful for agent {agent_id}")
        except Exception as e:
            logger.exception("AI generation failed")
            raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

        assistant_msg = ConversationMessage(
            role="assistant",
            content=response,
            timestamp=datetime.utcnow()
        )
        await redis_service.push_conversation_message(agent_id, assistant_msg)

        await redis_service.trim_conversation(agent_id, keep_last=100)

        # --- Trigger embedding for the new assistant message (short‑term memory) ---
        await trigger_message_embedding(agent_id, hive_id, response, datetime.utcnow().isoformat())

        logger.info(f"Generate-delta completed for agent {agent_id}")
        return GenerateResponse(response=response)

    except HTTPException:
        # Re-raise HTTP exceptions as they are (they already have the desired status code)
        raise
    except Exception as e:
        # Log the full traceback for any other exception
        logger.error(f"Unhandled exception in generate-delta for agent {request.agent_id}: {e}")
        logger.error(traceback.format_exc())
        # Return a 500 error
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# ==================== NEW ENDPOINT: SPAWN AGENT ====================
@router.post("/agents/spawn", response_model=dict)
async def spawn_agent(
    request: SpawnAgentRequest,
    token: str = Depends(verify_internal_token)
):
    """Internal endpoint to spawn a new agent for a task."""
    from ....services.agent_manager import AgentManager
    from ....services.docker_service import DockerService
    docker = DockerService()
    agent_manager = AgentManager(docker)
    agent = await agent_manager.spawn_agent_for_task(
        hive_id=request.hive_id,
        required_skill_ids=request.required_skill_ids,
        agent_type=request.agent_type
    )
    if not agent:
        raise HTTPException(status_code=500, detail="Failed to spawn agent")
    return {"agent_id": agent.id}

# ==================== CATCH-ALL FOR DEBUGGING ====================
@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(request: Request, path: str):
    """Catch-all route to log any unmatched requests to this router."""
    logger.error(f"Internal AI router catch-all: method={request.method}, path={path}, full_url={request.url}")
    # Attempt to read body for POST requests
    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
            logger.error(f"Request body: {body}")
        except:
            pass
    return JSONResponse(status_code=404, content={"detail": "Not found"})
