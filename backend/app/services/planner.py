# backend/app/services/planner.py
import logging
import json
import re
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from ..core.database import AsyncSessionLocal
from ..services.litellm_service import generate_with_messages
from ..core.config import settings
from ..models.types import HiveTask, HiveTaskStatus

logger = logging.getLogger(__name__)

class Planner:
    def __init__(self):
        self.model = None  # Will be determined dynamically

    async def plan(self, goal_id: str, goal_text: str, hive_context: Optional[str] = None, skills: Optional[List[Dict]] = None) -> List[HiveTask]:
        """
        Decompose goal into tasks and dependencies, store them in DB, and return the list.
        """
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

        # Build skills list for prompt
        skills_text = ""
        if skills:
            skills_lines = ["Available skills:"]
            for s in skills:
                skills_lines.append(f"- {s['name']}: {s['description']}")
            skills_text = "\n".join(skills_lines) + "\n\n"

        system_prompt = f"""You are an AI task planner for a multi-agent system. Your job is to break down a user's goal into a set of discrete tasks that can be executed by autonomous agents (bots). Each task should be self‑contained and have clear inputs and outputs. Also identify dependencies between tasks.

{skills_text}When listing required skills for a task, use the exact skill names from the list above. If a task requires a skill not in the list, you may invent a new skill name, but it will be less likely to be matched.

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

        user_prompt = f"Goal: {goal_text}\n\n"
        if hive_context:
            user_prompt += f"Hive context: {hive_context}\n\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        config = {"model": primary_model_id, "temperature": 0.2, "max_tokens": 1500}
        try:
            response = await generate_with_messages(messages, config)
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in planner response")
            plan = json.loads(json_match.group())
            tasks_dict = plan.get("tasks", [])
            if not tasks_dict:
                raise ValueError("No tasks in planner response")
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            # Fallback: create a single task
            tasks_dict = [{
                "id": "task_1",
                "description": goal_text,
                "agent_type": "builder",
                "depends_on": [],
                "required_skills": []
            }]

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
                    description=t["description"],
                    agent_type=t.get("agent_type", "builder"),
                    status=HiveTaskStatus.PENDING,
                    depends_on=[],  # will fill after all created
                    required_skills=t.get("required_skills", []),
                    created_at=datetime.utcnow()
                )
                tasks.append(task)
                # Insert into DB
                await session.execute(
                    text("INSERT INTO tasks (id, data) VALUES (:id, :data)"),
                    {"id": real_id, "data": task.model_dump_json()}
                )

            # Now update depends_on with real IDs
            for i, t in enumerate(tasks_dict):
                real_deps = [task_id_map[dep] for dep in t.get("depends_on", []) if dep in task_id_map]
                tasks[i].depends_on = real_deps
                # Update DB
                await session.execute(
                    text("UPDATE tasks SET data = :data WHERE id = :id"),
                    {"id": tasks[i].id, "data": tasks[i].model_dump_json()}
                )

            # Store edges in task_edges table
            for from_task, to_task in [(dep, task_id_map[t["id"]]) for t in tasks_dict for dep in t.get("depends_on", []) if dep in task_id_map]:
                await session.execute(
                    text("INSERT INTO task_edges (from_task, to_task) VALUES (:from, :to) ON CONFLICT DO NOTHING"),
                    {"from": from_task, "to": to_task}
                )

            await session.commit()

        logger.info(f"Planner created {len(tasks)} tasks for goal {goal_id}")
        return tasks
