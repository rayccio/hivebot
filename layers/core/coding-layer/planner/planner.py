import re
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Try to import from app (real environment); fallback for tests
try:
    from app.models.types import HiveTask, HiveTaskStatus
except ImportError:
    # Dummy classes for testing
    class HiveTask:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    class HiveTaskStatus:
        PENDING = "pending"

# Safe imports for litellm and settings
try:
    from app.services.litellm_service import generate_with_messages
except ImportError:
    # Mock for tests
    async def generate_with_messages(messages, config):
        raise NotImplementedError("generate_with_messages not available in test environment")

try:
    from app.core.config import settings
except ImportError:
    # Mock for tests
    class DummySettings:
        secrets = type('', (), {'get': lambda self, key, default=None: {}})()
    settings = DummySettings()

logger = logging.getLogger(__name__)


class CodingPlanner:
    """
    Custom planner for coding tasks. Uses LLM to decompose goals into tasks,
    leveraging the layer's roles, skills, and templates.
    """

    async def plan(
        self,
        goal_text: str,
        hive_context: str = "",
        skills: Optional[List[Dict]] = None,
        roles: Optional[List[str]] = None,
    ) -> List[HiveTask]:
        """
        Decompose a coding goal into tasks.
        Returns a list of HiveTask objects.
        """
        # Prepare available roles and skills for the prompt
        roles_text = "\n".join([f"- {role}" for role in (roles or [])]) if roles else "No specific roles defined."
        skills_text = ""
        skill_map = {}
        if skills:
            skills_lines = ["Available skills (name → description):"]
            for s in skills:
                skills_lines.append(f"- {s['name']}: {s['description']}")
                skill_map[s['name'].lower()] = s['id']
            skills_text = "\n".join(skills_lines) + "\n\n"

        # Load templates from the layer (if any)
        import json as json_lib
        from pathlib import Path
        templates = []
        templates_path = Path(__file__).parent / "templates.json"
        if templates_path.exists():
            with open(templates_path, "r") as f:
                templates = json_lib.load(f)

        # Build system prompt with few-shot examples
        system_prompt = f"""You are an AI task planner for a multi-agent system specialised in web development. Your job is to break down a user's goal into a set of discrete tasks that can be executed by autonomous agents (bots). Each task should be self‑contained and have clear inputs and outputs. Also identify dependencies between tasks.

Available agent roles (choose from these):
{roles_text}

{skills_text}
When listing required skills for a task, use the exact skill names from the list above. If a task requires a skill not in the list, you may invent a new skill name, but it will be less likely to be matched.

For each task, assign an `agent_type` from the available roles.

Respond in JSON format with the following structure:
{{
  "tasks": [
    {{
      "id": "task_1",  // Use simple IDs like task_1, task_2, etc.
      "description": "Describe what the agent should do",
      "agent_type": "frontend-developer",
      "depends_on": [],  // List of task IDs that must complete before this one
      "required_skills": ["skill_name1", "skill_name2"] // List of skill names needed
    }},
    ...
  ],
  "reasoning": "Brief explanation of the decomposition."
}}

Do not include any other text outside the JSON.
"""

        # Add few-shot templates if available
        if templates:
            system_prompt += "\n\nHere are some examples of how to decompose similar goals:\n"
            for tmpl in templates:
                if "template" in tmpl:
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
            # Fallback: single generic task
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
                    # Keep as placeholder (will be handled by skill suggestions)
                    skill_ids.append(name)
            t["required_skills"] = skill_ids

        # Convert to HiveTask objects
        tasks = []
        task_id_map = {}
        now = datetime.utcnow()
        for t in tasks_dict:
            real_id = f"t-{uuid.uuid4().hex[:8]}"
            task_id_map[t["id"]] = real_id
            task = HiveTask(
                id=real_id,
                goal_id="",  # Will be set by the caller (main planner)
                hive_id="",  # Will be set by the caller
                description=t["description"],
                agent_type=t.get("agent_type", "builder"),
                status=HiveTaskStatus.PENDING,
                depends_on=[],  # Will fill after we have all IDs
                required_skills=t.get("required_skills", []),
                created_at=now,
                loop_handler="coding_loop",  # Name of our custom loop handler (registered during installation)
                sandbox_level="task"         # Task-level sandbox for coding
            )
            tasks.append(task)

        # Resolve dependencies
        for i, t in enumerate(tasks_dict):
            real_deps = [task_id_map[dep] for dep in t.get("depends_on", []) if dep in task_id_map]
            tasks[i].depends_on = real_deps

        return tasks
