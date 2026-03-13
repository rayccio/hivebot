import os
import asyncio
import logging
import httpx
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class ToolExecutor:
    def __init__(self, simulator_url: str = "http://simulator:8080"):
        self.simulator_url = simulator_url
        # Real tool clients (lazy initialization)
        self._http_client: Optional[httpx.AsyncClient] = None
        self._ssh_client = None  # would be asyncssh client pool
        self._playwright = None   # would be playwright async api

    async def _get_http_client(self) -> httpx.AsyncClient:
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def execute(self, tool_name: str, params: Dict[str, Any], simulation: bool = False) -> Dict[str, Any]:
        """Execute a tool, either in simulation mode or real."""
        if simulation:
            return await self._call_simulator(tool_name, params)

        # Real execution
        tool_map = {
            "web_search": self._web_search,
            "ssh_execute": self._ssh_execute,
            "browser_action": self._browser_action,
            "run_code": self._run_code,
            "api_call": self._api_call,
        }
        func = tool_map.get(tool_name)
        if not func:
            logger.warning(f"Unknown tool '{tool_name}', falling back to simulator")
            return await self._call_simulator(tool_name, params)

        try:
            return await func(params)
        except Exception as e:
            logger.exception(f"Tool {tool_name} failed")
            return {"error": str(e), "simulated": False}

    async def _call_simulator(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Forward call to simulator service."""
        client = await self._get_http_client()
        url = f"{self.simulator_url}/mock/{tool_name}"
        try:
            resp = await client.post(url, json=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Simulator call failed: {e}")
            return {"error": str(e), "simulated": True}

    # --- Real tool implementations ---

    async def _web_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform a web search using configured API."""
        query = params.get("query", "")
        if not query:
            return {"error": "Missing query"}

        # Use environment-configured search API (e.g., SerpAPI, Bing)
        api_key = os.getenv("SEARCH_API_KEY")
        engine = os.getenv("SEARCH_ENGINE", "google").lower()

        if engine == "serpapi":
            # Example using SerpAPI
            client = await self._get_http_client()
            resp = await client.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": api_key, "engine": "google"}
            )
            resp.raise_for_status()
            data = resp.json()
            # Extract organic results
            results = []
            for r in data.get("organic_results", []):
                results.append({
                    "title": r.get("title"),
                    "link": r.get("link"),
                    "snippet": r.get("snippet")
                })
            return {"results": results}
        else:
            # Fallback to a simple mock
            return {
                "results": [
                    {"title": f"Mock result for {query}", "url": "http://example.com", "snippet": "This is a mock result."}
                ]
            }

    async def _ssh_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command on a remote server via SSH."""
        host = params.get("host")
        port = params.get("port", 22)
        username = params.get("username")
        password = params.get("password")
        command = params.get("command")

        if not all([host, username, command]):
            return {"error": "Missing required parameters"}

        # Use asyncssh (needs to be installed)
        try:
            import asyncssh
        except ImportError:
            return {"error": "asyncssh not installed"}

        try:
            async with asyncssh.connect(
                host=host,
                port=port,
                username=username,
                password=password,
                known_hosts=None  # In production, manage known_hosts
            ) as conn:
                result = await conn.run(command, check=True)
                return {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code
                }
        except Exception as e:
            return {"error": str(e)}

    async def _browser_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform browser automation using Playwright."""
        action = params.get("action")
        url = params.get("url")
        selector = params.get("selector")
        value = params.get("value")

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"error": "playwright not installed"}

        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            if action == "goto":
                await page.goto(url)
                content = await page.content()
                return {"html": content, "title": await page.title()}
            elif action == "click":
                await page.goto(url)
                await page.click(selector)
                await page.wait_for_load_state()
                return {"success": True, "html": await page.content()}
            elif action == "type":
                await page.goto(url)
                await page.fill(selector, value)
                return {"success": True}
            elif action == "screenshot":
                await page.goto(url)
                screenshot = await page.screenshot(full_page=True)
                # Return base64 encoded screenshot
                import base64
                return {"screenshot": base64.b64encode(screenshot).decode()}
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            await browser.close()
            await p.stop()

    async def _run_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code in an isolated Docker container."""
        code = params.get("code", "")
        language = params.get("language", "python").lower()

        # Use Docker SDK to run a temporary container
        try:
            import docker
        except ImportError:
            return {"error": "docker not installed"}

        client = docker.from_env()
        image_map = {
            "python": "python:3.11-slim",
            "node": "node:18-slim",
            "bash": "alpine:latest",
        }
        image = image_map.get(language, "alpine:latest")

        try:
            if language == "python":
                cmd = ["python", "-c", code]
            elif language == "node":
                cmd = ["node", "-e", code]
            elif language == "bash":
                cmd = ["sh", "-c", code]
            else:
                return {"error": f"Unsupported language: {language}"}

            container = client.containers.run(
                image=image,
                command=cmd,
                detach=False,
                remove=True,
                mem_limit="128m",
                cpu_shares=512,
                network_disabled=True,  # no network for security
                read_only=True
            )
            # container.run returns logs (since detach=False)
            logs = container.decode() if isinstance(container, bytes) else str(container)
            return {"stdout": logs, "stderr": ""}
        except Exception as e:
            return {"error": str(e)}

    async def _api_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make an HTTP request to an external API."""
        method = params.get("method", "GET").upper()
        url = params.get("url")
        headers = params.get("headers", {})
        body = params.get("body")

        if not url:
            return {"error": "Missing URL"}

        client = await self._get_http_client()
        try:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "POST":
                resp = await client.post(url, json=body, headers=headers)
            elif method == "PUT":
                resp = await client.put(url, json=body, headers=headers)
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers)
            else:
                return {"error": f"Unsupported method: {method}"}

            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                data = resp.json()
            else:
                data = resp.text

            return {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": data
            }
        except Exception as e:
            return {"error": str(e)}
