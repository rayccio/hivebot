#!/usr/bin/env python3
"""
Seed the core layer with default roles, skills, and other data.
Run after create_layer_tables.py.
"""

import asyncio
import asyncpg
import os
import sys
import uuid
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings
from app.constants import (
    BUILDER_SOUL, BUILDER_IDENTITY, BUILDER_TOOLS,
    TESTER_SOUL, TESTER_IDENTITY, TESTER_TOOLS,
    REVIEWER_SOUL, REVIEWER_IDENTITY, REVIEWER_TOOLS,
    FIXER_SOUL, FIXER_IDENTITY, FIXER_TOOLS,
    ARCHITECT_SOUL, ARCHITECT_IDENTITY, ARCHITECT_TOOLS,
    RESEARCHER_SOUL, RESEARCHER_IDENTITY, RESEARCHER_TOOLS,
    INITIAL_SOUL, INITIAL_IDENTITY, INITIAL_TOOLS
)

DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}/{settings.POSTGRES_DB}"

async def migrate():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Insert core layer
        core_layer_id = "core"
        now = datetime.utcnow()
        await conn.execute("""
            INSERT INTO layers (id, name, description, version, author, enabled, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (id) DO NOTHING
        """, core_layer_id, "HiveBot Core", "Core system roles and skills", "1.0.0", "system", True, now, now)
        print("Core layer inserted.")

        # Insert core roles
        roles = [
            ("builder", BUILDER_SOUL, BUILDER_IDENTITY, BUILDER_TOOLS, "core"),
            ("tester", TESTER_SOUL, TESTER_IDENTITY, TESTER_TOOLS, "core"),
            ("reviewer", REVIEWER_SOUL, REVIEWER_IDENTITY, REVIEWER_TOOLS, "core"),
            ("fixer", FIXER_SOUL, FIXER_IDENTITY, FIXER_TOOLS, "core"),
            ("architect", ARCHITECT_SOUL, ARCHITECT_IDENTITY, ARCHITECT_TOOLS, "core"),
            ("researcher", RESEARCHER_SOUL, RESEARCHER_IDENTITY, RESEARCHER_TOOLS, "core"),
            ("generic", INITIAL_SOUL, INITIAL_IDENTITY, INITIAL_TOOLS, "core"),
        ]
        for role_name, soul, identity, tools, role_type in roles:
            await conn.execute("""
                INSERT INTO layer_roles (layer_id, role_name, soul_md, identity_md, tools_md, role_type)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (layer_id, role_name) DO NOTHING
            """, core_layer_id, role_name, soul, identity, tools, role_type)
        print("Core roles inserted.")

        # Insert core skills (existing tools) into skills table
        # First, check if skills already exist
        core_skills = [
            ("web_search", "Search the web using a search engine", "tool"),
            ("ssh_execute", "Execute a command on a remote server via SSH", "tool"),
            ("browser_action", "Perform browser automation (goto, click, type, screenshot)", "tool"),
            ("run_code", "Execute code in an isolated container", "tool"),
            ("api_call", "Make an HTTP request to an external API", "tool"),
        ]
        for skill_name, skill_desc, skill_type in core_skills:
            # Insert skill if not exists
            skill_id = f"sk-{uuid.uuid4().hex[:8]}"
            # Check if skill already exists by name
            existing = await conn.fetchval("SELECT id FROM skills WHERE data->>'name' = $1", skill_name)
            if existing:
                print(f"Skill {skill_name} already exists, skipping.")
                continue
            skill_data = {
                "id": skill_id,
                "name": skill_name,
                "description": skill_desc,
                "type": skill_type,
                "visibility": "public",
                "author_id": "system",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "tags": [],
                "metadata": {}
            }
            await conn.execute(
                "INSERT INTO skills (id, data) VALUES ($1, $2)",
                skill_id, asyncpg.types.json.dumps(skill_data)
            )
            # Link to core layer
            await conn.execute(
                "INSERT INTO layer_skills (layer_id, skill_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                core_layer_id, skill_id
            )
            print(f"Skill {skill_name} inserted.")
        print("Core skills inserted.")

        # Insert a default lifecycle for core layer
        lifecycle = {
            "states": ["draft", "built", "tested", "final"],
            "transitions": {
                "draft": ["built"],
                "built": ["tested"],
                "tested": ["final"],
            }
        }
        await conn.execute("UPDATE layers SET lifecycle = $1 WHERE id = $2", asyncpg.types.json.dumps(lifecycle), core_layer_id)
        print("Default lifecycle set.")

        # Insert a default loop handler (generic)
        loop_id = "default_loop"
        await conn.execute("""
            INSERT INTO loop_handlers (id, layer_id, name, class_path)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO NOTHING
        """, loop_id, core_layer_id, "default", "worker.loop_handler.DefaultLoopHandler")
        print("Default loop handler registered.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
