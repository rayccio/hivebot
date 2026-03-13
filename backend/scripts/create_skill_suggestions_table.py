#!/usr/bin/env python3
"""
Create the skill_suggestions table if it does not exist.
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
        # Check if table exists
        result = await conn.fetchrow("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'skill_suggestions'
            )
        """)
        if result[0]:
            print("Table 'skill_suggestions' already exists.")
            return

        # Create table
        await conn.execute("""
            CREATE TABLE skill_suggestions (
                id VARCHAR PRIMARY KEY,
                skill_name VARCHAR NOT NULL,
                goal_id VARCHAR NOT NULL,
                goal_description TEXT NOT NULL,
                task_id VARCHAR NOT NULL,
                task_description TEXT NOT NULL,
                suggested_by VARCHAR,
                resolved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                resolved_at TIMESTAMPTZ
            )
        """)
        print("Table 'skill_suggestions' created successfully.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
