import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import text, and_
from ..core.database import AsyncSessionLocal
from ..models.types import ExecutionLog, ExecutionLogLevel
import logging

logger = logging.getLogger(__name__)

class ExecutionLogger:
    """Service for writing and retrieving execution logs."""

    async def log(
        self,
        goal_id: str,
        level: ExecutionLogLevel,
        message: str,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        iteration: Optional[int] = None
    ) -> ExecutionLog:
        """Write an execution log entry."""
        log_id = f"log-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        log = ExecutionLog(
            id=log_id,
            goal_id=goal_id,
            task_id=task_id,
            agent_id=agent_id,
            level=level,
            message=message,
            iteration=iteration,
            created_at=now
        )
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO execution_logs (id, goal_id, task_id, agent_id, level, message, iteration, created_at)
                    VALUES (:id, :goal_id, :task_id, :agent_id, :level, :message, :iteration, :created_at)
                """),
                {
                    "id": log_id,
                    "goal_id": goal_id,
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "level": level.value,
                    "message": message,
                    "iteration": iteration,
                    "created_at": now
                }
            )
            await session.commit()
        logger.debug(f"Logged execution event for goal {goal_id}: {message}")
        return log

    async def get_logs_for_goal(
        self,
        goal_id: str,
        limit: int = 100,
        offset: int = 0,
        level: Optional[ExecutionLogLevel] = None
    ) -> List[ExecutionLog]:
        """Retrieve execution logs for a goal, with optional filtering."""
        async with AsyncSessionLocal() as session:
            query = """
                SELECT id, goal_id, task_id, agent_id, level, message, iteration, created_at
                FROM execution_logs
                WHERE goal_id = :goal_id
            """
            params = {"goal_id": goal_id}
            if level:
                query += " AND level = :level"
                params["level"] = level.value
            query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            params["limit"] = limit
            params["offset"] = offset
            result = await session.execute(text(query), params)
            rows = await result.all()          # <-- changed from fetchall()
            logs = []
            for r in rows:
                logs.append(ExecutionLog(
                    id=r[0],
                    goal_id=r[1],
                    task_id=r[2],
                    agent_id=r[3],
                    level=ExecutionLogLevel(r[4]),
                    message=r[5],
                    iteration=r[6],
                    created_at=r[7]
                ))
            return logs

    async def get_logs_for_task(
        self,
        goal_id: str,
        task_id: str,
        limit: int = 50
    ) -> List[ExecutionLog]:
        """Retrieve logs specific to a task within a goal."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT id, goal_id, task_id, agent_id, level, message, iteration, created_at
                    FROM execution_logs
                    WHERE goal_id = :goal_id AND task_id = :task_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"goal_id": goal_id, "task_id": task_id, "limit": limit}
            )
            rows = await result.all()          # <-- changed from fetchall()
            logs = []
            for r in rows:
                logs.append(ExecutionLog(
                    id=r[0],
                    goal_id=r[1],
                    task_id=r[2],
                    agent_id=r[3],
                    level=ExecutionLogLevel(r[4]),
                    message=r[5],
                    iteration=r[6],
                    created_at=r[7]
                ))
            return logs
