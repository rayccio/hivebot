import json
import logging
from ..services.redis_service import redis_service

logger = logging.getLogger(__name__)

async def trigger_message_embedding(agent_id: str, hive_id: str, text: str, timestamp: str):
    """Publish a message embedding task to Redis."""
    task = {
        "type": "message",
        "agent_id": agent_id,
        "hive_id": hive_id,
        "text": text,
        "timestamp": timestamp
    }
    await redis_service.publish("embedding:tasks", task)
    logger.debug(f"Queued embedding for message from agent {agent_id}")

async def trigger_file_embedding(file_path: str, hive_id: str, file_id: str, agent_id: str = None):
    """Publish a file embedding task to Redis."""
    task = {
        "type": "file",
        "file_path": file_path,
        "hive_id": hive_id,
        "file_id": file_id,
        "agent_id": agent_id
    }
    await redis_service.publish("embedding:tasks", task)
    logger.info(f"Queued embedding for file {file_id}")
