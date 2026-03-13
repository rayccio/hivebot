import asyncio
import os
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

logging.basicConfig(level=logging.INFO)
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

# Import tool executor
from tool_executor import ToolExecutor

tool_executor = ToolExecutor(simulator_url=SIMULATOR_URL)

async def get_agent_from_db(agent_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT data FROM agents WHERE id = :id"),
            {"id": agent_id}
        )
        row = result.fetchone()
        if row:
            return json.loads(row[0])
    return None

async def update_agent_state(agent_id: str, new_state: dict):
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE agents SET data = :data, updated_at = NOW() WHERE id = :id"),
            {"data": json.dumps(new_state), "id": agent_id}
        )
        await session.commit()

async def register_agent_idle(agent_id: str):
    """Add agent to Redis idle set."""
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
    await redis_client.sadd("agents:idle", agent_id)
    await redis_client.close()

async def call_ai_delta(agent_id, user_input, model_config):
    url = f"{ORCHESTRATOR_URL}/api/v1/internal/ai/generate-delta"
    headers = {
        "Authorization": f"Bearer {INTERNAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "agent_id": agent_id,
        "input": user_input,
        "config": model_config
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()["response"]

def parse_tool_calls(ai_response: str) -> list:
    """Parse AI response for tool calls in JSON format."""
    tool_calls = []
    pattern = r'\{.*?\}'
    matches = re.findall(pattern, ai_response, re.DOTALL)
    for match in matches:
        try:
            obj = json.loads(match)
            if 'tool' in obj and 'params' in obj:
                tool_calls.append(obj)
        except:
            continue
    return tool_calls

async def process_think_command(agent_id, user_input, model_config, simulation=False):
    agent_data = await get_agent_from_db(agent_id)
    if not agent_data:
        logger.error(f"Agent {agent_id} not found in DB")
        return

    agent_data["status"] = "RUNNING"
    await update_agent_state(agent_id, agent_data)

    response = await call_ai_delta(agent_id, user_input, model_config)

    # Parse and execute tool calls
    tool_calls = parse_tool_calls(response)
    observations = []
    for tc in tool_calls:
        tool_name = tc['tool']
        params = tc['params']
        result = await tool_executor.execute(tool_name, params, simulation)
        observations.append(f"Observation from {tool_name}: {json.dumps(result)}")
    
    # If there were tool calls, we might want to call AI again with observations
    # For now, just append observations to response
    if observations:
        response += "\n" + "\n".join(observations)

    # Update memory
    if "memory" not in agent_data:
        agent_data["memory"] = {"shortTerm": [], "summary": "", "tokenCount": 0}
    agent_data["memory"]["shortTerm"].append(response)
    if len(agent_data["memory"]["shortTerm"]) > 10:
        agent_data["memory"]["shortTerm"] = agent_data["memory"]["shortTerm"][-10:]
    agent_data["memory"]["tokenCount"] += len(response.split()) * 1.3

    agent_data["status"] = "IDLE"
    await update_agent_state(agent_id, agent_data)

    await register_agent_idle(agent_id)

    # Determine reporting target
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

async def process_task_assign(agent_id, task_id, description, input_data, goal_id, simulation=False):
    agent_data = await get_agent_from_db(agent_id)
    if not agent_data:
        logger.error(f"Agent {agent_id} not found in DB")
        return

    agent_data["status"] = "RUNNING"
    await update_agent_state(agent_id, agent_data)

    prompt = f"""You are an autonomous bot with the following identity and tools.

IDENTITY:
{agent_data.get('identityMd', '')}

SOUL:
{agent_data.get('soulMd', '')}

TOOLS:
{agent_data.get('toolsMd', '')}

You have been assigned a task:
Task Description: {description}
Additional input: {json.dumps(input_data, indent=2)}

Carry out the task. Use your tools if needed. When you are done, provide the final output in a clear format.
"""
    response = await call_ai_delta(agent_id, prompt, {})

    # Parse and execute tool calls
    tool_calls = parse_tool_calls(response)
    observations = []
    for tc in tool_calls:
        tool_name = tc['tool']
        params = tc['params']
        result = await tool_executor.execute(tool_name, params, simulation)
        observations.append(f"Observation from {tool_name}: {json.dumps(result)}")
    
    if observations:
        response += "\n" + "\n".join(observations)

    # Update memory
    if "memory" not in agent_data:
        agent_data["memory"] = {"shortTerm": [], "summary": "", "tokenCount": 0}
    agent_data["memory"]["shortTerm"].append(response)
    if len(agent_data["memory"]["shortTerm"]) > 10:
        agent_data["memory"]["shortTerm"] = agent_data["memory"]["shortTerm"][-10:]
    agent_data["memory"]["tokenCount"] += len(response.split()) * 1.3

    agent_data["status"] = "IDLE"
    await update_agent_state(agent_id, agent_data)

    await register_agent_idle(agent_id)

    result = {
        "agent_id": agent_id,
        "task_id": task_id,
        "goal_id": goal_id,
        "output": response,
        "timestamp": datetime.utcnow().isoformat(),
        "simulation": simulation
    }
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
    await redis_client.publish(f"task:{goal_id}:completed", json.dumps(result))
    await redis_client.close()

async def worker_loop():
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("agent:*")
    logger.info("Worker subscribed to agent:*")

    async for message in pubsub.listen():
        if message["type"] != "pmessage":
            continue
        channel = message["channel"]
        data = json.loads(message["data"])
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
                simulation
            ))
        else:
            logger.warning(f"Unknown command {cmd} for agent {agent_id}")

async def main():
    logger.info("Starting HiveBot worker...")
    await worker_loop()

if __name__ == "__main__":
    asyncio.run(main())
