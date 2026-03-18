import os
import asyncio
import asyncpg
import redis.asyncio as redis
import logging
import json
import httpx
from datetime import datetime, timedelta
from aiohttp import web

logging.basicConfig(level=logging.INFO)
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

TASK_TIMEOUT_SECONDS = int(os.getenv("TASK_TIMEOUT_SECONDS", 300))  # 5 minutes
ORCHESTRATOR_INTERVAL = int(os.getenv("ORCHESTRATOR_INTERVAL", 5))   # seconds between loops

async def wait_for_db(pg_pool, retries=30, delay=2):
    """Wait for the agents and goals tables to exist."""
    for attempt in range(retries):
        try:
            async with pg_pool.acquire() as conn:
                # Check if agents table exists
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
    """Load all pending tasks from DB and add to Redis sorted set."""
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, created_at FROM tasks WHERE data->>'status' = 'pending'")
        for row in rows:
            score = row['created_at'].timestamp() * 1000
            await redis_client.zadd("tasks:pending", {row['id']: score})
    logger.info(f"Populated {len(rows)} pending tasks into Redis")

async def populate_idle_agents(pg_pool, redis_client):
    """Load all idle agents from DB and add to Redis set."""
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id FROM agents WHERE data->>'status' = 'IDLE'")
        for row in rows:
            await redis_client.sadd("agents:idle", row['id'])
    logger.info(f"Populated {len(rows)} idle agents into Redis")

async def fetch_goals(pg_pool, statuses):
    """Fetch goals with given statuses."""
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT data FROM goals WHERE data->>'status' = ANY($1)",
            [statuses]
        )
        return [json.loads(r['data']) for r in rows]

async def fetch_tasks_for_goal(pg_pool, goal_id):
    """Fetch all tasks for a goal."""
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT data FROM tasks WHERE data->>'goalId' = $1",   # <-- corrected key
            goal_id
        )
        tasks = []
        for r in rows:
            data = r['data']
            if isinstance(data, str):
                data = json.loads(data)
            tasks.append(data)
        return tasks

async def fetch_task_edges(pg_pool, goal_id):
    """Fetch all edges for tasks of a goal."""
    # Get all task IDs for this goal
    async with pg_pool.acquire() as conn:
        task_ids = await conn.fetch(
            "SELECT id FROM tasks WHERE data->>'goalId' = $1",   # <-- corrected key
            goal_id
        )
        task_ids = [t['id'] for t in task_ids]
        if not task_ids:
            return []
        rows = await conn.fetch(
            "SELECT from_task, to_task FROM task_edges WHERE from_task = ANY($1) OR to_task = ANY($1)",
            task_ids
        )
        return [{"from": r['from_task'], "to": r['to_task']} for r in rows]

async def are_dependencies_met(pg_pool, task_id, depends_on):
    """Check if all dependencies of a task are completed."""
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
    """Call internal API to spawn an agent."""
    url = f"{ORCHESTRATOR_URL}/api/v1/internal/agents/spawn"
    headers = {"Authorization": f"Bearer {INTERNAL_API_KEY}"}
    payload = {
        "hive_id": hive_id,
        "required_skill_ids": required_skill_ids,
        "agent_type": agent_type
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get("agent_id")
        except Exception as e:
            logger.error(f"Failed to spawn agent: {e}")
            return None

async def assign_task(pg_pool, redis_client, task, agent_id):
    """Assign a task to an agent."""
    # Update task in DB
    task['status'] = 'assigned'
    task['assigned_agent_id'] = agent_id
    task['started_at'] = datetime.utcnow().isoformat()
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE tasks SET data = $1 WHERE id = $2",
            json.dumps(task), task['id']
        )
    # Update agent status in DB
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
    # Remove from Redis queues
    await redis_client.zrem("tasks:pending", task['id'])
    await redis_client.srem("agents:idle", agent_id)
    # Publish task_assign message
    message = {
        'type': 'task_assign',
        'task_id': task['id'],
        'description': task['description'],
        'input_data': task.get('input_data', {}),
        'goal_id': task['goal_id'],
        'hive_id': task.get('hive_id')
    }
    await redis_client.publish(f"agent:{agent_id}", json.dumps(message))
    logger.info(f"Assigned task {task['id']} to agent {agent_id}")

async def handle_task_completion(pg_pool, redis_client, goal_id, task_id, output):
    """Handle task completion: update task status and push new ready tasks."""
    # Fetch task
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

    # Find dependent tasks
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT to_task FROM task_edges WHERE from_task = $1",
            task_id
        )
        for row in rows:
            dep_task_id = row['to_task']
            # Fetch the dependent task
            dep_row = await conn.fetchrow("SELECT data FROM tasks WHERE id = $1", dep_task_id)
            if not dep_row:
                continue
            dep_data = dep_row['data']
            if isinstance(dep_data, str):
                dep_data = json.loads(dep_data)
            if dep_data['status'] != 'pending':
                continue
            # Check if all its dependencies are met
            depends_on = dep_data.get('depends_on', [])
            if await are_dependencies_met(pg_pool, dep_task_id, depends_on):
                # Push to pending queue
                created_at = datetime.fromisoformat(dep_data['created_at'])
                score = created_at.timestamp() * 1000
                await redis_client.zadd("tasks:pending", {dep_task_id: score})
                logger.info(f"Task {dep_task_id} is now ready and added to pending")

    # Check if goal is complete
    async with pg_pool.acquire() as conn:
        # Get all tasks for this goal
        rows = await conn.fetch(
            "SELECT data FROM tasks WHERE data->>'goalId' = $1",   # <-- corrected key
            goal_id
        )
        all_tasks = []
        for r in rows:
            data = r['data']
            if isinstance(data, str):
                data = json.loads(data)
            all_tasks.append(data)
        if all(t.get('status') == 'completed' for t in all_tasks):
            # Update goal status
            await conn.execute(
                "UPDATE goals SET data = jsonb_set(data, '{status}', '\"completed\"') WHERE id = $1",
                goal_id
            )
            logger.info(f"Goal {goal_id} completed")

async def orchestrator_loop(pg_pool, redis_client):
    """Main orchestrator loop: process goals and assign tasks."""
    while True:
        try:
            # Fetch all goals that are planning or executing
            goals = await fetch_goals(pg_pool, ["planning", "executing"])
            for goal in goals:
                goal_id = goal['id']
                # Fetch all tasks for this goal
                tasks = await fetch_tasks_for_goal(pg_pool, goal_id)
                # Build task map
                task_map = {t['id']: t for t in tasks}
                # Find ready tasks (pending and dependencies satisfied)
                ready_tasks = []
                for t in tasks:
                    if t['status'] != 'pending':
                        continue
                    if await are_dependencies_met(pg_pool, t['id'], t.get('depends_on', [])):
                        ready_tasks.append(t)

                for task in ready_tasks:
                    # Try to find an idle agent with required skills
                    required_skills = task.get('required_skills', [])
                    # Get idle agents from Redis
                    idle_agent_ids = await redis_client.smembers("agents:idle")
                    if not idle_agent_ids:
                        # No idle agents, spawn one
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
                        # Fetch agent data to check skills
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
                                await assign_task(pg_pool, redis_client, task, matching_agent)
                            else:
                                # No matching idle agent, spawn one
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
    """Subscribe to task completion events and handle them."""
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
    """Periodically remove tasks that are no longer pending from Redis, and handle timeouts."""
    while True:
        await asyncio.sleep(30)
        # Remove completed/failed tasks
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

        # Handle timed-out tasks (assigned but not completed)
        now = datetime.utcnow()
        async with pg_pool.acquire() as conn:
            # Find tasks that are assigned and started more than TASK_TIMEOUT_SECONDS ago
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
                # Reset task status
                task_data['status'] = 'pending'
                task_data['assigned_agent_id'] = None
                task_data.pop('started_at', None)
                await conn.execute(
                    "UPDATE tasks SET data = $1 WHERE id = $2",
                    json.dumps(task_data), task_id
                )
                # Re-add to pending queue (using original created_at as score)
                created_at = datetime.fromisoformat(task_data['created_at'])
                score = created_at.timestamp() * 1000
                await redis_client.zadd("tasks:pending", {task_id: score})
                # Remove agent from idle set if it was there? Actually agent may be dead; we'll handle separately.
                if agent_id:
                    await redis_client.srem("agents:idle", agent_id)
                    # Optionally mark agent as error
                    agent_row = await conn.fetchrow("SELECT data FROM agents WHERE id = $1", agent_id)
                    if agent_row:
                        raw_agent = agent_row['data']
                        if isinstance(raw_agent, str):
                            agent_data = json.loads(raw_agent)
                        else:
                            agent_data = raw_agent
                        agent_data['status'] = 'ERROR'
                        await conn.execute(
                            "UPDATE agents SET data = $1 WHERE id = $2",
                            json.dumps(agent_data), agent_id
                        )

async def main():
    pg_pool = await asyncpg.create_pool(POSTGRES_DSN)
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)

    # Wait for database tables to be ready
    await wait_for_db(pg_pool)

    # Start health server
    asyncio.create_task(start_health_server())

    # Initial population
    await populate_pending_tasks(pg_pool, redis_client)
    await populate_idle_agents(pg_pool, redis_client)

    # Start maintenance loop
    asyncio.create_task(maintenance_loop(pg_pool, redis_client))

    # Start task completion listener
    asyncio.create_task(listen_for_task_completions(pg_pool, redis_client))

    # Start orchestrator loop
    asyncio.create_task(orchestrator_loop(pg_pool, redis_client))

    logger.info("Hive Core orchestrator started")

    # Keep running
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await redis_client.close()
        await pg_pool.close()

if __name__ == "__main__":
    asyncio.run(main())
