import logging
from typing import List, Dict, Any, Optional
from ..services.litellm_service import generate_with_messages
from ..core.config import settings
import json
import re

logger = logging.getLogger(__name__)

class Planner:
    def __init__(self):
        self.model = None  # Will be determined dynamically

    async def plan(self, goal: str, hive_context: Optional[str] = None, skills: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Decompose goal into tasks and dependencies.
        Returns: {
            "tasks": [{"id": "...", "description": "...", "depends_on": ["task_id"], "required_skills": ["skill_name"]}],
            "reasoning": "..."
        }
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

Respond in JSON format with the following structure:
{{
  "tasks": [
    {{
      "id": "task_1",  // Use simple IDs like task_1, task_2, etc.
      "description": "Describe what the agent should do",
      "depends_on": [],  // List of task IDs that must complete before this one
      "required_skills": ["skill_name1", "skill_name2"] // List of skill names needed
    }},
    ...
  ],
  "reasoning": "Brief explanation of the decomposition."
}}

Do not include any other text outside the JSON.
"""

        user_prompt = f"Goal: {goal}\n\n"
        if hive_context:
            user_prompt += f"Hive context: {hive_context}\n\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        config = {"model": primary_model_id, "temperature": 0.2, "max_tokens": 1500}
        try:
            response = await generate_with_messages(messages, config)
            # Extract JSON from response (handle possible markdown)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in planner response")
            plan = json.loads(json_match.group())
            # Ensure tasks list exists
            if "tasks" not in plan:
                plan["tasks"] = []
            # Ensure each task has depends_on and required_skills
            for t in plan["tasks"]:
                if "depends_on" not in t:
                    t["depends_on"] = []
                if "required_skills" not in t:
                    t["required_skills"] = []
            return plan
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            # Fallback: create a single task
            return {
                "tasks": [{"id": "task_1", "description": goal, "depends_on": [], "required_skills": []}],
                "reasoning": "Fallback: could not decompose, treating as single task."
            }
