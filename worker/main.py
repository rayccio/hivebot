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
from typing import Optional

# Import role prompts from local constants
import constants

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/worker.log')
    ]
)
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

try:
    from tool_executor import ToolExecutor
    tool_executor = ToolExecutor(simulator_url=SIMULATOR_URL)
except Exception as e:
    logger.exception("Failed to import ToolExecutor, worker will exit")
    raise

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

async def save_artifact(hive_id, goal_id, task_id, file_path, content, status="draft"):
    url = f"{ORCHESTRATOR_URL}/api/v1/hives/{hive_id}/goals/{goal_id}/artifacts"
    async with httpx.AsyncClient() as client:
        files = {'file': (file_path, content)}
        data = {'task_id': task_id, 'file_path': file_path, 'status': status}
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

# ==================== LOOP IMPLEMENTATION ====================

MAX_ITERATIONS = 5

async def execute_task_with_loop(agent_id, task_id, description, input_data, goal_id, hive_id, agent_data, allowed_tools):
    reasoning_config = agent_data.get("reasoning", {})

    async def call_with_role(role_prompt, user_prompt):
        return await call_ai_delta(
            agent_id,
            user_prompt,
            reasoning_config,
            system_prompt_override=role_prompt,
            retries=1
        )

    def make_system_prompt(soul, identity, tools):
        return f"""You are an AI agent with the following STRICT IDENTITY. You must follow this identity exactly.

IDENTITY:
{identity}

SOUL:
{soul}

TOOLS:
{tools}

IMPORTANT: You are NOT a generic AI assistant. You are the entity described above. Always respond in character.
"""

    builder_prompt = make_system_prompt(constants.BUILDER_SOUL, constants.BUILDER_IDENTITY, constants.BUILDER_TOOLS)
    tester_prompt = make_system_prompt(constants.TESTER_SOUL, constants.TESTER_IDENTITY, constants.TESTER_TOOLS)
    reviewer_prompt = make_system_prompt(constants.REVIEWER_SOUL, constants.REVIEWER_IDENTITY, constants.REVIEWER_TOOLS)
    fixer_prompt = make_system_prompt(constants.FIXER_SOUL, constants.FIXER_IDENTITY, constants.FIXER_TOOLS)

    current_code = None
    for iteration in range(1, MAX_ITERATIONS + 1):
        asyncio.create_task(log_execution(goal_id, "info", f"Starting iteration {iteration}", task_id, agent_id, iteration))
        logger.info(f"Agent {agent_id} – Iteration {iteration} for task {task_id}")

        # Builder step
        builder_input = f"""Task: {description}
Additional input: {json.dumps(input_data, indent=2)}
Previous code (if any): {current_code or 'None'}
Generate the code for this task. Output only the code, no explanations."""
        code = await call_with_role(builder_prompt, builder_input)
        asyncio.create_task(log_execution(goal_id, "debug", f"Generated code for iteration {iteration}", task_id, agent_id, iteration))
        file_path = f"task_{task_id}/iteration_{iteration}/code.py"
        await save_artifact(hive_id, goal_id, task_id, file_path, code.encode(), status="draft")
        current_code = code

        # Tester step – enforce JSON output
        tester_input = f"""Task: {description}
Code to test:
{code}
Write and run tests for this code. Output the test results **strictly as a JSON object** with exactly two keys: "passed" (boolean) and "errors" (list of strings). Do not include any other text. Example: {{"passed": false, "errors": ["Test failed because ..."]}}"""
        test_result_text = await call_with_role(tester_prompt, tester_input)
        # Attempt to parse JSON; if fails, treat as failure with error message
        try:
            # Try to extract JSON from response (in case there is extra text)
            json_match = re.search(r'\{.*\}', test_result_text, re.DOTALL)
            if json_match:
                test_result = json.loads(json_match.group())
            else:
                test_result = json.loads(test_result_text)
            if not isinstance(test_result, dict) or "passed" not in test_result:
                raise ValueError("Missing 'passed' key")
        except Exception as e:
            logger.warning(f"Failed to parse tester output: {e}\nOutput: {test_result_text[:500]}")
            test_result = {"passed": False, "errors": [f"Invalid test output: {test_result_text[:200]}"]}
        await save_artifact(hive_id, goal_id, task_id, f"task_{task_id}/iteration_{iteration}/test_result.json", json.dumps(test_result).encode(), status="tested")

        if test_result.get("passed"):
            asyncio.create_task(log_execution(goal_id, "info", f"Task passed on iteration {iteration}", task_id, agent_id, iteration))
            logger.info(f"Task {task_id} passed on iteration {iteration}")
            await save_artifact(hive_id, goal_id, task_id, f"task_{task_id}/final_code.py", current_code.encode(), status="final")
            asyncio.create_task(log_execution(goal_id, "info", f"Task {task_id} completed successfully after {iteration} iterations", task_id, agent_id, iteration))
            return True, iteration
        else:
            asyncio.create_task(log_execution(goal_id, "warning", f"Tests failed on iteration {iteration}: {test_result.get('errors', [])}", task_id, agent_id, iteration))

        # Reviewer step
        reviewer_input = f"""Task: {description}
Code:
{code}
Test errors:
{json.dumps(test_result.get('errors', []), indent=2)}
List the issues in the code that caused the test failures. Provide a list of actionable fixes."""
        issues = await call_with_role(reviewer_prompt, reviewer_input)
        await save_artifact(hive_id, goal_id, task_id, f"task_{task_id}/iteration_{iteration}/issues.txt", issues.encode(), status="reviewed")
        asyncio.create_task(log_execution(goal_id, "info", f"Review completed, issues identified", task_id, agent_id, iteration))

        # Fixer step
        fixer_input = f"""Task: {description}
Code:
{code}
Issues:
{issues}
Provide the fixed code. Output only the corrected code, no explanations."""
        fixed_code = await call_with_role(fixer_prompt, fixer_input)
        current_code = fixed_code
        await save_artifact(hive_id, goal_id, task_id, f"task_{task_id}/iteration_{iteration}/fixed_code.py", fixed_code.encode(), status="fixed")
        asyncio.create_task(log_execution(goal_id, "debug", f"Fixed code applied for iteration {iteration}", task_id, agent_id, iteration))

    asyncio.create_task(log_execution(goal_id, "error", f"Task {task_id} failed after {MAX_ITERATIONS} iterations", task_id, agent_id))
    logger.warning(f"Task {task_id} failed after {MAX_ITERATIONS} iterations")
    return False, MAX_ITERATIONS

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

        tools_md = agent_data.get("tools_md", "")
        allowed_tools = parse_allowed_tools(tools_md)

        response = await call_ai_delta(agent_id, user_input, model_config, retries=1)
        logger.debug(f"Agent {agent_id} AI response: {response[:100]}...")

        tool_calls = parse_tool_calls(response)
        observations = []
        for tc in tool_calls:
            tool_name = tc['tool']
            params = tc['params']
            try:
                result = await tool_executor.execute(tool_name, params, simulation, allowed_tools)
                observations.append(f"Observation from {tool_name}: {json.dumps(result)}")
            except Exception as e:
                observations.append(f"Observation from {tool_name}: error - {str(e)}")
                logger.error(f"Tool {tool_name} execution failed: {e}")

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

        # Ensure memory structure
        if "memory" not in agent_data:
            agent_data["memory"] = {"shortTerm": [], "summary": "", "tokenCount": 0}
        else:
            if "shortTerm" not in agent_data["memory"]:
                agent_data["memory"]["shortTerm"] = []
            if "summary" not in agent_data["memory"]:
                agent_data["memory"]["summary"] = ""
            if "tokenCount" not in agent_data["memory"]:
                agent_data["memory"]["tokenCount"] = 0

        tools_md = agent_data.get("tools_md", "")
        allowed_tools = parse_allowed_tools(tools_md)

        agent_data["status"] = "RUNNING"
        await update_agent_state(agent_id, agent_data)
        logger.info(f"Agent {agent_id} started task {task_id}")

        asyncio.create_task(log_execution(goal_id, "info", f"Task {task_id} assigned to agent {agent_id}", task_id, agent_id))

        success, iterations = await execute_task_with_loop(
            agent_id, task_id, description, input_data, goal_id, hive_id, agent_data, allowed_tools
        )

        agent_data["memory"]["shortTerm"].append(f"Task {task_id} {'succeeded' if success else 'failed'} after {iterations} iterations.")
        if len(agent_data["memory"]["shortTerm"]) > 10:
            agent_data["memory"]["shortTerm"] = agent_data["memory"]["shortTerm"][-10:]
        agent_data["memory"]["tokenCount"] += len(f"Task {task_id} {'succeeded' if success else 'failed'} after {iterations} iterations.".split()) * 1.3

        agent_data["status"] = "IDLE"
        await update_agent_state(agent_id, agent_data)

        await register_agent_idle(agent_id)

        result = {
            "agent_id": agent_id,
            "task_id": task_id,
            "goal_id": goal_id,
            "output": f"Task completed with status: {'success' if success else 'failure'}",
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
    # Ensure logs directory exists
    os.makedirs('/app/logs', exist_ok=True)
    logger.info("Starting HiveBot worker...")
    try:
        await worker_loop()
    except Exception as e:
        logger.exception("Worker crashed")
        raise

if __name__ == "__main__":
    asyncio.run(main())
