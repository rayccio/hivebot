import asyncio
import os
import json
import logging
import httpx
import redis.asyncio as redis
import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"{LOG_DIR}/meta-agent.log")
    ]
)
logger = logging.getLogger("meta-agent")

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

# --- Configuration ---
EVALUATION_PERIOD_HOURS = 24
MIN_TASKS_FOR_EVALUATION = 5
TEST_TASK_SAMPLE_SIZE = 10
MAX_TEST_AGENTS_PER_CYCLE = 5
PROMOTION_THRESHOLD = 0.05  # 5% improvement

# --- Database helpers ---
async def fetch_all_agents():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id, data FROM agents")
        )
        rows = result.fetchall()
        agents = []
        for row in rows:
            agent_id = row[0]
            data = row[1]
            if isinstance(data, str):
                data = json.loads(data)
            agents.append((agent_id, data))
        return agents

async def fetch_agent(agent_id: str):
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

async def update_agent(agent_id: str, data: dict):
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE agents SET data = :data, updated_at = NOW() WHERE id = :id"),
            {"data": json.dumps(data), "id": agent_id}
        )
        await session.commit()

async def create_agent(agent_data: dict) -> str:
    import uuid
    agent_id = f"b-{uuid.uuid4().hex[:4]}"
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("INSERT INTO agents (id, data) VALUES (:id, :data)"),
            {"id": agent_id, "data": json.dumps(agent_data)}
        )
        await session.commit()
    return agent_id

async def delete_agent(agent_id: str):
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM agents WHERE id = :id"),
            {"id": agent_id}
        )
        await session.commit()

# --- Fetch evaluation tasks from DB ---
async def fetch_evaluation_tasks(limit: int = TEST_TASK_SAMPLE_SIZE):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id, description, input_data FROM evaluation_tasks WHERE active = true ORDER BY random() LIMIT :limit"),
            {"limit": limit}
        )
        rows = result.fetchall()
        tasks = []
        for row in rows:
            input_data = row[2]
            if isinstance(input_data, str):
                input_data = json.loads(input_data)
            tasks.append({
                "id": row[0],
                "description": row[1],
                "input_data": input_data
            })
        return tasks

# --- Fetch available models from provider config ---
async def fetch_available_models():
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{ORCHESTRATOR_URL}/api/v1/providers",
            headers={"Authorization": f"Bearer {INTERNAL_API_KEY}"}
        )
        resp.raise_for_status()
        data = resp.json()
        models = []
        for provider_key, provider in data.get("providers", {}).items():
            if provider.get("enabled") and provider.get("api_key_present"):
                for model_id, model in provider.get("models", {}).items():
                    if model.get("enabled"):
                        models.append(f"{provider_key}/{model_id}")
        return models

# --- Generate a dummy goal_id per evaluation run ---
def generate_goal_id():
    return f"g-{uuid.uuid4().hex[:8]}"

# --- Performance metrics (from DB) ---
async def get_agent_performance(agent_id: str, hours: int = EVALUATION_PERIOD_HOURS):
    since = datetime.utcnow() - timedelta(hours=hours)
    async with AsyncSessionLocal() as session:
        # Ensure 'since' is a datetime object (defensive)
        if isinstance(since, str):
            since = datetime.fromisoformat(since)
        result = await session.execute(
            text("""
                SELECT data FROM tasks
                WHERE data->>'assigned_agent_id' = :agent_id
                AND (data->>'created_at')::timestamptz >= :since
            """),
            {"agent_id": agent_id, "since": since}
        )
        rows = result.fetchall()
        tasks = []
        for r in rows:
            task_data = r[0]
            if isinstance(task_data, str):
                task_data = json.loads(task_data)
            tasks.append(task_data)
        if len(tasks) < MIN_TASKS_FOR_EVALUATION:
            return None
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        success_rate = completed / total if total > 0 else 0
        timed_tasks = [t for t in tasks if t.get("started_at") and t.get("completed_at")]
        avg_time = 0
        if timed_tasks:
            total_time = sum(
                (datetime.fromisoformat(t["completed_at"]) - datetime.fromisoformat(t["started_at"])).total_seconds()
                for t in timed_tasks
            )
            avg_time = total_time / len(timed_tasks)
        return {
            "agent_id": agent_id,
            "total_tasks": total,
            "completed": completed,
            "success_rate": success_rate,
            "avg_response_time": avg_time,
            "period_hours": hours
        }

# --- Run a single task on an agent and wait for completion using Redis ---
async def run_task_and_wait(agent_id: str, goal_id: str, task_description: str, input_data: dict, timeout: int = 60) -> bool:
    import uuid
    task_id = f"t-{uuid.uuid4().hex[:8]}"
    
    # Connect to Redis
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
    
    # Create a unique completion channel for this task
    completion_channel = f"task:{goal_id}:completed"
    
    # Subscribe to the completion channel before publishing to avoid race
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(completion_channel)
    
    # Publish task_assign message
    message = {
        "type": "task_assign",
        "task_id": task_id,
        "description": task_description,
        "input_data": input_data,
        "goal_id": goal_id,
        "simulation": True  # always run evaluation tasks in simulation mode
    }
    await redis_client.publish(f"agent:{agent_id}", json.dumps(message))
    
    # Wait for completion message
    start = datetime.utcnow()
    async for msg in pubsub.listen():
        if msg["type"] != "message":
            continue
        try:
            data = json.loads(msg["data"])
            if data.get("task_id") == task_id and data.get("goal_id") == goal_id:
                await pubsub.unsubscribe(completion_channel)
                await redis_client.close()
                return True
        except:
            continue
        if (datetime.utcnow() - start).total_seconds() > timeout:
            break
    
    await pubsub.unsubscribe(completion_channel)
    await redis_client.close()
    logger.warning(f"Task {task_id} timed out")
    return False

# --- Run evaluation on agent with given tasks ---
async def evaluate_agent(agent_id: str, tasks: list) -> dict:
    goal_id = generate_goal_id()
    success_count = 0
    results = []
    for task in tasks:
        success = await run_task_and_wait(agent_id, goal_id, task["description"], task.get("input_data", {}))
        if success:
            success_count += 1
        results.append({"task": task["description"], "success": success})
    return {
        "total": len(tasks),
        "success": success_count,
        "success_rate": success_count / len(tasks) if tasks else 0,
        "results": results
    }

# --- Variant generation with provider-aware model mutation ---
async def generate_variant(original_agent: dict, mutation_type: str = "temperature") -> dict:
    """Create a slightly modified copy of the agent for A/B testing."""
    variant = original_agent.copy()
    variant["id"] = None
    variant["name"] = f"{original_agent.get('name', 'Agent')} (test)"
    variant["meta"] = variant.get("meta", {})
    variant["meta"]["parent_agent"] = original_agent.get("id")
    variant["meta"]["improved"] = True
    variant["meta"]["simulation"] = False
    variant["meta"]["mutation"] = mutation_type

    reasoning = variant.get("reasoning", {})
    if mutation_type == "temperature":
        current = reasoning.get("temperature", 0.7)
        delta = random.uniform(-0.2, 0.2)
        reasoning["temperature"] = max(0.1, min(1.0, current + delta))
    elif mutation_type == "prompt":
        if "identityMd" in variant:
            variant["identityMd"] += "\n## Additional Directive\nBe more concise and direct."
    elif mutation_type == "model":
        available_models = await fetch_available_models()
        if available_models:
            current_model = reasoning.get("model")
            others = [m for m in available_models if m != current_model]
            if others:
                reasoning["model"] = random.choice(others)
    elif mutation_type == "skills":
        skills = variant.get("skills", [])
        if not any(s.get("skillId") == "default_search" for s in skills):
            skills.append({"skillId": "default_search", "config": {}})
        variant["skills"] = skills

    variant["reasoning"] = reasoning
    return variant

# --- Main meta-agent loop ---
async def meta_agent_loop():
    while True:
        logger.info("Meta-agent waking up for self-improvement cycle...")
        agents = await fetch_all_agents()
        test_agents_spawned = 0
        evaluation_tasks = await fetch_evaluation_tasks()

        for agent_id, agent_data in agents:
            if agent_data.get("meta", {}).get("improved") or agent_data.get("meta", {}).get("archived"):
                continue
            if agent_data.get("meta", {}).get("last_evaluated"):
                last = datetime.fromisoformat(agent_data["meta"]["last_evaluated"])
                if datetime.utcnow() - last < timedelta(hours=12):
                    continue

            perf = await get_agent_performance(agent_id)
            if not perf:
                continue

            logger.info(f"Agent {agent_id} performance: success_rate={perf['success_rate']:.2f}")

            if perf["success_rate"] < 0.8:
                variant = await generate_variant(agent_data, mutation_type="temperature")
                test_id = await create_agent(variant)
                logger.info(f"Spawned test agent {test_id} from parent {agent_id}")

                parent_eval = await evaluate_agent(agent_id, evaluation_tasks)
                test_eval = await evaluate_agent(test_id, evaluation_tasks)

                if test_eval["success_rate"] > parent_eval["success_rate"] + PROMOTION_THRESHOLD:
                    logger.info(f"Test agent {test_id} outperformed parent! Promoting.")
                    variant["meta"]["simulation"] = False
                    variant["meta"]["improved"] = True
                    variant["meta"]["promoted_at"] = datetime.utcnow().isoformat()
                    await update_agent(test_id, variant)

                    agent_data["meta"]["archived"] = True
                    agent_data["meta"]["archived_at"] = datetime.utcnow().isoformat()
                    await update_agent(agent_id, agent_data)
                else:
                    logger.info(f"Test agent {test_id} did not outperform parent. Deleting.")
                    await delete_agent(test_id)

                agent_data["meta"]["last_evaluated"] = datetime.utcnow().isoformat()
                await update_agent(agent_id, agent_data)

                test_agents_spawned += 1
                if test_agents_spawned >= MAX_TEST_AGENTS_PER_CYCLE:
                    logger.info("Reached max test agents per cycle, breaking.")
                    break

        logger.info("Meta-agent cycle complete. Sleeping for 1 hour.")
        await asyncio.sleep(3600)

async def main():
    logger.info("Starting Meta-Agent (Self-Improvement)...")
    await meta_agent_loop()

if __name__ == "__main__":
    asyncio.run(main())
