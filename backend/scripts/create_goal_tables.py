#!/usr/bin/env python3
"""
Create the goals, task_edges, and artifacts tables.
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
        # Create goals table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id VARCHAR PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("Table 'goals' ensured.")

        # Create task_edges table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS task_edges (
                from_task VARCHAR NOT NULL,
                to_task VARCHAR NOT NULL,
                PRIMARY KEY (from_task, to_task)
            )
        """)
        print("Table 'task_edges' ensured.")

        # Create artifacts table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id VARCHAR PRIMARY KEY,
                goal_id VARCHAR NOT NULL,
                task_id VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                content TEXT,
                version INT DEFAULT 1,
                status VARCHAR DEFAULT 'draft',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("Table 'artifacts' ensured.")

        # Add agent_type column to tasks if not exists
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='tasks' AND column_name='agent_type'
                ) THEN
                    ALTER TABLE tasks ADD COLUMN agent_type VARCHAR;
                END IF;
            END
            $$;
        """)
        print("Checked/added agent_type column.")

        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='tasks' AND column_name='retries'
                ) THEN
                    ALTER TABLE tasks ADD COLUMN retries INT DEFAULT 0;
                END IF;
            END
            $$;
        """)
        print("Checked/added retries column.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
