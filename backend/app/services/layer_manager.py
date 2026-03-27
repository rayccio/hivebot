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

    LAYERS_DIR = settings.LAYERS_DIR

    def __init__(self):
        self.LAYERS_DIR.mkdir(parents=True, exist_ok=True)

    # ========== Existing methods (install_layer, enable_layer, disable_layer, etc.) remain unchanged ==========

    async def _install_from_local(self, layer_dir: Path, layer_id: str, is_core: bool = True) -> str:
        """
        Install a layer from a local directory (used for core layers).
        This method inserts/updates the layer record and all its components.
        """
        manifest_path = layer_dir / "manifest.json"
        if not manifest_path.exists():
            raise Exception(f"manifest.json not found in {layer_dir}")

        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        required = ["name", "version", "description"]
        for field in required:
            if field not in manifest:
                raise Exception(f"manifest.json missing required field: {field}")

        now = datetime.utcnow()

        async with AsyncSessionLocal() as session:
            # Check if layer already exists
            result = await session.execute(
                text("SELECT id, version FROM layers WHERE id = :id"),
                {"id": layer_id}
            )
            row = result.fetchone()

            if row:
                existing_version = row[1]
                if existing_version == manifest["version"]:
                    logger.info(f"Layer {layer_id} already at version {manifest['version']}, skipping.")
                    return layer_id
                # Update existing
                await session.execute(
                    text("""
                        UPDATE layers SET
                            name = :name,
                            description = :description,
                            version = :version,
                            author = :author,
                            dependencies = :dependencies,
                            enabled = :enabled,
                            type = :type,
                            updated_at = :updated_at
                        WHERE id = :id
                    """),
                    {
                        "id": layer_id,
                        "name": manifest["name"],
                        "description": manifest.get("description", ""),
                        "version": manifest["version"],
                        "author": manifest.get("author"),
                        "dependencies": json.dumps(manifest.get("dependencies", [])),
                        "enabled": True,
                        "type": "core" if is_core else "contrib",
                        "updated_at": now,
                    }
                )
                # Delete existing components for this layer (clean slate)
                await session.execute(
                    text("DELETE FROM layer_roles WHERE layer_id = :layer_id"),
                    {"layer_id": layer_id}
                )
                await session.execute(
                    text("DELETE FROM planner_templates WHERE layer_id = :layer_id"),
                    {"layer_id": layer_id}
                )
                await session.execute(
                    text("DELETE FROM loop_handlers WHERE layer_id = :layer_id"),
                    {"layer_id": layer_id}
                )
                # Do NOT delete layer_skills – they are just links; we'll re‑add them
            else:
                # Insert new
                await session.execute(
                    text("""
                        INSERT INTO layers (id, name, description, version, author, dependencies, enabled, type, created_at, updated_at)
                        VALUES (:id, :name, :description, :version, :author, :dependencies, :enabled, :type, :created_at, :updated_at)
                    """),
                    {
                        "id": layer_id,
                        "name": manifest["name"],
                        "description": manifest.get("description", ""),
                        "version": manifest["version"],
                        "author": manifest.get("author"),
                        "dependencies": json.dumps(manifest.get("dependencies", [])),
                        "enabled": True,
                        "type": "core" if is_core else "contrib",
                        "created_at": now,
                        "updated_at": now,
                    }
                )

            # ----- Roles -----
            roles_dir = layer_dir / "roles"
            if roles_dir.exists():
                for role_name_dir in roles_dir.iterdir():
                    if role_name_dir.is_dir():
                        role_name = role_name_dir.name
                        soul_md = (role_name_dir / "soul.md").read_text(encoding="utf-8") if (role_name_dir / "soul.md").exists() else ""
                        identity_md = (role_name_dir / "identity.md").read_text(encoding="utf-8") if (role_name_dir / "identity.md").exists() else ""
                        tools_md = (role_name_dir / "tools.md").read_text(encoding="utf-8") if (role_name_dir / "tools.md").exists() else ""
                        await session.execute(
                            text("""
                                INSERT INTO layer_roles (layer_id, role_name, soul_md, identity_md, tools_md, role_type)
                                VALUES (:layer_id, :role_name, :soul_md, :identity_md, :tools_md, 'specialized')
                                ON CONFLICT (layer_id, role_name) DO UPDATE SET
                                    soul_md = EXCLUDED.soul_md,
                                    identity_md = EXCLUDED.identity_md,
                                    tools_md = EXCLUDED.tools_md
                            """),
                            {
                                "layer_id": layer_id,
                                "role_name": role_name,
                                "soul_md": soul_md,
                                "identity_md": identity_md,
                                "tools_md": tools_md,
                            }
                        )

            # ----- Skills -----
            skills_dir = layer_dir / "skills"
            if skills_dir.exists():
                for skill_name_dir in skills_dir.iterdir():
                    if skill_name_dir.is_dir():
                        skill_name = skill_name_dir.name
                        # Check if skill already exists
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

                        # Skill versions
                        versions_dir = skill_name_dir / "versions"
                        if versions_dir.exists():
                            for version_dir in versions_dir.iterdir():
                                if version_dir.is_dir():
                                    version = version_dir.name
                                    code_file = version_dir / "code.py"
                                    if not code_file.exists():
                                        continue
                                    code = code_file.read_text(encoding="utf-8")
                                    requirements_file = version_dir / "requirements.txt"
                                    requirements = requirements_file.read_text(encoding="utf-8").splitlines() if requirements_file.exists() else []
                                    config_schema_file = version_dir / "config_schema.json"
                                    config_schema = json.loads(config_schema_file.read_text()) if config_schema_file.exists() else None

                                    # Insert version if not exists
                                    version_id = f"sv-{uuid.uuid4().hex[:8]}"
                                    version_data = {
                                        "id": version_id,
                                        "skill_id": skill_id,
                                        "version": version,
                                        "code": code,
                                        "language": "python",
                                        "entry_point": "run",
                                        "requirements": requirements,
                                        "config_schema": config_schema,
                                        "created_at": now.isoformat(),
                                        "is_active": True,
                                        "changelog": "Initial version"
                                    }
                                    await session.execute(
                                        text("INSERT INTO skill_versions (id, skill_id, data) VALUES (:id, :skill_id, :data) ON CONFLICT DO NOTHING"),
                                        {"id": version_id, "skill_id": skill_id, "data": json.dumps(version_data)}
                                    )

            # ----- Planner templates -----
            templates_file = layer_dir / "planner" / "templates.json"
            if templates_file.exists():
                templates = json.loads(templates_file.read_text())
                for tmpl in templates:
                    goal_pattern = tmpl.get("goal_pattern")
                    template_text = tmpl.get("template")
                    priority = tmpl.get("priority", 0)
                    template_id = f"pt-{uuid.uuid4().hex[:8]}"
                    await session.execute(
                        text("""
                            INSERT INTO planner_templates (id, layer_id, goal_pattern, template, priority)
                            VALUES (:id, :layer_id, :goal_pattern, :template, :priority)
                            ON CONFLICT (id) DO UPDATE SET
                                goal_pattern = EXCLUDED.goal_pattern,
                                template = EXCLUDED.template,
                                priority = EXCLUDED.priority
                        """),
                        {
                            "id": template_id,
                            "layer_id": layer_id,
                            "goal_pattern": goal_pattern,
                            "template": template_text,
                            "priority": priority
                        }
                    )

            # ----- Custom planner (if any) -----
            planner_info = manifest.get("planner")
            if planner_info and planner_info.get("class"):
                class_path = planner_info["class"]
                goal_pattern = planner_info.get("goal_pattern")
                priority = planner_info.get("priority", 0)
                template_id = f"pt-{uuid.uuid4().hex[:8]}"
                await session.execute(
                    text("""
                        INSERT INTO planner_templates (id, layer_id, goal_pattern, custom_planner_class, priority)
                        VALUES (:id, :layer_id, :goal_pattern, :custom_planner_class, :priority)
                        ON CONFLICT (id) DO UPDATE SET
                            goal_pattern = EXCLUDED.goal_pattern,
                            custom_planner_class = EXCLUDED.custom_planner_class,
                            priority = EXCLUDED.priority
                    """),
                    {
                        "id": template_id,
                        "layer_id": layer_id,
                        "goal_pattern": goal_pattern,
                        "custom_planner_class": class_path,
                        "priority": priority
                    }
                )

            # ----- Loop handler -----
            loop_info = manifest.get("loop_handler")
            if loop_info and loop_info.get("class"):
                loop_name = loop_info.get("name", f"{manifest['name']}_loop")
                class_path = loop_info["class"]
                handler_id = f"lh-{uuid.uuid4().hex[:8]}"
                await session.execute(
                    text("""
                        INSERT INTO loop_handlers (id, layer_id, name, class_path)
                        VALUES (:id, :layer_id, :name, :class_path)
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name,
                            class_path = EXCLUDED.class_path
                    """),
                    {
                        "id": handler_id,
                        "layer_id": layer_id,
                        "name": loop_name,
                        "class_path": class_path
                    }
                )

            # ----- Lifecycle -----
            lifecycle_file = layer_dir / "lifecycle.json"
            if lifecycle_file.exists():
                lifecycle = json.loads(lifecycle_file.read_text())
                await session.execute(
                    text("UPDATE layers SET lifecycle = :lifecycle WHERE id = :id"),
                    {"lifecycle": json.dumps(lifecycle), "id": layer_id}
                )

            await session.commit()

        logger.info(f"Layer {layer_id} installed from local directory {layer_dir}")
        return layer_id

    async def load_core_layers(self):
        """Load all core layers from /app/layers/core directory."""
        core_dir = self.LAYERS_DIR / "core"
        if not core_dir.exists():
            logger.warning(f"Core layers directory {core_dir} does not exist, skipping.")
            return

        for layer_dir in core_dir.iterdir():
            if not layer_dir.is_dir():
                continue
            manifest_path = layer_dir / "manifest.json"
            if not manifest_path.exists():
                logger.warning(f"Skipping {layer_dir.name} – no manifest.json")
                continue
            layer_id = layer_dir.name
            # Skip the main system core layer (id "core") if it ever appears here
            if layer_id == "core":
                continue
            logger.info(f"Loading core layer {layer_id} from {layer_dir}")
            try:
                await self._install_from_local(layer_dir, layer_id, is_core=True)
            except Exception as e:
                logger.error(f"Failed to load core layer {layer_id}: {e}")
