#!/usr/bin/env python3
"""
Add custom_planner_class column to planner_templates.
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
            ALTER TABLE planner_templates ADD COLUMN IF NOT EXISTS custom_planner_class VARCHAR
        """)
        print("Added custom_planner_class column to planner_templates")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
