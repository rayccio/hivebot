#!/usr/bin/env python3
"""
Create the execution_logs table.
Run this after updating the codebase.
"""

import asyncio
import asyncpg
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings

DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}/{settings.POSTGRES_DB}"

async def migrate():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id VARCHAR PRIMARY KEY,
                goal_id VARCHAR NOT NULL,
                task_id VARCHAR,
                agent_id VARCHAR,
                level VARCHAR NOT NULL,
                message TEXT NOT NULL,
                iteration INT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("Table 'execution_logs' ensured.")
        # Create index on goal_id for fast retrieval
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_logs_goal_id ON execution_logs(goal_id)")
        print("Index on goal_id created.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
