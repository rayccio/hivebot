import os
import asyncio
import json
import logging
import redis.asyncio as redis
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
import httpx
from typing import List, Dict, Any
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("embedding-worker")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://backend:8000")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", 384))

COLLECTION_NAME = "hive_mind"

# Load embedding model once at startup
model = SentenceTransformer(EMBEDDING_MODEL)

async def ensure_collection(qdrant: AsyncQdrantClient):
    """Create collection if it doesn't exist."""
    collections = await qdrant.get_collections()
    if COLLECTION_NAME not in [c.name for c in collections.collections]:
        await qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE)
        )
        logger.info(f"Created collection {COLLECTION_NAME}")

def generate_point_id(text: str) -> str:
    """Generate a stable ID for a given text (to avoid duplicates)."""
    return hashlib.sha256(text.encode()).hexdigest()

async def process_message_task(agent_id: str, hive_id: str, text: str, timestamp: str):
    """Generate embedding for a single message and store in Qdrant."""
    if not text.strip():
        return
    vector = model.encode(text).tolist()
    point_id = generate_point_id(text)
    payload = {
        "agent_id": agent_id,
        "hive_id": hive_id,
        "text": text,
        "timestamp": timestamp,
        "source": "message"
    }
    qdrant = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    await qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=[models.PointStruct(id=point_id, vector=vector, payload=payload)]
    )
    await qdrant.close()
    logger.debug(f"Embedded message from agent {agent_id}")

async def process_file_task(file_path: str, hive_id: str, file_id: str, agent_id: str = None):
    """Read file, chunk (if large), and embed each chunk."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        return

    # Simple chunking: split by paragraphs, max 1000 chars each
    chunks = []
    for para in content.split("\n\n"):
        if not para.strip():
            continue
        if len(para) > 1000:
            # further split into sentences
            sentences = para.split(". ")
            chunk = ""
            for sent in sentences:
                if len(chunk) + len(sent) < 1000:
                    chunk += sent + ". "
                else:
                    if chunk:
                        chunks.append(chunk.strip())
                    chunk = sent + ". "
            if chunk:
                chunks.append(chunk.strip())
        else:
            chunks.append(para.strip())

    qdrant = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    points = []
    for i, chunk in enumerate(chunks):
        vector = model.encode(chunk).tolist()
        point_id = generate_point_id(f"{file_id}_{i}")
        payload = {
            "hive_id": hive_id,
            "file_id": file_id,
            "chunk_index": i,
            "text": chunk,
            "source": "file",
            "agent_id": agent_id  # None for hive files
        }
        points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))
    if points:
        await qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
        logger.info(f"Embedded {len(points)} chunks from file {file_id}")
    await qdrant.close()

async def main_loop():
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
    qdrant = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    await ensure_collection(qdrant)
    await qdrant.close()

    pubsub = redis_client.pubsub()
    await pubsub.subscribe("embedding:tasks")
    logger.info("Embedding worker subscribed to embedding:tasks")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            task = json.loads(message["data"])
            task_type = task.get("type")

            if task_type == "message":
                await process_message_task(
                    task["agent_id"],
                    task["hive_id"],
                    task["text"],
                    task["timestamp"]
                )
            elif task_type == "file":
                await process_file_task(
                    task["file_path"],
                    task["hive_id"],
                    task["file_id"],
                    task.get("agent_id")
                )
            else:
                logger.warning(f"Unknown task type: {task_type}")
        except Exception as e:
            logger.exception("Error processing embedding task")

if __name__ == "__main__":
    asyncio.run(main_loop())
