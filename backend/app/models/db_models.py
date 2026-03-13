from sqlalchemy import Column, String, JSON, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.sql import func
from ..core.database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=generate_uuid)
    data = Column(JSON, nullable=False)
    container_id = Column(String, nullable=True)
    status = Column(String, default="IDLE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class HiveModel(Base):
    __tablename__ = "hives"

    id = Column(String, primary_key=True, default=generate_uuid)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=generate_uuid)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class SkillModel(Base):
    __tablename__ = "skills"

    id = Column(String, primary_key=True, default=generate_uuid)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class SkillVersionModel(Base):
    __tablename__ = "skill_versions"

    id = Column(String, primary_key=True, default=generate_uuid)
    skill_id = Column(String, ForeignKey("skills.id"), nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class SkillSuggestionModel(Base):
    __tablename__ = "skill_suggestions"

    id = Column(String, primary_key=True, default=generate_uuid)
    skill_name = Column(String, nullable=False)
    goal_id = Column(String, nullable=False)
    goal_description = Column(Text, nullable=False)
    task_id = Column(String, nullable=False)
    task_description = Column(Text, nullable=False)
    suggested_by = Column(String, nullable=True)   # could be agent_id or "planner"
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class GlobalSettingsModel(Base):
    __tablename__ = "global_settings"

    id = Column(Integer, primary_key=True, default=1)  # singleton
    data = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class EvaluationTaskModel(Base):
    __tablename__ = "evaluation_tasks"

    id = Column(String, primary_key=True, default=generate_uuid)
    description = Column(Text, nullable=False)
    input_data = Column(JSON, default={})
    tags = Column(JSON, default=[])
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
