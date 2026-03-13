import os
import asyncio
import asyncpg
import redis.asyncio as redis
import logging
import json
from datetime import datetime, timedelta
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")

# Redis settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# PostgreSQL settings
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_USER = os.getenv("POSTGRES_USER", "hivebot")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "hivebot")
POSTGRES_DB = os.getenv("POSTGRES_DB", "hivebot_test")

POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

AUTO_ASSIGN = os.getenv("SCHEDULER_AUTO_ASSIGN", "false").lower() == "true"
ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"
TASK_TIMEOUT_SECONDS = int(os.getenv("TASK_TIMEOUT_SECONDS", 300))  # 5 minutes default

async def health_check(request):
    return web.json_response({"status": "ok", "service": "scheduler"})

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
                    task_data = json.loads(row['data'])
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
                task_data = json.loads(row['data'])
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
                        agent_data = json.loads(agent_row['data'])
                        agent_data['status'] = 'ERROR'
                        await conn.execute(
                            "UPDATE agents SET data = $1 WHERE id = $2",
                            json.dumps(agent_data), agent_id
                        )

async def assignment_loop(pg_pool, redis_client):
    """Main assignment loop – matches pending tasks to idle agents."""
    while True:
        # Get highest priority pending task
        tasks = await redis_client.zrange("tasks:pending", 0, 0, withscores=True)
        if not tasks:
            await asyncio.sleep(1)
            continue
        task_id, score = tasks[0]

        # Fetch task from DB
        async with pg_pool.acquire() as conn:
            task_row = await conn.fetchrow("SELECT data FROM tasks WHERE id = $1", task_id)
            if not task_row:
                await redis_client.zrem("tasks:pending", task_id)
                continue
            task_data = json.loads(task_row['data'])
            if task_data['status'] != 'pending':
                await redis_client.zrem("tasks:pending", task_id)
                continue
            required_skills = task_data.get('required_skills', [])

            # Get idle agent ids
            idle_agent_ids = await redis_client.smembers("agents:idle")
            if not idle_agent_ids:
                await asyncio.sleep(1)
                continue

            # Fetch all idle agents' data in one query
            agents_rows = await conn.fetch(
                "SELECT id, data FROM agents WHERE id = ANY($1)",
                list(idle_agent_ids)
            )
            matching_agent = None
            for agent_row in agents_rows:
                agent_id = agent_row['id']
                agent_data = json.loads(agent_row['data'])
                agent_skills = [s['skillId'] for s in agent_data.get('skills', [])]
                if set(required_skills).issubset(set(agent_skills)):
                    matching_agent = agent_id
                    break

            if not matching_agent:
                await asyncio.sleep(1)
                continue

            # Assign task
            task_data['status'] = 'assigned'
            task_data['assigned_agent_id'] = matching_agent
            task_data['started_at'] = datetime.utcnow().isoformat()
            await conn.execute(
                "UPDATE tasks SET data = $1 WHERE id = $2",
                json.dumps(task_data), task_id
            )

            # Update agent status in DB
            agent_data = await conn.fetchval("SELECT data FROM agents WHERE id = $1", matching_agent)
            agent_data = json.loads(agent_data)
            agent_data['status'] = 'ASSIGNED'
            await conn.execute(
                "UPDATE agents SET data = $1 WHERE id = $2",
                json.dumps(agent_data), matching_agent
            )

            # Remove from Redis queues
            await redis_client.zrem("tasks:pending", task_id)
            await redis_client.srem("agents:idle", matching_agent)

            # Notify agent
            await redis_client.publish(
                f"agent:{matching_agent}",
                json.dumps({
                    'type': 'task_assign',
                    'task_id': task_id,
                    'description': task_data['description'],
                    'input_data': task_data.get('input_data', {}),
                    'goal_id': task_data.get('goal_id'),
                    'hive_id': task_data.get('hive_id')
                })
            )
            logger.info(f"Assigned task {task_id} to agent {matching_agent}")

async def main():
    if not ENABLED:
        logger.info("Scheduler disabled, exiting.")
        return

    pg_pool = await asyncpg.create_pool(POSTGRES_DSN)
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)

    # Start health server
    asyncio.create_task(start_health_server())

    # Initial population
    await populate_pending_tasks(pg_pool, redis_client)
    await populate_idle_agents(pg_pool, redis_client)

    # Start maintenance loop
    asyncio.create_task(maintenance_loop(pg_pool, redis_client))

    if AUTO_ASSIGN:
        logger.info("Auto-assign enabled, starting assignment loop")
        asyncio.create_task(assignment_loop(pg_pool, redis_client))
    else:
        logger.info("Auto-assign disabled, scheduler running in maintenance mode")

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
