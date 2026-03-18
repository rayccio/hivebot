import os
import asyncio
import logging
import httpx
from typing import Dict, Any, Optional, List
import json

logger = logging.getLogger(__name__)

# Optional imports – gracefully handled
try:
    import asyncssh
except ImportError:
    asyncssh = None
    logger.warning("asyncssh not installed, SSH tool will be unavailable")

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None
    logger.warning("playwright not installed, browser tool will be unavailable")

try:
    import docker
except ImportError:
    docker = None
    logger.warning("docker not installed, code execution tool will be unavailable")


class ToolExecutor:
    def __init__(self, simulator_url: str = "http://simulator:8080"):
        self.simulator_url = simulator_url
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def execute(
        self,
        tool_name: str,
        params: Dict[str, Any],
        simulation: bool = False,
        allowed_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Execute a tool, checking permissions first."""
        # Permission check
        if allowed_tools is not None and tool_name not in allowed_tools:
            logger.warning(f"Tool '{tool_name}' not allowed for this agent")
            return {"error": f"Tool '{tool_name}' is not in allowed tools list", "simulated": simulation}

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

    # --- Real tool implementations (with availability checks) ---

    async def _web_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform a web search using configured API."""
        query = params.get("query", "")
        if not query:
            return {"error": "Missing query"}

        api_key = os.getenv("SEARCH_API_KEY")
        engine = os.getenv("SEARCH_ENGINE", "google").lower()

        if engine == "serpapi" and api_key:
            client = await self._get_http_client()
            try:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={"q": query, "api_key": api_key, "engine": "google"}
                )
                resp.raise_for_status()
                data = resp.json()
                results = []
                for r in data.get("organic_results", []):
                    results.append({
                        "title": r.get("title"),
                        "link": r.get("link"),
                        "snippet": r.get("snippet")
                    })
                return {"results": results}
            except Exception as e:
                logger.error(f"Web search failed: {e}")
                return {"error": str(e)}
        else:
            # Fallback mock
            return {
                "results": [
                    {"title": f"Mock result for {query}", "url": "http://example.com", "snippet": "This is a mock result."}
                ]
            }

    async def _ssh_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command on a remote server via SSH."""
        if asyncssh is None:
            return {"error": "asyncssh not installed"}

        host = params.get("host")
        port = params.get("port", 22)
        username = params.get("username")
        password = params.get("password")
        command = params.get("command")

        if not all([host, username, command]):
            return {"error": "Missing required parameters"}

        try:
            async with asyncssh.connect(
                host=host,
                port=port,
                username=username,
                password=password,
                known_hosts=None
            ) as conn:
                result = await conn.run(command, check=True)
                return {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code
                }
        except Exception as e:
            logger.error(f"SSH execution failed: {e}")
            return {"error": str(e)}

    async def _browser_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform browser automation using Playwright."""
        if async_playwright is None:
            return {"error": "playwright not installed"}

        action = params.get("action")
        url = params.get("url")
        selector = params.get("selector")
        value = params.get("value")

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
                import base64
                return {"screenshot": base64.b64encode(screenshot).decode()}
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            logger.error(f"Browser action failed: {e}")
            return {"error": str(e)}
        finally:
            await browser.close()
            await p.stop()

    async def _run_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code in an isolated Docker container."""
        if docker is None:
            return {"error": "docker not installed"}

        code = params.get("code", "")
        language = params.get("language", "python").lower()

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
                network_disabled=True,
                read_only=True
            )
            logs = container.decode() if isinstance(container, bytes) else str(container)
            return {"stdout": logs, "stderr": ""}
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
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
            logger.error(f"API call failed: {e}")
            return {"error": str(e)}
