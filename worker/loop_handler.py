import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from pathlib import Path
import importlib

logger = logging.getLogger(__name__)

# ==================== Base Interface ====================

class BaseLoopHandler(ABC):
    """Abstract base class for all loop handlers."""

    @abstractmethod
    async def run(
        self,
        agent_id: str,
        task_id: str,
        description: str,
        input_data: Dict[str, Any],
        goal_id: str,
        hive_id: str,
        project_id: Optional[str],
        skill_executor,
        call_ai_delta,
        save_artifact,
        update_artifact_status,
        layer_id: Optional[str] = "core"
    ) -> Dict[str, Any]:
        """
        Execute the task with a domain‑specific loop.
        Must return a dict with at least 'success' (bool) and 'iterations' (int).
        """
        pass

# ==================== Default Implementation ====================

class DefaultLoopHandler(BaseLoopHandler):
    """The standard build‑test‑fix loop (moved from worker)."""

    MAX_ITERATIONS = 5

    async def run(
        self,
        agent_id: str,
        task_id: str,
        description: str,
        input_data: Dict[str, Any],
        goal_id: str,
        hive_id: str,
        project_id: Optional[str],
        skill_executor,
        call_ai_delta,
        save_artifact,
        update_artifact_status,
        layer_id: Optional[str] = "core"
    ) -> Dict[str, Any]:
        from worker.constants import (
            BUILDER_SOUL, BUILDER_IDENTITY, BUILDER_TOOLS,
            TESTER_SOUL, TESTER_IDENTITY, TESTER_TOOLS,
            REVIEWER_SOUL, REVIEWER_IDENTITY, REVIEWER_TOOLS,
            FIXER_SOUL, FIXER_IDENTITY, FIXER_TOOLS
        )

        def make_system_prompt(soul, identity, tools):
            return f"""You are an AI agent with the following STRICT IDENTITY. You must follow this identity exactly.

IDENTITY:
{identity}

SOUL:
{soul}

TOOLS:
{tools}

IMPORTANT: You are NOT a generic AI assistant. You are the entity described above. Always respond in character.
"""

        builder_prompt = make_system_prompt(BUILDER_SOUL, BUILDER_IDENTITY, BUILDER_TOOLS)
        tester_prompt = make_system_prompt(TESTER_SOUL, TESTER_IDENTITY, TESTER_TOOLS)
        reviewer_prompt = make_system_prompt(REVIEWER_SOUL, REVIEWER_IDENTITY, REVIEWER_TOOLS)
        fixer_prompt = make_system_prompt(FIXER_SOUL, FIXER_IDENTITY, FIXER_TOOLS)

        async def call_with_role(role_prompt, user_prompt):
            return await call_ai_delta(
                agent_id,
                user_prompt,
                {},  # config will be taken from agent in the backend
                system_prompt_override=role_prompt,
                retries=1
            )

        def extract_json(text: str) -> Optional[dict]:
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if code_block_match:
                try:
                    return json.loads(code_block_match.group(1))
                except:
                    pass
            json_match = re.search(r'\{.*?\}', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            return None

        current_code = None
        final_artifact_id = None
        for iteration in range(1, self.MAX_ITERATIONS + 1):
            logger.info(f"Agent {agent_id} – Iteration {iteration} for task {task_id}")

            builder_input = f"""Task: {description}
Additional input: {json.dumps(input_data, indent=2)}
Previous code (if any): {current_code or 'None'}
Generate the code for this task. Output only the code, no explanations."""
            code = await call_with_role(builder_prompt, builder_input)
            file_path = f"task_{task_id}/iteration_{iteration}/code.py"
            code_artifact = await save_artifact(hive_id, goal_id, task_id, file_path, code.encode(), status="draft", layer_id=layer_id)
            if code_artifact and code_artifact.get('id'):
                await update_artifact_status(hive_id, goal_id, code_artifact['id'], "built")
            current_code = code

            tester_input = f"""Task: {description}
Code to test:
{code}
Write and run tests for this code. Output the test results **in JSON format only** with keys "passed" (bool) and "errors" (list of strings). Do not include any other text.
Example: {{"passed": true, "errors": []}}"""
            test_result_text = await call_with_role(tester_prompt, tester_input)
            logger.debug(f"Raw test result from AI: {test_result_text[:200]}")

            test_result = extract_json(test_result_text)
            if test_result is None:
                logger.error(f"Failed to parse test result: {test_result_text}")
                test_result = {"passed": False, "errors": ["Failed to parse test output"]}

            test_artifact = await save_artifact(hive_id, goal_id, task_id, f"task_{task_id}/iteration_{iteration}/test_result.json", json.dumps(test_result).encode(), status="tested", layer_id=layer_id)
            if code_artifact and code_artifact.get('id'):
                await update_artifact_status(hive_id, goal_id, code_artifact['id'], "tested")

            if test_result.get("passed"):
                logger.info(f"Task {task_id} passed on iteration {iteration}")
                final_artifact = await save_artifact(hive_id, goal_id, task_id, f"task_{task_id}/final_code.py", current_code.encode(), status="final", layer_id=layer_id)
                if final_artifact and final_artifact.get('id'):
                    await update_artifact_status(hive_id, goal_id, final_artifact['id'], "final")
                return {
                    "success": True,
                    "iterations": iteration,
                    "output": {
                        "final_artifact": final_artifact.get('id') if final_artifact else None,
                        "message": "Task completed successfully"
                    }
                }
            else:
                logger.warning(f"Tests failed on iteration {iteration}: {test_result.get('errors', [])}")

            reviewer_input = f"""Task: {description}
Code:
{code}
Test errors:
{json.dumps(test_result.get('errors', []), indent=2)}
List the issues in the code that caused the test failures. Provide a list of actionable fixes."""
            issues = await call_with_role(reviewer_prompt, reviewer_input)
            await save_artifact(hive_id, goal_id, task_id, f"task_{task_id}/iteration_{iteration}/issues.txt", issues.encode(), status="reviewed", layer_id=layer_id)

            fixer_input = f"""Task: {description}
Code:
{code}
Issues:
{issues}
Provide the fixed code. Output only the corrected code, no explanations."""
            fixed_code = await call_with_role(fixer_prompt, fixer_input)
            current_code = fixed_code
            fixed_artifact = await save_artifact(hive_id, goal_id, task_id, f"task_{task_id}/iteration_{iteration}/fixed_code.py", fixed_code.encode(), status="fixed", layer_id=layer_id)
            if code_artifact and code_artifact.get('id'):
                # The fixed code is a new artifact; we could link it as a child, but not required.
                pass

        logger.warning(f"Task {task_id} failed after {self.MAX_ITERATIONS} iterations")
        return {
            "success": False,
            "iterations": self.MAX_ITERATIONS,
            "output": {"message": "Max iterations exceeded"}
        }

# ==================== Registry ====================

class LoopHandlerRegistry:
    """Loads and provides loop handlers. Always includes a built‑in default."""

    def __init__(self):
        self._handlers = {
            'default': DefaultLoopHandler,   # built‑in fallback
        }

    async def load_from_db(self, db_session):
        """Query loop_handlers table and import classes. Overrides if a handler with the same name exists."""
        from sqlalchemy import text
        result = await db_session.execute(
            text("SELECT id, name, class_path FROM loop_handlers")
        )
        rows = result.fetchall()
        for row in rows:
            name = row[1]
            class_path = row[2]
            try:
                module_name, class_name = class_path.rsplit(".", 1)
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name)
                self._handlers[name] = cls   # override if name already exists
                logger.info(f"Loaded loop handler: {name} -> {class_path}")
            except Exception as e:
                logger.error(f"Failed to load loop handler {name} from {class_path}: {e}")

    def get(self, name: str):
        """Return the handler class (not instance) for the given name."""
        return self._handlers.get(name)

    def default(self):
        return self.get("default")

# Global registry instance (will be populated at worker startup)
registry = LoopHandlerRegistry()
