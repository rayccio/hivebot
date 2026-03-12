import os
import asyncio
from typing import List, Dict, Any, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)

COLLECTION_NAME = "hive_mind"

class VectorService:
    def __init__(self):
        self.client = None

    async def connect(self, max_retries: int = 10, delay: int = 2):
        """Connect to Qdrant with retries."""
        host = os.getenv("QDRANT_HOST", "qdrant")
        port = int(os.getenv("QDRANT_PORT", 6333))
        for attempt in range(max_retries):
            try:
                self.client = AsyncQdrantClient(host=host, port=port)
                # Test connection
                await self.client.get_collections()
                logger.info(f"Connected to Qdrant at {host}:{port}")
                return
            except Exception as e:
                logger.warning(f"Qdrant connection attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay * (2 ** attempt))  # exponential backoff
                else:
                    logger.error("Failed to connect to Qdrant after all retries")
                    raise

    async def ensure_collection(self, dim: int = 384):
        """Create collection if it doesn't exist."""
        if not self.client:
            await self.connect()
        collections = await self.client.get_collections()
        if COLLECTION_NAME not in [c.name for c in collections.collections]:
            await self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE)
            )
            logger.info(f"Created collection {COLLECTION_NAME}")

    async def search(self, vector: List[float], filter_condition: Optional[models.Filter] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar vectors with optional filter."""
        if not self.client:
            await self.connect()
        results = await self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            query_filter=filter_condition,
            limit=limit,
            with_payload=True
        )
        return [hit.payload for hit in results]

    async def delete_by_file(self, file_id: str):
        """Delete all vectors associated with a file."""
        if not self.client:
            await self.connect()
        await self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(key="file_id", match=models.MatchValue(value=file_id))
                ]
            )
        )
        logger.debug(f"Deleted vectors for file {file_id}")

    async def delete_by_agent(self, agent_id: str):
        """Delete all vectors for a given agent (e.g., when agent is deleted)."""
        if not self.client:
            await self.connect()
        await self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(key="agent_id", match=models.MatchValue(value=agent_id))
                ]
            )
        )
        logger.debug(f"Deleted vectors for agent {agent_id}")

    async def close(self):
        if self.client:
            await self.client.close()

vector_service = VectorService()
