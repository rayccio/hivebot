import asyncio
import os
import sys
import json
import logging
import asyncpg
import redis.asyncio as redis
import httpx
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
import re
from typing import Optional
from pathlib import Path

# Add layers directory to sys.path so that custom loop handlers and planners can be imported
sys.path.insert(0, '/app/layers')

# Configure logging to file – allow override via environment variable
LOG_DIR = Path(os.getenv('HIVEBOT_LOG_DIR', '/app/logs'))
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "worker.log")
    ]
)

import constants

logger = logging.getLogger("hivebot-worker")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_USER = os.getenv("POSTGRES_USER", "hivebot")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "hivebot")
POSTGRES_DB = os.getenv("POSTGRES_DB", "hivebot")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://backend:8000")
SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://simulator:8080")

DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

from skill_executor import SkillExecutor
skill_executor = SkillExecutor(simulator_url=SIMULATOR_URL)

from loop_handler import registry as loop_handler_registry, BaseLoopHandler
from container_manager import container_manager

# ==================== HELPER FUNCTIONS ====================

async def get_agent_from_db(agent_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT data FROM agents WHERE id = :id"),
            {"id": agent_id}
        )
        row = result.fetchone()
        if row:
            data = row[0]
            if isinstance(data, str):
                return json.loads(data)
            return data
    return None

async def update_agent_state(agent_id: str, new_state: dict):
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE agents SET data = :data, updated_at = NOW() WHERE id = :id"),
            {"data": json.dumps(new_state), "id": agent_id}
        )
        await session.commit()

async def register_agent_idle(agent_id: str):
    try:
        redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
        await redis_client.sadd("agents:idle", agent_id)
        await redis_client.close()
        logger.debug(f"Agent {agent_id} registered as idle")
    except Exception as e:
        logger.error(f"Failed to register agent {agent_id} as idle: {e}")

async def call_ai_delta(agent_id, user_input, model_config, system_prompt_override=None, retries=1):
    url = f"{ORCHESTRATOR_URL}/api/v1/internal/ai/generate-delta"
    headers = {
        "Authorization": f"Bearer {INTERNAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "agent_id": agent_id,
        "input": user_input,
        "config": model_config,
        "system_prompt_override": system_prompt_override
    }
    async with httpx.AsyncClient() as client:
        for attempt in range(retries + 1):
            try:
                logger.info(f"Calling AI endpoint (attempt {attempt+1}): {url}")
                logger.debug(f"Payload: {payload}")
                resp = await client.post(url, json=payload, headers=headers, timeout=60)
                logger.info(f"AI response status: {resp.status_code}")
                if resp.status_code == 404:
                    logger.error(f"404 response body: {resp.text}")
                    if attempt < retries:
                        logger.info(f"Retrying in 0.5 seconds...")
                        await asyncio.sleep(0.5)
                        continue
                    else:
                        raise httpx.HTTPStatusError(f"404 after {retries} retries", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp.json()["response"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404 and attempt < retries:
                    logger.info(f"404, retrying in 0.5 seconds...")
                    await asyncio.sleep(0.5)
                    continue
                else:
                    raise

def parse_tool_calls(ai_response: str) -> list:
    pattern = r'\{.*?\}'
    matches = re.findall(pattern, ai_response, re.DOTALL)
    tool_calls = []
    for match in matches:
        try:
            obj = json.loads(match)
            if 'tool' in obj and 'params' in obj:
                tool_calls.append(obj)
        except:
            continue
    return tool_calls

def parse_allowed_tools(tools_md: str) -> list:
    allowed = []
    in_permitted_section = False
    for line in tools_md.splitlines():
        line = line.strip()
        if line.startswith('## Permitted Tools'):
            in_permitted_section = True
            continue
        elif line.startswith('## '):
            in_permitted_section = False
            continue
        if in_permitted_section and line.startswith('- '):
            parts = line[2:].split()
            if parts:
                tool = parts[0].strip('`*_')
                allowed.append(tool)
    return allowed

async def save_artifact(hive_id, goal_id, task_id, file_path, content, status="draft", layer_id=None, parent_artifact_id=None):
    url = f"{ORCHESTRATOR_URL}/api/v1/hives/{hive_id}/goals/{goal_id}/artifacts"
    async with httpx.AsyncClient() as client:
        files = {'file': (file_path, content)}
        data = {
            'task_id': task_id,
            'file_path': file_path,
            'status': status
        }
        if layer_id:
            data['layer_id'] = layer_id
        if parent_artifact_id:
            data['parent_artifact_id'] = parent_artifact_id
        resp = await client.post(url, data=data, files=files, headers={"Authorization": f"Bearer {INTERNAL_API_KEY}"})
        resp.raise_for_status()
        return resp.json()

async def read_artifact(hive_id, goal_id, task_id, file_path):
    url = f"{ORCHESTRATOR_URL}/api/v1/hives/{hive_id}/goals/{goal_id}/artifacts/latest?task_id={task_id}&file_path={file_path}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {INTERNAL_API_KEY}"})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.content

async def update_artifact_status(hive_id: str, goal_id: str, artifact_id: str, status: str):
    url = f"{ORCHESTRATOR_URL}/api/v1/hives/{hive_id}/goals/{goal_id}/artifacts/{artifact_id}/status"
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            url,
            data={"status": status},
            headers={"Authorization": f"Bearer {INTERNAL_API_KEY}"}
        )
        resp.raise_for_status()

# ==================== EXECUTION LOGGING ====================

async def log_execution(goal_id: str, level: str, message: str, task_id: Optional[str] = None, agent_id: Optional[str] = None, iteration: Optional[int] = None):
    url = f"{ORCHESTRATOR_URL}/api/v1/internal/logs/execution"
    headers = {
        "Authorization": f"Bearer {INTERNAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "goal_id": goal_id,
        "level": level,
        "message": message,
        "task_id": task_id,
        "agent_id": agent_id,
        "iteration": iteration
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers, timeout=5)
    except Exception as e:
        logger.warning(f"Failed to send execution log: {e}")

# ==================== COMMAND PROCESSING ====================

async def process_think_command(agent_id, user_input, model_config, simulation=False):
    try:
        agent_data = await get_agent_from_db(agent_id)
        if not agent_data:
            logger.error(f"Agent {agent_id} not found in DB")
            return

        agent_data["status"] = "RUNNING"
        await update_agent_state(agent_id, agent_data)
        logger.info(f"Agent {agent_id} started think command")

        # Get allowed skills from agent's installed skills
        allowed_skills = {s['skillId'] for s in agent_data.get('skills', []) if s.get('enabled', True)}

        # Retrieve sandbox level from Redis (set by task assign)
        redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
        sandbox_level = await redis_client.get(f"agent:{agent_id}:sandbox") or "skill"
        task_id = await redis_client.get(f"agent:{agent_id}:current_task") or None
        project_id = await redis_client.get(f"agent:{agent_id}:current_project") or None
        await redis_client.close()

        response = await call_ai_delta(agent_id, user_input, model_config, retries=1)
        logger.debug(f"Agent {agent_id} AI response: {response[:100]}...")

        tool_calls = parse_tool_calls(response)
        observations = []
        for tc in tool_calls:
            skill_name = tc['tool']
            params = tc['params']
            try:
                result = await skill_executor.execute(
                    skill_name, params, simulation, list(allowed_skills),
                    sandbox_level=sandbox_level,
                    task_id=task_id,
                    project_id=project_id,
                    agent_id=agent_id
                )
                observations.append(f"Observation from {skill_name}: {json.dumps(result)}")
            except Exception as e:
                observations.append(f"Observation from {skill_name}: error - {str(e)}")
                logger.error(f"Skill {skill_name} execution failed: {e}")

        if observations:
            response += "\n" + "\n".join(observations)

        if "memory" not in agent_data:
            agent_data["memory"] = {"shortTerm": [], "summary": "", "tokenCount": 0}
        else:
            if "shortTerm" not in agent_data["memory"]:
                agent_data["memory"]["shortTerm"] = []
            if "summary" not in agent_data["memory"]:
                agent_data["memory"]["summary"] = ""
            if "tokenCount" not in agent_data["memory"]:
                agent_data["memory"]["tokenCount"] = 0
        agent_data["memory"]["shortTerm"].append(response)
        if len(agent_data["memory"]["shortTerm"]) > 10:
            agent_data["memory"]["shortTerm"] = agent_data["memory"]["shortTerm"][-10:]
        agent_data["memory"]["tokenCount"] += len(response.split()) * 1.3

        agent_data["status"] = "IDLE"
        await update_agent_state(agent_id, agent_data)

        await register_agent_idle(agent_id)

        reporting_target = agent_data.get("reportingTarget", "PARENT_AGENT")
        parent_id = agent_data.get("parentId")

        channels_to_publish = []
        if reporting_target == "PARENT_AGENT" and parent_id:
            channels_to_publish.append(f"report:parent:{parent_id}")
        elif reporting_target == "OWNER_DIRECT":
            channels_to_publish.append("report:owner")
        elif reporting_target == "HYBRID":
            if parent_id:
                channels_to_publish.append(f"report:parent:{parent_id}")
            channels_to_publish.append("report:owner")
        else:
            channels_to_publish.append("report:owner")

        result = {
            "agent_id": agent_id,
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
            "simulation": simulation
        }
        redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
        for ch in channels_to_publish:
            await redis_client.publish(ch, json.dumps(result))
        await redis_client.close()
        logger.info(f"Agent {agent_id} finished think command")
    except Exception as e:
        logger.exception(f"Unhandled error in process_think_command for agent {agent_id}")
        try:
            agent_data = await get_agent_from_db(agent_id)
            if agent_data:
                agent_data["status"] = "ERROR"
                agent_data["last_active"] = datetime.utcnow().isoformat()
                await update_agent_state(agent_id, agent_data)
        except:
            pass

async def process_task_assign(agent_id, task_id, description, input_data, goal_id, hive_id, simulation=False):
    try:
        await asyncio.sleep(0.5)

        agent_data = await get_agent_from_db(agent_id)
        if not agent_data:
            logger.error(f"Agent {agent_id} not found in DB")
            return

        # Ensure memory structure exists
        if "memory" not in agent_data:
            agent_data["memory"] = {"shortTerm": [], "summary": "", "tokenCount": 0}
        else:
            if "shortTerm" not in agent_data["memory"]:
                agent_data["memory"]["shortTerm"] = []
            if "summary" not in agent_data["memory"]:
                agent_data["memory"]["summary"] = ""
            if "tokenCount" not in agent_data["memory"]:
                agent_data["memory"]["tokenCount"] = 0

        # Get allowed skills from agent's installed skills
        allowed_skills = {s['skillId'] for s in agent_data.get('skills', []) if s.get('enabled', True)}

        agent_data["status"] = "RUNNING"
        await update_agent_state(agent_id, agent_data)
        logger.info(f"Agent {agent_id} started task {task_id}")

        asyncio.create_task(log_execution(goal_id, "info", f"Task {task_id} assigned to agent {agent_id}", task_id, agent_id))

        # Fetch full task data from DB to get loop_handler, project_id, sandbox_level, and layer_id
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT data FROM tasks WHERE id = :id"),
                {"id": task_id}
            )
            row = result.fetchone()
            if not row:
                logger.error(f"Task {task_id} not found in DB")
                return
            task_data = row[0]
            if isinstance(task_data, str):
                task_data = json.loads(task_data)
            loop_handler_name = task_data.get("loop_handler", "default")
            project_id = task_data.get("project_id")
            sandbox_level = task_data.get("sandbox_level", "task")
            layer_id = task_data.get("layer_id", "core")

        # Store sandbox level and current task in Redis for this agent
        redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
        await redis_client.set(f"agent:{agent_id}:sandbox", sandbox_level)
        await redis_client.set(f"agent:{agent_id}:current_task", task_id)
        await redis_client.set(f"agent:{agent_id}:current_project", project_id or "")
        await redis_client.close()

        # Get loop handler class
        handler_class = loop_handler_registry.get(loop_handler_name)
        if not handler_class:
            logger.warning(f"Loop handler '{loop_handler_name}' not found, using default")
            handler_class = loop_handler_registry.default()
        if not handler_class:
            raise Exception("No default loop handler available")

        handler = handler_class()
        loop_result = await handler.run(
            agent_id=agent_id,
            task_id=task_id,
            description=description,
            input_data=input_data,
            goal_id=goal_id,
            hive_id=hive_id,
            project_id=project_id,
            skill_executor=skill_executor,
            call_ai_delta=call_ai_delta,
            save_artifact=save_artifact,
            update_artifact_status=update_artifact_status,
            layer_id=layer_id
        )

        success = loop_result.get("success", False)
        iterations = loop_result.get("iterations", 0)

        agent_data["memory"]["shortTerm"].append(f"Task {task_id} {'succeeded' if success else 'failed'} after {iterations} iterations.")
        if len(agent_data["memory"]["shortTerm"]) > 10:
            agent_data["memory"]["shortTerm"] = agent_data["memory"]["shortTerm"][-10:]
        agent_data["memory"]["tokenCount"] += len(f"Task {task_id} {'succeeded' if success else 'failed'} after {iterations} iterations.".split()) * 1.3

        agent_data["status"] = "IDLE"
        await update_agent_state(agent_id, agent_data)

        await register_agent_idle(agent_id)

        # Clean up Redis keys and containers
        redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
        await redis_client.delete(f"agent:{agent_id}:sandbox")
        await redis_client.delete(f"agent:{agent_id}:current_task")
        await redis_client.delete(f"agent:{agent_id}:current_project")
        await redis_client.close()

        # Clean up container if it was task-level
        if sandbox_level == "task":
            await container_manager.cleanup_task(task_id)
        elif sandbox_level == "project" and project_id:
            # Optionally keep project container alive; we'll not clean it here.
            pass

        # Build a structured output dict
        output_data = {
            "success": success,
            "iterations": iterations,
            "task_id": task_id,
            "goal_id": goal_id,
            "final_artifact": loop_result.get("output", {}).get("final_artifact"),
            "message": loop_result.get("output", {}).get("message", "Task completed")
        }

        result = {
            "agent_id": agent_id,
            "task_id": task_id,
            "goal_id": goal_id,
            "output": output_data,
            "timestamp": datetime.utcnow().isoformat(),
            "simulation": simulation,
            "iterations": iterations,
            "success": success
        }
        redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
        await redis_client.publish(f"task:{goal_id}:completed", json.dumps(result))
        await redis_client.close()
        logger.info(f"Agent {agent_id} completed task {task_id}")
    except Exception as e:
        logger.exception(f"Unhandled error in process_task_assign for agent {agent_id} on task {task_id}")
        asyncio.create_task(log_execution(goal_id, "error", f"Exception in task {task_id}: {str(e)}", task_id, agent_id))
        try:
            agent_data = await get_agent_from_db(agent_id)
            if agent_data:
                agent_data["status"] = "ERROR"
                agent_data["last_active"] = datetime.utcnow().isoformat()
                await update_agent_state(agent_id, agent_data)
        except:
            pass

async def worker_loop():
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("agent:*")
    logger.info("Worker subscribed to agent:*")

    async for message in pubsub.listen():
        if message["type"] != "pmessage":
            continue
        channel = message["channel"]
        try:
            data = json.loads(message["data"])
        except Exception as e:
            logger.error(f"Failed to parse message on {channel}: {e}")
            continue
        cmd = data.get("type")
        agent_id = channel.split(":")[1]
        simulation = data.get("simulation", False)

        if cmd == "think":
            asyncio.create_task(process_think_command(
                agent_id,
                data.get("input", ""),
                data.get("config", {}),
                simulation
            ))
        elif cmd == "task_assign":
            asyncio.create_task(process_task_assign(
                agent_id,
                data.get("task_id"),
                data.get("description"),
                data.get("input_data", {}),
                data.get("goal_id"),
                data.get("hive_id"),
                simulation
            ))
        else:
            logger.warning(f"Unknown command {cmd} for agent {agent_id}")

async def main():
    logger.info("Starting HiveBot worker...")

    # Load loop handler registry
    async with AsyncSessionLocal() as session:
        await loop_handler_registry.load_from_db(session)
        if loop_handler_registry.get('default'):
            logger.info("Default loop handler is registered.")
        else:
            logger.error("Default loop handler is NOT registered!")

    try:
        await worker_loop()
    except Exception as e:
        logger.exception("Worker crashed")
        raise

if __name__ == "__main__":
    asyncio.run(main())
