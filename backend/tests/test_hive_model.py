# backend/tests/test_hive_model.py
import pytest
from datetime import datetime
from app.models.types import Hive, Agent, AgentStatus, ReasoningConfig, ReportingTarget, AgentRole
import json

def test_hive_model_serialization():
    """Test that Hive model correctly serializes agent_ids and excludes agents."""
    now = datetime.utcnow()
    hive = Hive(
        id="h-test",
        name="Test Hive",
        description="desc",
        agent_ids=["b-123", "b-456"],
        agents=[],  # excluded
        global_user_md="",
        messages=[],
        global_files=[],
        hive_mind_config={},
        created_at=now,
        updated_at=now
    )
    dumped = hive.model_dump(by_alias=True)
    # Should contain agentIds (camelCase) and not agents
    assert "agentIds" in dumped
    assert dumped["agentIds"] == ["b-123", "b-456"]
    assert "agents" not in dumped
    # Check that other fields are present
    assert dumped["id"] == "h-test"
    assert dumped["name"] == "Test Hive"

def test_hive_model_deserialization():
    """Test that Hive model correctly reads agentIds from JSON."""
    now = datetime.utcnow().isoformat()
    data = {
        "id": "h-test",
        "name": "Test Hive",
        "description": "desc",
        "agentIds": ["b-123", "b-456"],
        "globalUserMd": "",
        "messages": [],
        "globalFiles": [],
        "hiveMindConfig": {},
        "createdAt": now,
        "updatedAt": now
    }
    hive = Hive.model_validate(data)
    assert hive.agent_ids == ["b-123", "b-456"]
    assert hive.agents == []  # not loaded

def test_get_hive_for_agent_query():
    """Test that the SQL query used in internal.py works with camelCase key."""
    # This test requires a real database – we'll simulate by checking the query string.
    from app.api.v1.endpoints.internal import get_hive_for_agent
    # The query should contain 'agentIds' (camelCase) not 'agent_ids'.
    import inspect
    source = inspect.getsource(get_hive_for_agent)
    assert "data->'agentIds'" in source or "data->>agentIds" in source, \
        "Query must use camelCase key 'agentIds'"
