#!/usr/bin/env python3
"""
Migrate existing hives to include the 'agentIds' field.
Run this once after updating the codebase.
"""

import asyncio
import json
import asyncpg
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings

DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}/{settings.POSTGRES_DB}"

async def migrate():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Fetch all hives
        rows = await conn.fetch("SELECT id, data FROM hives")
        for row in rows:
            hive_id = row['id']
            data = row['data']
            if isinstance(data, str):
                data = json.loads(data)
            # Check if 'agentIds' already exists
            if 'agentIds' in data:
                print(f"Hive {hive_id} already has agentIds, skipping.")
                continue
            # If there is an 'agents' array, extract IDs; else empty list
            agent_ids = []
            if 'agents' in data and isinstance(data['agents'], list):
                agent_ids = [a.get('id') for a in data['agents'] if a.get('id')]
            data['agentIds'] = agent_ids
            # Optionally remove the old 'agents' field to save space (not required)
            # data.pop('agents', None)
            await conn.execute(
                "UPDATE hives SET data = $1 WHERE id = $2",
                json.dumps(data), hive_id
            )
            print(f"Updated hive {hive_id} with agentIds: {agent_ids}")
        print("Migration complete.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
