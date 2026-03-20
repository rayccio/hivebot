import os
import json
import logging
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
import uvicorn
import redis.asyncio as redis
from pathlib import Path

LOG_DIR = Path("/app/logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "simulator.log")
    ]
)
logger = logging.getLogger("simulator")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

app = FastAPI(title="HiveBot Simulator")

redis_client = None

@app.on_event("startup")
async def startup():
    global redis_client
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
    logger.info("Simulator connected to Redis")

@app.on_event("shutdown")
async def shutdown():
    if redis_client:
        await redis_client.close()

@app.post("/mock/ssh_execute")
async def mock_ssh_execute(request: Request):
    payload = await request.json()
    command = payload.get("command", "")
    logger.info(f"Mock SSH execute: {command}")
    return {
        "stdout": f"Simulated output for command: {command}",
        "stderr": "",
        "exit_code": 0
    }

@app.post("/mock/browser_action")
async def mock_browser_action(request: Request):
    payload = await request.json()
    action = payload.get("action", "")
    url = payload.get("url", "")
    logger.info(f"Mock browser action: {action} on {url}")
    return {
        "screenshot": None,
        "html": "<html><body>Simulated page</body></html>",
        "success": True
    }

@app.post("/mock/web_search")
async def mock_web_search(request: Request):
    payload = await request.json()
    query = payload.get("query", "")
    logger.info(f"Mock web search: {query}")
    return {
        "results": [
            {"title": f"Simulated result for {query}", "url": "http://example.com", "snippet": "This is a simulated snippet."}
        ]
    }

@app.post("/mock/api_call")
async def mock_api_call(request: Request):
    payload = await request.json()
    endpoint = payload.get("endpoint", "")
    method = payload.get("method", "GET")
    logger.info(f"Mock API call: {method} {endpoint}")
    return {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "body": {"message": "Simulated API response"}
    }

@app.post("/mock/run_code")
async def mock_run_code(request: Request):
    payload = await request.json()
    code = payload.get("code", "")
    language = payload.get("language", "python")
    logger.info(f"Mock run code ({language})")
    return {
        "stdout": "Simulated code output",
        "stderr": "",
        "exit_code": 0
    }

@app.post("/mock/{tool_name:path}")
async def mock_tool(tool_name: str, request: Request):
    payload = await request.json()
    logger.info(f"Mock tool '{tool_name}' called with payload: {payload}")
    return {
        "result": f"Simulated response for {tool_name}",
        "simulated": True
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
