#!/usr/bin/env python3
"""
Add 'type' column to layers table if not exists.
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
        # Check if column exists
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'layers' AND column_name = 'type'
            )
        """)
        if not result:
            await conn.execute("""
                ALTER TABLE layers ADD COLUMN type VARCHAR DEFAULT 'contrib'
            """)
            print("Added 'type' column to layers table.")
        else:
            print("Column 'type' already exists.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
