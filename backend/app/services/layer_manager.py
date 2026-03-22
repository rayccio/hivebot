import os
import json
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.config import settings
from ..core.database import AsyncSessionLocal
from ..models.types import Layer, LayerRole, LayerSkill
import logging

logger = logging.getLogger(__name__)

class LayerManager:
    """Manages installation, enabling/disabling, and configuration of layers."""

    LAYERS_DIR = Path("/app/layers")  # host directory mounted in docker-compose

    def __init__(self):
        self.LAYERS_DIR.mkdir(parents=True, exist_ok=True)

    async def install_layer(self, git_url: str, version: Optional[str] = None) -> str:
        """Clone a layer repository, parse its manifest, and insert into DB."""
        layer_name = git_url.split('/')[-1].replace('.git', '')
        layer_dir = self.LAYERS_DIR / layer_name
        if layer_dir.exists():
            shutil.rmtree(layer_dir)

        # Clone the repository
        cmd = ["git", "clone", git_url, str(layer_dir)]
        if version:
            cmd += ["--branch", version]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Git clone failed: {result.stderr}")

        # Read manifest
        manifest_path = layer_dir / "manifest.json"
        if not manifest_path.exists():
            raise Exception("manifest.json not found in layer")
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        # Validate required fields
        required = ["name", "version", "description"]
        for field in required:
            if field not in manifest:
                raise Exception(f"manifest.json missing required field: {field}")

        layer_id = f"layer-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()

        # Insert into layers table
        async with AsyncSessionLocal() as session:
            # Insert layer
            await session.execute(
                text("""
                    INSERT INTO layers (id, name, description, version, author, dependencies, enabled, created_at, updated_at)
                    VALUES (:id, :name, :description, :version, :author, :dependencies, :enabled, :created_at, :updated_at)
                """),
                {
                    "id": layer_id,
                    "name": manifest["name"],
                    "description": manifest.get("description", ""),
                    "version": manifest["version"],
                    "author": manifest.get("author"),
                    "dependencies": json.dumps(manifest.get("dependencies", [])),
                    "enabled": False,  # disabled by default
                    "created_at": now,
                    "updated_at": now
                }
            )

            # Insert roles
            roles = manifest.get("roles", [])
            for role_name in roles:
                role_dir = layer_dir / "roles" / role_name
                soul_md = (role_dir / "soul.md").read_text(encoding="utf-8") if (role_dir / "soul.md").exists() else ""
                identity_md = (role_dir / "identity.md").read_text(encoding="utf-8") if (role_dir / "identity.md").exists() else ""
                tools_md = (role_dir / "tools.md").read_text(encoding="utf-8") if (role_dir / "tools.md").exists() else ""
                await session.execute(
                    text("""
                        INSERT INTO layer_roles (layer_id, role_name, soul_md, identity_md, tools_md, role_type)
                        VALUES (:layer_id, :role_name, :soul_md, :identity_md, :tools_md, 'specialized')
                    """),
                    {
                        "layer_id": layer_id,
                        "role_name": role_name,
                        "soul_md": soul_md,
                        "identity_md": identity_md,
                        "tools_md": tools_md
                    }
                )

            # Insert skills
            skills = manifest.get("skills", [])
            for skill_name in skills:
                # Check if skill already exists (by name)
                result = await session.execute(
                    text("SELECT id FROM skills WHERE data->>'name' = :name"),
                    {"name": skill_name}
                )
                row = result.fetchone()
                if row:
                    skill_id = row[0]
                else:
                    skill_id = f"sk-{uuid.uuid4().hex[:8]}"
                    skill_data = {
                        "id": skill_id,
                        "name": skill_name,
                        "description": f"Skill from layer {manifest['name']}",
                        "type": "tool",
                        "visibility": "public",
                        "author_id": "layer",
                        "created_at": now.isoformat(),
                        "updated_at": now.isoformat(),
                        "tags": [],
                        "metadata": {}
                    }
                    await session.execute(
                        text("INSERT INTO skills (id, data) VALUES (:id, :data)"),
                        {"id": skill_id, "data": json.dumps(skill_data)}
                    )
                # Link skill to layer
                await session.execute(
                    text("INSERT INTO layer_skills (layer_id, skill_id) VALUES (:layer_id, :skill_id) ON CONFLICT DO NOTHING"),
                    {"layer_id": layer_id, "skill_id": skill_id}
                )

            # Insert planner templates (including custom planners)
            await self._register_custom_planner(session, layer_id, layer_dir, manifest)

            # Insert loop handler if exists
            loop_file = layer_dir / "loop.py"
            if loop_file.exists():
                loop_handler_id = f"lh-{uuid.uuid4().hex[:8]}"
                await session.execute(
                    text("""
                        INSERT INTO loop_handlers (id, layer_id, name, class_path)
                        VALUES (:id, :layer_id, :name, :class_path)
                    """),
                    {
                        "id": loop_handler_id,
                        "layer_id": layer_id,
                        "name": f"{manifest['name']}_loop",
                        "class_path": f"layers.{layer_name}.loop.LoopHandler"  # placeholder; actual import path depends on layout
                    }
                )

            # Store lifecycle if exists
            lifecycle_file = layer_dir / "lifecycle.json"
            if lifecycle_file.exists():
                lifecycle = json.loads(lifecycle_file.read_text())
                await session.execute(
                    text("UPDATE layers SET lifecycle = :lifecycle WHERE id = :id"),
                    {"lifecycle": json.dumps(lifecycle), "id": layer_id}
                )

            # Store config schema (optional)
            config_schema_file = layer_dir / "config" / "settings.json"
            if config_schema_file.exists():
                config_schema = json.loads(config_schema_file.read_text())
                # We can store this in layer_configs table later when a user configures it.
                # For now, just log.
                logger.info(f"Config schema found for layer {layer_id}")

            await session.commit()

        logger.info(f"Layer {layer_id} installed from {git_url}")
        return layer_id

    async def _register_custom_planner(self, session, layer_id: str, layer_dir: Path, manifest: dict):
        """Register a custom planner if present."""
        planner_info = manifest.get("planner")
        if not planner_info:
            return
        class_path = planner_info.get("class")
        goal_pattern = planner_info.get("goal_pattern")
        priority = planner_info.get("priority", 0)
        if not class_path:
            return

        # Build full class path (e.g., layers.coding.planner.CodingPlanner)
        # The layer_dir name is the layer name (from git repo). We need to know the package name.
        # The layer is installed under /app/layers/<layer_name>. So the Python module path
        # should be "layers.<layer_name>.planner.CodingPlanner".
        layer_name = layer_dir.name
        full_class_path = f"layers.{layer_name}.{class_path}"
        template_text = planner_info.get("template")  # optional few-shot example

        # Insert a planner template
        template_id = f"pt-{uuid.uuid4().hex[:8]}"
        await session.execute(
            text("""
                INSERT INTO planner_templates (id, layer_id, goal_pattern, template, custom_planner_class, priority)
                VALUES (:id, :layer_id, :goal_pattern, :template, :custom_planner_class, :priority)
            """),
            {
                "id": template_id,
                "layer_id": layer_id,
                "goal_pattern": goal_pattern,
                "template": template_text,
                "custom_planner_class": full_class_path,
                "priority": priority
            }
        )
        logger.info(f"Registered custom planner for layer {layer_id}: {full_class_path}")

    async def enable_layer(self, layer_id: str) -> bool:
        """Enable a layer (set enabled=True). Also check dependencies."""
        async with AsyncSessionLocal() as session:
            # Check if layer exists
            row = await session.execute(
                text("SELECT dependencies FROM layers WHERE id = :id"),
                {"id": layer_id}
            )
            result = row.fetchone()
            if not result:
                return False
            deps = result[0] or []
            # Ensure all dependencies are installed and enabled
            for dep in deps:
                dep_row = await session.execute(
                    text("SELECT enabled FROM layers WHERE name = :name"),
                    {"name": dep}
                )
                dep_enabled = dep_row.scalar()
                if not dep_enabled:
                    raise Exception(f"Dependency layer {dep} is not enabled")
            # Enable the layer
            await session.execute(
                text("UPDATE layers SET enabled = TRUE WHERE id = :id"),
                {"id": layer_id}
            )
            await session.commit()
        return True

    async def disable_layer(self, layer_id: str) -> bool:
        """Disable a layer (set enabled=False)."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("UPDATE layers SET enabled = FALSE WHERE id = :id AND id != 'core' RETURNING id"),
                {"id": layer_id}
            )
            await session.commit()
            return result.rowcount > 0

    async def configure_layer(self, layer_id: str, hive_id: str, config: Dict[str, Any]) -> bool:
        """Save configuration for a layer in a specific hive."""
        config_id = f"lc-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            # Check if config already exists for this (layer, hive)
            row = await session.execute(
                text("SELECT id FROM layer_configs WHERE layer_id = :layer_id AND hive_id = :hive_id"),
                {"layer_id": layer_id, "hive_id": hive_id}
            )
            existing = row.fetchone()
            if existing:
                # Update existing
                await session.execute(
                    text("UPDATE layer_configs SET config_data = :config, updated_at = :updated_at WHERE id = :id"),
                    {"config": json.dumps(config), "updated_at": now, "id": existing[0]}
                )
            else:
                # Insert new
                await session.execute(
                    text("""
                        INSERT INTO layer_configs (id, layer_id, hive_id, config_data, created_at, updated_at)
                        VALUES (:id, :layer_id, :hive_id, :config, :created_at, :updated_at)
                    """),
                    {
                        "id": config_id,
                        "layer_id": layer_id,
                        "hive_id": hive_id,
                        "config": json.dumps(config),
                        "created_at": now,
                        "updated_at": now
                    }
                )
            await session.commit()
        return True

    async def get_layer_config(self, layer_id: str, hive_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve configuration for a layer in a hive."""
        async with AsyncSessionLocal() as session:
            row = await session.execute(
                text("SELECT config_data FROM layer_configs WHERE layer_id = :layer_id AND hive_id = :hive_id"),
                {"layer_id": layer_id, "hive_id": hive_id}
            )
            result = row.fetchone()
            if result:
                return json.loads(result[0])
        return None

    async def get_layer_config_schema(self, layer_id: str) -> Optional[Dict[str, Any]]:
        """Return the config schema from the layer's settings.json."""
        # We need to know the layer's name to find its directory.
        async with AsyncSessionLocal() as session:
            row = await session.execute(
                text("SELECT name FROM layers WHERE id = :id"),
                {"id": layer_id}
            )
            layer_name = row.scalar()
            if not layer_name:
                return None
        layer_dir = self.LAYERS_DIR / layer_name
        config_schema_file = layer_dir / "config" / "settings.json"
        if config_schema_file.exists():
            with open(config_schema_file, "r") as f:
                return json.load(f)
        return None

    async def list_loop_handlers(self, layer_id: str) -> List[Dict[str, Any]]:
        """Return loop handlers registered for a layer."""
        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                text("SELECT id, name, class_path FROM loop_handlers WHERE layer_id = :layer_id"),
                {"layer_id": layer_id}
            )
            return [{"id": r[0], "name": r[1], "class_path": r[2]} for r in rows.fetchall()]
