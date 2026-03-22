import os
import asyncio
import asyncpg
import redis.asyncio as redis
import logging
import json
import httpx
from datetime import datetime, timedelta
from aiohttp import web
from pathlib import Path

# Configure logging to file – allow override via environment variable
LOG_DIR = Path(os.getenv('HIVEBOT_LOG_DIR', '/app/logs'))
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "scheduler.log")
    ]
)
logger = logging.getLogger("hive-core")

# Redis settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# PostgreSQL settings
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_USER = os.getenv("POSTGRES_USER", "hivebot")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "hivebot")
POSTGRES_DB = os.getenv("POSTGRES_DB", "hivebot")

POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# Orchestrator settings
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://backend:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
if not INTERNAL_API_KEY:
    raise ValueError("INTERNAL_API_KEY environment variable is required")

TASK_TIMEOUT_SECONDS = int(os.getenv("TASK_TIMEOUT_SECONDS", 300))
ORCHESTRATOR_INTERVAL = int(os.getenv("ORCHESTRATOR_INTERVAL", 5))

async def wait_for_db(pg_pool, retries=30, delay=2):
    for attempt in range(retries):
        try:
            async with pg_pool.acquire() as conn:
                result = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'agents'
                    )
                """)
                if result:
                    logger.info("Database tables are ready.")
                    return
                else:
                    logger.warning(f"Agents table not yet created (attempt {attempt+1}/{retries})")
        except Exception as e:
            logger.warning(f"Database connection error (attempt {attempt+1}/{retries}): {e}")
        await asyncio.sleep(delay)
    raise Exception("Database not ready after multiple attempts")

async def health_check(request):
    return web.json_response({"status": "ok", "service": "hive-core"})

async def start_health_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8087)
    await site.start()
    logger.info("Health server started on port 8087")

async def populate_pending_tasks(pg_pool, redis_client):
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, data, created_at FROM tasks WHERE data->>'status' = 'pending'")
        logger.info(f"Found {len(rows)} pending tasks in DB")
        for row in rows:
            if rows.index(row) == 0:
                task_data = row['data']
                if isinstance(task_data, str):
                    task_data = json.loads(task_data)
                logger.info(f"Sample task keys: {list(task_data.keys())}")
            score = row['created_at'].timestamp() * 1000
            await redis_client.zadd("tasks:pending", {row['id']: score})
    logger.info(f"Populated {len(rows)} pending tasks into Redis")

async def populate_idle_agents(pg_pool, redis_client):
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id FROM agents WHERE data->>'status' = 'IDLE'")
        for row in rows:
            await redis_client.sadd("agents:idle", row['id'])
    logger.info(f"Populated {len(rows)} idle agents into Redis")

async def fetch_goals(pg_pool, statuses):
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT data FROM goals WHERE data->>'status' = ANY($1)",
            statuses
        )
        goals = []
        for r in rows:
            goal_data = r['data']
            if isinstance(goal_data, str):
                goal_data = json.loads(goal_data)
            goals.append(goal_data)
        return goals

async def fetch_tasks_for_goal(pg_pool, goal_id):
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT data FROM tasks WHERE data->>'goalId' = $1",
            goal_id
        )
        if rows:
            logger.debug(f"Found {len(rows)} tasks using key 'goalId' for goal {goal_id}")
        else:
            rows = await conn.fetch(
                "SELECT data FROM tasks WHERE data->>'goal_id' = $1",
                goal_id
            )
            if rows:
                logger.debug(f"Found {len(rows)} tasks using key 'goal_id' for goal {goal_id}")
            else:
                sample = await conn.fetch("SELECT data FROM tasks LIMIT 1")
                if sample:
                    sample_data = sample[0]['data']
                    if isinstance(sample_data, str):
                        sample_data = json.loads(sample_data)
                    logger.info(f"No tasks for goal {goal_id}. Sample task keys: {list(sample_data.keys())}")
        tasks = []
        for r in rows:
            data = r['data']
            if isinstance(data, str):
                data = json.loads(data)
            tasks.append(data)
        return tasks

async def are_dependencies_met(pg_pool, task_id, depends_on):
    if not depends_on:
        return True
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT data FROM tasks WHERE id = ANY($1)",
            depends_on
        )
        for r in rows:
            data = r['data']
            if isinstance(data, str):
                data = json.loads(data)
            if data.get('status') != 'completed':
                return False
        return True

async def spawn_agent_for_task(hive_id, required_skill_ids, agent_type):
    url = f"{ORCHESTRATOR_URL}/api/v1/internal/ai/agents/spawn"
    headers = {"Authorization": f"Bearer {INTERNAL_API_KEY}"}
    payload = {
        "hive_id": hive_id,
        "required_skill_ids": required_skill_ids,
        "agent_type": agent_type
    }
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Spawning agent for hive {hive_id}, skills {required_skill_ids}, type {agent_type}")
            resp = await client.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            agent_id = data.get("agent_id")
            logger.info(f"Agent spawned: {agent_id}")
            return agent_id
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error spawning agent: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to spawn agent: {e}")
            return None

async def assign_task(pg_pool, redis_client, task, agent_id):
    task['status'] = 'assigned'
    task['assigned_agent_id'] = agent_id
    task['started_at'] = datetime.utcnow().isoformat()
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE tasks SET data = $1 WHERE id = $2",
            json.dumps(task), task['id']
        )
    async with pg_pool.acquire() as conn:
        agent_row = await conn.fetchrow("SELECT data FROM agents WHERE id = $1", agent_id)
        if agent_row:
            agent_data = agent_row['data']
            if isinstance(agent_data, str):
                agent_data = json.loads(agent_data)
            agent_data['status'] = 'ASSIGNED'
            await conn.execute(
                "UPDATE agents SET data = $1 WHERE id = $2",
                json.dumps(agent_data), agent_id
            )
    await redis_client.zrem("tasks:pending", task['id'])
    await redis_client.srem("agents:idle", agent_id)
    message = {
        'type': 'task_assign',
        'task_id': task['id'],
        'description': task['description'],
        'input_data': task.get('input_data', {}),
        'goal_id': task['goal_id'],
        'hive_id': task.get('hive_id'),
        'loop_handler': task.get('loop_handler'),   # NEW
        'project_id': task.get('project_id')        # NEW
    }
    await redis_client.publish(f"agent:{agent_id}", json.dumps(message))
    logger.info(f"Assigned task {task['id']} to agent {agent_id}")

async def handle_task_completion(pg_pool, redis_client, goal_id, task_id, output):
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT data FROM tasks WHERE id = $1", task_id)
        if not row:
            logger.error(f"Task {task_id} not found")
            return
        task_data = row['data']
        if isinstance(task_data, str):
            task_data = json.loads(task_data)
        task_data['status'] = 'completed'
        task_data['output_data'] = output
        task_data['completed_at'] = datetime.utcnow().isoformat()
        await conn.execute(
            "UPDATE tasks SET data = $1 WHERE id = $2",
            json.dumps(task_data), task_id
        )

    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT to_task FROM task_edges WHERE from_task = $1",
            task_id
        )
        for row in rows:
            dep_task_id = row['to_task']
            dep_row = await conn.fetchrow("SELECT data FROM tasks WHERE id = $1", dep_task_id)
            if not dep_row:
                continue
            dep_data = dep_row['data']
            if isinstance(dep_data, str):
                dep_data = json.loads(dep_data)
            if dep_data['status'] != 'pending':
                continue
            depends_on = dep_data.get('depends_on', [])
            if await are_dependencies_met(pg_pool, dep_task_id, depends_on):
                created_at = datetime.fromisoformat(dep_data['created_at'])
                score = created_at.timestamp() * 1000
                await redis_client.zadd("tasks:pending", {dep_task_id: score})
                logger.info(f"Task {dep_task_id} is now ready and added to pending")

    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT data FROM tasks WHERE data->>'goalId' = $1 OR data->>'goal_id' = $1",
            goal_id
        )
        all_tasks = []
        for r in rows:
            data = r['data']
            if isinstance(data, str):
                data = json.loads(data)
            all_tasks.append(data)
        if all(t.get('status') == 'completed' for t in all_tasks):
            await conn.execute(
                "UPDATE goals SET data = jsonb_set(data, '{status}', '\"completed\"') WHERE id = $1",
                goal_id
            )
            logger.info(f"Goal {goal_id} completed")

async def orchestrator_loop(pg_pool, redis_client):
    logger.info("Orchestrator loop started")
    while True:
        try:
            logger.info("Orchestrator loop iteration")
            goals = await fetch_goals(pg_pool, ["planning", "executing"])
            logger.info(f"Fetched {len(goals)} goals with status planning/executing")
            for goal in goals:
                goal_id = goal['id']
                tasks = await fetch_tasks_for_goal(pg_pool, goal_id)
                logger.info(f"Goal {goal_id} has {len(tasks)} tasks")
                ready_tasks = []
                for t in tasks:
                    if t['status'] != 'pending':
                        continue
                    if await are_dependencies_met(pg_pool, t['id'], t.get('depends_on', [])):
                        ready_tasks.append(t)

                logger.info(f"Goal {goal_id} has {len(ready_tasks)} ready tasks")
                for task in ready_tasks:
                    required_skills = task.get('required_skills', [])
                    idle_agent_ids = await redis_client.smembers("agents:idle")
                    logger.info(f"Idle agents count: {len(idle_agent_ids)}")
                    if not idle_agent_ids:
                        logger.info(f"No idle agents, spawning new agent for task {task['id']}")
                        agent_id = await spawn_agent_for_task(
                            goal['hive_id'],
                            required_skills,
                            task.get('agent_type', 'builder')
                        )
                        if agent_id:
                            await assign_task(pg_pool, redis_client, task, agent_id)
                        else:
                            logger.warning(f"Failed to spawn agent for task {task['id']}")
                    else:
                        async with pg_pool.acquire() as conn:
                            rows = await conn.fetch(
                                "SELECT id, data FROM agents WHERE id = ANY($1)",
                                list(idle_agent_ids)
                            )
                            matching_agent = None
                            for row in rows:
                                agent_id = row['id']
                                agent_data = row['data']
                                if isinstance(agent_data, str):
                                    agent_data = json.loads(agent_data)
                                agent_skills = [s['skillId'] for s in agent_data.get('skills', [])]
                                if set(required_skills).issubset(set(agent_skills)):
                                    matching_agent = agent_id
                                    break
                            if matching_agent:
                                logger.info(f"Assigning task {task['id']} to existing agent {matching_agent}")
                                await assign_task(pg_pool, redis_client, task, matching_agent)
                            else:
                                logger.info(f"No matching idle agent, spawning new for task {task['id']}")
                                agent_id = await spawn_agent_for_task(
                                    goal['hive_id'],
                                    required_skills,
                                    task.get('agent_type', 'builder')
                                )
                                if agent_id:
                                    await assign_task(pg_pool, redis_client, task, agent_id)
                                else:
                                    logger.warning(f"Failed to spawn agent for task {task['id']}")
        except Exception as e:
            logger.exception("Error in orchestrator loop")
        await asyncio.sleep(ORCHESTRATOR_INTERVAL)

async def listen_for_task_completions(pg_pool, redis_client):
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("task:*:completed")
    logger.info("Subscribed to task:*:completed")
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
            await handle_task_completion(pg_pool, redis_client, goal_id, task_id, output)
        except Exception as e:
            logger.error(f"Error processing task completion: {e}")

async def maintenance_loop(pg_pool, redis_client):
    while True:
        await asyncio.sleep(30)
        task_ids = await redis_client.zrange("tasks:pending", 0, -1)
        if task_ids:
            async with pg_pool.acquire() as conn:
                for task_id in task_ids:
                    row = await conn.fetchrow("SELECT data FROM tasks WHERE id = $1", task_id)
                    if not row:
                        await redis_client.zrem("tasks:pending", task_id)
                        continue
                    raw_data = row['data']
                    if isinstance(raw_data, str):
                        task_data = json.loads(raw_data)
                    else:
                        task_data = raw_data
                    if task_data.get('status') != 'pending':
                        await redis_client.zrem("tasks:pending", task_id)
                        logger.debug(f"Removed {task_id} from pending queue (status {task_data['status']})")

        now = datetime.utcnow()
        async with pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, data FROM tasks
                WHERE data->>'status' = 'assigned'
                AND (data->>'started_at')::timestamptz < $1
            """, now - timedelta(seconds=TASK_TIMEOUT_SECONDS))
            for row in rows:
                task_id = row['id']
                raw_data = row['data']
                if isinstance(raw_data, str):
                    task_data = json.loads(raw_data)
                else:
                    task_data = raw_data
                agent_id = task_data.get('assigned_agent_id')
                logger.warning(f"Task {task_id} timed out, re-queuing")
                task_data['status'] = 'pending'
                task_data['assigned_agent_id'] = None
                task_data.pop('started_at', None)
                await conn.execute(
                    "UPDATE tasks SET data = $1 WHERE id = $2",
                    json.dumps(task_data), task_id
                )
                created_at = datetime.fromisoformat(task_data['created_at'])
                score = created_at.timestamp() * 1000
                await redis_client.zadd("tasks:pending", {task_id: score})
                if agent_id:
                    await redis_client.srem("agents:idle", agent_id)
                    agent_row = await conn.fetchrow("SELECT data FROM agents WHERE id = $1", agent_id)
                    if agent_row:
                        raw_agent = agent_row['data']
                        if isinstance(raw_agent, str):
                            agent_data = json.loads(raw_agent)
                        else:
                            agent_data = raw_agent
                        agent_data['status'] = 'ERROR'
                        agent_data['last_active'] = datetime.utcnow().isoformat()
                        await conn.execute(
                            "UPDATE agents SET data = $1 WHERE id = $2",
                            json.dumps(agent_data), agent_id
                        )

async def main():
    pg_pool = await asyncpg.create_pool(POSTGRES_DSN)
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)

    await wait_for_db(pg_pool)

    asyncio.create_task(start_health_server())

    await populate_pending_tasks(pg_pool, redis_client)
    await populate_idle_agents(pg_pool, redis_client)

    asyncio.create_task(maintenance_loop(pg_pool, redis_client))
    asyncio.create_task(listen_for_task_completions(pg_pool, redis_client))
    asyncio.create_task(orchestrator_loop(pg_pool, redis_client))

    logger.info("Hive Core orchestrator started")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await redis_client.close()
        await pg_pool.close()

if __name__ == "__main__":
    asyncio.run(main())
