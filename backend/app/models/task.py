from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

class Task(BaseModel):
    id: str
    hive_id: str
    goal_id: str
    parent_task_id: Optional[str] = None
    description: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: Optional[str] = None
    input_data: Dict[str, Any] = {}
    output_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    required_skills: List[str] = []
    depends_on: List[str] = []          # NEW: stores IDs of tasks this task depends on

class TaskGraph(BaseModel):
    goal_id: str
    goal_description: str
    hive_id: str
    tasks: List[Task]
    edges: List[Dict[str, str]]  # [{"from": "task_id", "to": "task_id"}]
    created_at: datetime
    status: str = "active"       # active, completed, failed
