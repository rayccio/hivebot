from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .core.config import settings
from .api.v1.router import api_router
from .api.v1.endpoints.ws import router as ws_router
from .api.v1.endpoints import internal  # <-- IMPORT INTERNAL ROUTER
from .services.redis_service import redis_service
from .services.ws_manager import manager
from .services.agent_manager import AgentManager
from .services.docker_service import DockerService
from .services.litellm_service import generate_with_messages
from .services.user_manager import UserManager
from .services.task_manager import TaskManager
from .services.vector_service import vector_service
from .models.types import UserCreate, UserRole, GlobalSettings, AgentUpdate
from .api.v1.endpoints.bridges import BRIDGE_CONTAINERS
from .core.database import engine, Base
from .models import db_models  # noqa
import logging
import asyncio
import json
import litellm
import secrets as pysecrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    """Create database tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")

async def sync_bridge_containers():
    """Ensure that only bridges marked as enabled are running."""
    docker = DockerService()
    enabled_bridges = settings.secrets.get("ENABLED_BRIDGES") or []
    for bridge_type, container_name in BRIDGE_CONTAINERS.items():
        status = docker.get_container_status_by_name(container_name)
        is_enabled = bridge_type in enabled_bridges
        if is_enabled and status != "running":
            logger.info(f"Starting bridge {bridge_type} (enabled but not running)")
            try:
                docker.start_container(container_name)
            except Exception as e:
                logger.error(f"Failed to start bridge {bridge_type}: {e}")
        elif not is_enabled and status == "running":
            logger.info(f"Stopping bridge {bridge_type} (disabled but running)")
            try:
                docker.stop_container_by_name(container_name)
            except Exception as e:
                logger.error(f"Failed to stop bridge {bridge_type}: {e}")

async def listen_for_task_completions():
    pubsub = redis_service.client.pubsub()
    await pubsub.psubscribe("task:*:completed")
    logger.info("Subscribed to task completions")
    task_manager = TaskManager()
    async for message in pubsub.listen():
        if message["type"] != "pmessage":
            continue
        try:
            data = json.loads(message["data"])
            goal_id = data.get("goal_id")
            task_id = data.get("task_id")
            output = data.get("output")
            if not goal_id or not task_id:
                continue
            # Update task
            await task_manager.update_task(task_id, status="completed", output_data=output)
            # Check if all tasks in graph are completed
            graph = await task_manager.get_task_graph(goal_id)
            if graph:
                all_done = all(t.status == "completed" for t in graph.tasks)
                if all_done:
                    logger.info(f"Goal {goal_id} completed")
        except Exception as e:
            logger.error(f"Error processing task completion: {e}")

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.ENVIRONMENT != "production" else None,
    )

    # --- Custom exception handler for consistent error responses ---
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "code": "INTERNAL_ERROR"}
        )

    # --- CORS middleware ---
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # --- Include the main API router (does NOT include internal) ---
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # --- Explicitly include the internal AI router under /internal ---
    app.include_router(internal.router, prefix=f"{settings.API_V1_STR}/internal")
    logger.info(f"Included internal router at prefix: {settings.API_V1_STR}/internal")

    # --- WebSocket router (no prefix) ---
    app.include_router(ws_router)

    @app.get("/health")
    async def health_check():
        try:
            docker = DockerService()
            docker.client.ping()
            docker_ok = True
        except:
            docker_ok = False
        return {"status": "ok", "environment": settings.ENVIRONMENT, "docker": docker_ok}

    @app.on_event("startup")
    async def startup_event():
        logger.info("Starting up HiveBot Orchestrator...")
        await init_db()
        await redis_service.wait_ready()
        logger.info("Redis connected")

        # Connect to Qdrant with retries
        await vector_service.connect()
        await vector_service.ensure_collection(dim=384)
        logger.info("Qdrant ready")

        # Initialize global settings if not present
        if not settings.secrets.get("GLOBAL_SETTINGS"):
            default_settings = GlobalSettings(
                login_enabled=False,
                session_timeout=30,
                system_name="HiveBot Orchestrator",
                maintenance_mode=False,
                default_agent_uid="10001",
                rate_limit_enabled=True,
                rate_limit_requests=100,
                rate_limit_period_seconds=60
            )
            settings.secrets.set("GLOBAL_SETTINGS", default_settings.dict())
            logger.info("Initialized global settings with gateway disabled and rate limiting enabled")

        # Create default admin if no users exist
        try:
            user_manager = UserManager()
            users = await user_manager.list_users()
            if not users:
                admin_password = pysecrets.token_urlsafe(12)
                settings.secrets.set("ADMIN_PASSWORD", admin_password)
                admin_user = UserCreate(
                    username="admin",
                    password=admin_password,
                    role=UserRole.GLOBAL_ADMIN,
                    assigned_hive_ids=[]
                )
                await user_manager.create_user(admin_user)
                logger.info(f"Default admin created with password: {admin_password}")
                logger.warning("Please change the admin password immediately after first login.")
        except Exception as e:
            logger.error(f"Failed to create default admin: {e}")

        asyncio.create_task(listen_for_owner_reports())
        asyncio.create_task(listen_for_parent_reports())
        asyncio.create_task(update_agent_memory_from_reports())
        asyncio.create_task(summarize_agent_memories())
        asyncio.create_task(sync_bridge_containers())
        asyncio.create_task(listen_for_task_completions())

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down HiveBot...")
        await manager.disconnect_all()
        await vector_service.close()

    async def listen_for_owner_reports():
        pubsub = redis_service.client.pubsub()
        await pubsub.subscribe("report:owner")
        logger.info("Subscribed to report:owner")
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    response = data.get("response", "")
                    if response.startswith("FORWARD:"):
                        parts = response.split(maxsplit=2)
                        if len(parts) >= 3:
                            _, target_id, forward_msg = parts
                            forward_cmd = {
                                "type": "think",
                                "input": forward_msg,
                                "config": {},
                                "timestamp": data.get("timestamp", "")
                            }
                            await redis_service.publish(f"agent:{target_id}", forward_cmd)
                            logger.info(f"Forwarded message to agent {target_id}")
                            continue
                    await manager.broadcast(message["data"])
                except Exception as e:
                    logger.error(f"Error processing report:owner message: {e}")

    async def listen_for_parent_reports():
        pubsub = redis_service.client.pubsub()
        await pubsub.psubscribe("report:parent:*")
        logger.info("Subscribed to report:parent:*")
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                channel = message["channel"]
                parent_id = channel.split(":")[-1]
                try:
                    data = json.loads(message["data"])
                    forward_msg = {
                        "type": "child_report",
                        "child_id": data.get("agent_id"),
                        "response": data.get("response"),
                        "timestamp": data.get("timestamp")
                    }
                    await redis_service.publish(f"agent:{parent_id}", forward_msg)
                    logger.info(f"Forwarded child report from {data.get('agent_id')} to parent {parent_id}")
                except Exception as e:
                    logger.error(f"Failed to forward parent report: {e}")

    async def update_agent_memory_from_reports():
        pubsub = redis_service.client.pubsub()
        await pubsub.subscribe("report:owner")
        logger.info("Subscribed to report:owner for memory updates")
        docker_service = DockerService()
        agent_manager = AgentManager(docker_service)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
                agent_id = data.get("agent_id")
                response = data.get("response")
                if not agent_id or not response:
                    continue

                agent = await agent_manager.get_agent(agent_id)
                if not agent:
                    continue

                agent.memory.short_term.append(response)
                if len(agent.memory.short_term) > 10:
                    agent.memory.short_term = agent.memory.short_term[-10:]
                agent.memory.token_count += len(response.split()) * 1.3

                await agent_manager.update_agent(agent_id, AgentUpdate(memory=agent.memory))
                logger.debug(f"Updated memory for agent {agent_id}")
            except Exception as e:
                logger.error(f"Failed to update agent memory: {e}")

    async def summarize_agent_memories():
        """Periodically summarize long conversations using cheap models."""
        while True:
            await asyncio.sleep(300)
            try:
                docker_service = DockerService()
                agent_manager = AgentManager(docker_service)
                agents = await agent_manager.list_agents()
                for agent in agents:
                    conversation = await redis_service.get_conversation(agent.id, limit=20)
                    if len(conversation) < 10:
                        continue

                    history = "\n".join([f"{msg.role}: {msg.content}" for msg in conversation])
                    prompt = f"""Summarize the following conversation history of an AI agent.

Agent identity:
{agent.identity_md}

Soul:
{agent.soul_md}

Conversation history:
{history}

Provide a concise summary (max 100 words) that captures the key points and context."""
                    
                    model_config = {}
                    if agent.reasoning.cheap_model:
                        model_config["model"] = agent.reasoning.cheap_model
                    else:
                        provider_config = settings.secrets.get("PROVIDER_CONFIG", {})
                        utility = None
                        for pkey, pconf in provider_config.get("providers", {}).items():
                            for mid, mconf in pconf.get("models", {}).items():
                                if mconf.get("is_utility"):
                                    utility = f"{pkey}/{mid}"
                                    break
                            if utility:
                                break
                        if utility:
                            model_config["model"] = utility
                        else:
                            logger.warning(f"No utility model available for summarization of agent {agent.id}")
                            continue
                    
                    try:
                        messages_for_ai = [{"role": "user", "content": prompt}]
                        response = await generate_with_messages(messages_for_ai, model_config)
                        agent.memory.summary = response
                        await agent_manager.update_agent(agent.id, AgentUpdate(memory=agent.memory))
                        logger.info(f"Summarized memory for agent {agent.id}")
                    except Exception as e:
                        logger.error(f"Summarization failed for agent {agent.id}: {e}")
            except Exception as e:
                logger.exception("Error in memory summarization task")

    # --- Log all registered routes after app creation ---
    logger.info("=== Registered Routes ===")
    for route in app.routes:
        if hasattr(route, "path"):
            logger.info(f"  {route.path}")
    logger.info("=========================")

    return app

app = create_app()
