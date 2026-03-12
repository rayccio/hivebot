import redis.asyncio as redis
from typing import Optional, Any, List, Set
from ..core.config import settings
import json
import logging
import asyncio
from ..models.types import ConversationMessage
from datetime import datetime

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self):
        self.client = None

    async def connect(self):
        self.client = await redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
            decode_responses=True
        )
        await self.client.ping()
        return self.client

    async def wait_ready(self, max_attempts=10, delay=2):
        for i in range(max_attempts):
            try:
                await self.connect()
                logger.info("Redis is ready.")
                return
            except Exception as e:
                logger.warning(f"Redis not ready (attempt {i+1}/{max_attempts}): {e}")
                await asyncio.sleep(delay)
        raise ConnectionError("Redis unreachable after multiple attempts")

    async def get_client(self):
        if not self.client:
            await self.connect()
        return self.client

    async def publish(self, channel: str, message: dict):
        client = await self.get_client()
        await client.publish(channel, json.dumps(message))

    async def set(self, key: str, value: Any, expire: Optional[int] = None):
        client = await self.get_client()
        if expire:
            await client.setex(key, expire, json.dumps(value))
        else:
            await client.set(key, json.dumps(value))

    async def get(self, key: str) -> Optional[Any]:
        client = await self.get_client()
        val = await client.get(key)
        if val:
            return json.loads(val)
        return None

    async def delete(self, key: str):
        client = await self.get_client()
        await client.delete(key)

    def pubsub(self):
        if not self.client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self.client.pubsub()

    # ----------------------------
    # Set operations
    # ----------------------------
    async def sadd(self, key: str, member: str) -> int:
        client = await self.get_client()
        return await client.sadd(key, member)

    async def srem(self, key: str, member: str) -> int:
        client = await self.get_client()
        return await client.srem(key, member)

    async def smembers(self, key: str) -> Set[str]:
        client = await self.get_client()
        return await client.smembers(key)

    async def sismember(self, key: str, member: str) -> bool:
        client = await self.get_client()
        return await client.sismember(key, member)

    # ----------------------------
    # Sorted set operations
    # ----------------------------
    async def zadd(self, key: str, member: str, score: float) -> int:
        client = await self.get_client()
        return await client.zadd(key, {member: score})

    async def zrem(self, key: str, member: str) -> int:
        client = await self.get_client()
        return await client.zrem(key, member)

    async def zrange(self, key: str, start: int, end: int, withscores: bool = False) -> List:
        client = await self.get_client()
        return await client.zrange(key, start, end, withscores=withscores)

    async def zscore(self, key: str, member: str) -> Optional[float]:
        client = await self.get_client()
        return await client.zscore(key, member)

    # ----------------------------
    # Conversation Methods
    # ----------------------------
    async def push_conversation_message(self, agent_id: str, message: ConversationMessage):
        key = f"conversation:{agent_id}"
        client = await self.get_client()
        await client.rpush(key, message.model_dump_json())

    async def get_conversation(self, agent_id: str, limit: int = -1) -> List[ConversationMessage]:
        key = f"conversation:{agent_id}"
        client = await self.get_client()
        if limit > 0:
            items = await client.lrange(key, -limit, -1)
        else:
            items = await client.lrange(key, 0, -1)
        messages = []
        for item in items:
            try:
                data = json.loads(item)
                messages.append(ConversationMessage(**data))
            except Exception as e:
                logger.error(f"Failed to parse conversation message: {e}")
        return messages

    async def clear_conversation(self, agent_id: str):
        client = await self.get_client()
        await client.delete(f"conversation:{agent_id}")

    async def trim_conversation(self, agent_id: str, keep_last: int = 50):
        key = f"conversation:{agent_id}"
        client = await self.get_client()
        await client.ltrim(key, -keep_last, -1)

redis_service = RedisService()
