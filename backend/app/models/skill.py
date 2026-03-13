from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class SkillType(str, Enum):
    TOOL = "tool"
    PROMPT = "prompt"
    WORKFLOW = "workflow"

class SkillVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ORGANIZATION = "organization"

class Skill(BaseModel):
    id: str
    name: str
    description: str
    type: SkillType
    visibility: SkillVisibility = SkillVisibility.PRIVATE
    author_id: Optional[str] = None
    organization_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tags: List[str] = []
    icon: Optional[str] = None
    metadata: Dict[str, Any] = {}

class SkillCreate(BaseModel):
    name: str
    description: str
    type: SkillType
    visibility: SkillVisibility = SkillVisibility.PRIVATE
    tags: List[str] = []
    icon: Optional[str] = None
    metadata: Dict[str, Any] = {}

class SkillVersion(BaseModel):
    id: str
    skill_id: str
    version: str
    code: str
    language: str = "python"
    entry_point: str = "run"
    requirements: List[str] = []
    config_schema: Optional[Dict[str, Any]] = None
    created_at: datetime
    is_active: bool = True
    changelog: Optional[str] = None

class SkillVersionCreate(BaseModel):
    version: str
    code: str
    language: str = "python"
    entry_point: str = "run"
    requirements: List[str] = []
    config_schema: Optional[Dict[str, Any]] = None
    is_active: bool = True
    changelog: Optional[str] = None

class AgentSkill(BaseModel):
    agent_id: str
    skill_id: str
    skill_version_id: str
    installed_at: datetime
    config: Dict[str, Any] = {}
    enabled: bool = True

# --- Skill Suggestion Models ---
class SkillSuggestion(BaseModel):
    id: str
    skill_name: str
    goal_id: str
    goal_description: str
    task_id: str
    task_description: str
    suggested_by: Optional[str] = None
    resolved: bool = False
    created_at: datetime
    resolved_at: Optional[datetime] = None

class SkillSuggestionCreate(BaseModel):
    skill_name: str
    goal_id: str
    goal_description: str
    task_id: str
    task_description: str
    suggested_by: Optional[str] = None
