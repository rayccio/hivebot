import logging
import json
import re
import uuid
import importlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from ..core.database import AsyncSessionLocal
from ..services.litellm_service import generate_with_messages
from ..core.config import settings
from ..models.types import HiveTask, HiveTaskStatus

logger = logging.getLogger(__name__)

class Planner:
    async def _get_enabled_layers(self):
        """Fetch only enabled layers (core is always considered enabled)."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT id, name FROM layers WHERE enabled = TRUE OR id = 'core'")
            )
            return result.fetchall()

    async def _get_layer_roles(self, layer_ids: List[str]):
        if not layer_ids:
            return []
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT role_name FROM layer_roles WHERE layer_id = ANY(:ids)"),
                {"ids": layer_ids}
            )
            rows = result.fetchall()
            return [row[0] for row in rows]

    async def _get_layer_skills(self, layer_ids: List[str]):
        if not layer_ids:
            return []
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT s.id, s.data->>'name' as name, s.data->>'description' as description
                    FROM skills s
                    JOIN layer_skills ls ON s.id = ls.skill_id
                    WHERE ls.layer_id = ANY(:ids)
                """),
                {"ids": layer_ids}
            )
            rows = result.fetchall()
            return [{"id": r[0], "name": r[1], "description": r[2]} for r in rows]

    async def _get_matching_templates(self, goal_text: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT pt.goal_pattern, pt.template, pt.custom_planner_class, pt.priority, l.id as layer_id
                    FROM planner_templates pt
                    JOIN layers l ON pt.layer_id = l.id
                    WHERE l.enabled = TRUE OR l.id = 'core'
                    ORDER BY pt.priority DESC
                """)
            )
            templates = result.fetchall()
            matches = []
            for pattern, template, custom_class, priority, layer_id in templates:
                if pattern and re.search(pattern, goal_text, re.IGNORECASE):
                    matches.append({
                        "template": template,
                        "custom_planner_class": custom_class,
                        "priority": priority,
                        "layer_id": layer_id
                    })
            return matches

    async def plan(
        self,
        goal_id: str,
        hive_id: str,
        goal_text: str,
        hive_context: Optional[str] = None,
        skills: Optional[List[Dict]] = None,
        project_id: Optional[str] = None,
        layer_id: Optional[str] = "core"
    ) -> List[HiveTask]:
        """
        Decompose goal into tasks and dependencies, store them in DB, and return the list.
        """
        # Get enabled layers
        layers = await self._get_enabled_layers()
        layer_ids = [l[0] for l in layers]
        layer_names = {l[0]: l[1] for l in layers}

        # Get roles and skills from layers
        roles = await self._get_layer_roles(layer_ids)
        layer_skills = await self._get_layer_skills(layer_ids)

        # Combine passed skills with layer skills
        all_skills = skills or []
        all_skills.extend(layer_skills)
        # Remove duplicates by id
        seen = set()
        unique_skills = []
        for s in all_skills:
            if s["id"] not in seen:
                seen.add(s["id"])
                unique_skills.append(s)
        all_skills = unique_skills

        # Build skill map for name -> id
        skill_map = {s["name"].lower(): s["id"] for s in all_skills}

        # Build system prompt
        roles_text = "\n".join([f"- {role}" for role in roles]) if roles else "No specific roles defined."
        skills_text = "\n".join([f"- {s['name']}: {s['description']}" for s in all_skills]) if all_skills else "No skills available."

        # Fetch matching templates
        templates = await self._get_matching_templates(goal_text)

        # Check for custom planner
        custom_planner_class = None
        for tmpl in templates:
            if tmpl["custom_planner_class"]:
                custom_planner_class = tmpl["custom_planner_class"]
                break  # highest priority first

        if custom_planner_class:
            logger.info(f"Using custom planner: {custom_planner_class}")
            try:
                module_name, class_name = custom_planner_class.rsplit(".", 1)
                module = importlib.import_module(module_name)
                planner_cls = getattr(module, class_name)
                planner_instance = planner_cls()
                tasks = await planner_instance.plan(
                    goal_text=goal_text,
                    hive_context=hive_context,
                    skills=all_skills,
                    roles=roles
                )
                # Convert to HiveTask objects if necessary (assume already HiveTask)
                # Store tasks in DB
                async with AsyncSessionLocal() as session:
                    for task in tasks:
                        task.goal_id = goal_id
                        task.hive_id = hive_id
                        task.project_id = project_id
                        task.layer_id = layer_id  # set layer_id
                        await session.execute(
                            text("INSERT INTO tasks (id, data) VALUES (:id, :data)"),
                            {"id": task.id, "data": task.model_dump_json()}
                        )
                    await session.commit()
                return tasks
            except Exception as e:
                logger.error(f"Custom planner failed: {e}, falling back to LLM")

        # Fallback to LLM planning
        system_prompt = f"""You are an AI task planner for a multi-agent system. Your job is to break down a user's goal into a set of discrete tasks that can be executed by autonomous agents (bots). Each task should be self‑contained and have clear inputs and outputs. Also identify dependencies between tasks.

Available agent roles:
{roles_text}

Available skills:
{skills_text}

When listing required skills for a task, use the exact skill names from the list above. If a task requires a skill not in the list, you may invent a new skill name, but it will be less likely to be matched.

For each task, also assign an `agent_type` from the following list:
- "builder" – writes code or creates files
- "tester" – runs tests and reports results
- "reviewer" – analyzes code for issues
- "fixer" – applies patches
- "researcher" – gathers information
- "architect" – designs structure

Respond in JSON format with the following structure:
{{
  "tasks": [
    {{
      "id": "task_1",  // Use simple IDs like task_1, task_2, etc.
      "description": "Describe what the agent should do",
      "agent_type": "builder",
      "depends_on": [],  // List of task IDs that must complete before this one
      "required_skills": ["skill_name1", "skill_name2"] // List of skill names needed
    }},
    ...
  ],
  "reasoning": "Brief explanation of the decomposition."
}}

Do not include any other text outside the JSON.
"""

        # Add templates as few-shot examples
        if templates:
            system_prompt += "\n\nHere are some examples of how to decompose similar goals:\n"
            for tmpl in templates:
                if tmpl["template"]:
                    system_prompt += f"- {tmpl['template']}\n"

        user_prompt = f"Goal: {goal_text}\n\n"
        if hive_context:
            user_prompt += f"Hive context: {hive_context}\n\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Get primary model from provider config
        provider_config = settings.secrets.get("PROVIDER_CONFIG", {})
        primary_model_id = None
        for pkey, pconf in provider_config.get("providers", {}).items():
            for mid, mconf in pconf.get("models", {}).items():
                if mconf.get("is_primary") and mconf.get("enabled"):
                    primary_model_id = f"{pkey}/{mid}"
                    break
            if primary_model_id:
                break

        if not primary_model_id:
            raise RuntimeError("No primary AI model configured for planning")

        config = {"model": primary_model_id, "temperature": 0.2, "max_tokens": 1500}
        try:
            response = await generate_with_messages(messages, config)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in planner response")
            plan = json.loads(json_match.group())
            tasks_dict = plan.get("tasks", [])
            if not tasks_dict:
                raise ValueError("No tasks in planner response")
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            tasks_dict = [{
                "id": "task_1",
                "description": goal_text,
                "agent_type": "builder",
                "depends_on": [],
                "required_skills": []
            }]

        # Convert skill names to IDs
        for t in tasks_dict:
            skill_names = t.get("required_skills", [])
            skill_ids = []
            for name in skill_names:
                sid = skill_map.get(name.lower())
                if sid:
                    skill_ids.append(sid)
                else:
                    skill_ids.append(name)  # keep as placeholder
            t["required_skills"] = skill_ids

        # Convert to HiveTask objects and store in DB
        tasks = []
        task_id_map = {}
        async with AsyncSessionLocal() as session:
            for t in tasks_dict:
                real_id = f"t-{uuid.uuid4().hex[:8]}"
                task_id_map[t["id"]] = real_id
                task = HiveTask(
                    id=real_id,
                    goal_id=goal_id,
                    hive_id=hive_id,
                    description=t["description"],
                    agent_type=t.get("agent_type", "builder"),
                    status=HiveTaskStatus.PENDING,
                    depends_on=[],  # will fill after all created
                    required_skills=t.get("required_skills", []),
                    created_at=datetime.utcnow(),
                    project_id=project_id,
                    layer_id=layer_id  # <-- new
                )
                tasks.append(task)
                await session.execute(
                    text("INSERT INTO tasks (id, data) VALUES (:id, :data)"),
                    {"id": real_id, "data": task.model_dump_json()}
                )

            for i, t in enumerate(tasks_dict):
                real_deps = [task_id_map[dep] for dep in t.get("depends_on", []) if dep in task_id_map]
                tasks[i].depends_on = real_deps
                await session.execute(
                    text("UPDATE tasks SET data = :data WHERE id = :id"),
                    {"id": tasks[i].id, "data": tasks[i].model_dump_json()}
                )

            for from_task, to_task in [(dep, task_id_map[t["id"]]) for t in tasks_dict for dep in t.get("depends_on", []) if dep in task_id_map]:
                await session.execute(
                    text("INSERT INTO task_edges (from_task, to_task) VALUES (:from, :to) ON CONFLICT DO NOTHING"),
                    {"from": from_task, "to": to_task}
                )

            await session.commit()

        logger.info(f"Planner created {len(tasks)} tasks for goal {goal_id}")
        return tasks
