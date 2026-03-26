import pytest
from unittest.mock import AsyncMock, patch
import json

@pytest.mark.asyncio
async def test_html_builder_success(mock_httpx_client):
    from skills.html_builder.version_1.code import run

    # Mock the internal AI response
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "<html><body>Test</body></html>"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "a simple page"}, {})
    assert "html" in result
    assert "<html>" in result["html"]
    mock_httpx_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_html_builder_missing_description():
    from skills.html_builder.version_1.code import run
    result = await run({}, {})
    assert "error" in result
    assert "Missing description" in result["error"]

@pytest.mark.asyncio
async def test_css_styling_success(mock_httpx_client):
    from skills.css_styling.version_1.code import run

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "body { color: red; }"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "red text"}, {})
    assert "css" in result
    assert "color: red" in result["css"]

@pytest.mark.asyncio
async def test_javascript_interactivity_success(mock_httpx_client):
    from skills.javascript_interactivity.version_1.code import run

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "console.log('hello');"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "log hello"}, {})
    assert "js" in result
    assert "console.log" in result["js"]

@pytest.mark.asyncio
async def test_react_component_success(mock_httpx_client):
    from skills.react_component.version_1.code import run

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "function App() { return <div>Hello</div>; }"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "hello component"}, {})
    assert "component" in result
    assert "function App" in result["component"]

@pytest.mark.asyncio
async def test_rest_api_success(mock_httpx_client):
    from skills.rest_api.version_1.code import run

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/')\ndef root(): return {'message': 'Hello'}"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "simple API"}, {})
    assert "code" in result
    assert "from fastapi import FastAPI" in result["code"]

@pytest.mark.asyncio
async def test_database_schema_success(mock_httpx_client):
    from skills.database_schema.version_1.code import run

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "CREATE TABLE users (id INT PRIMARY KEY, name TEXT);"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "users table"}, {})
    assert "sql" in result
    assert "CREATE TABLE users" in result["sql"]

@pytest.mark.asyncio
async def test_sql_query_success(mock_httpx_client):
    from skills.sql_query.version_1.code import run

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "SELECT * FROM users WHERE id = 1;"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "select user by id", "schema": "users(id, name)"}, {})
    assert "query" in result
    assert "SELECT * FROM users" in result["query"]

@pytest.mark.asyncio
async def test_authentication_success(mock_httpx_client):
    from skills.authentication.version_1.code import run

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "from fastapi.security import OAuth2PasswordBearer\noauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "JWT auth"}, {})
    assert "code" in result
    assert "OAuth2PasswordBearer" in result["code"]

@pytest.mark.asyncio
async def test_dockerfile_success(mock_httpx_client):
    from skills.dockerfile.version_1.code import run

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "FROM python:3.11\nCOPY . /app\nCMD ['python', 'app.py']"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "Python app"}, {})
    assert "dockerfile" in result
    assert "FROM python" in result["dockerfile"]

@pytest.mark.asyncio
async def test_github_actions_success(mock_httpx_client):
    from skills.github_actions.version_1.code import run

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "name: CI\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "CI workflow"}, {})
    assert "workflow" in result
    assert "name: CI" in result["workflow"]

@pytest.mark.asyncio
async def test_deploy_script_success(mock_httpx_client):
    from skills.deploy_script.version_1.code import run

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = AsyncMock(return_value={"response": "#!/bin/bash\necho 'Deploying...'"})
    mock_httpx_client.post.return_value = mock_response

    result = await run({"description": "bash deploy"}, {})
    assert "script" in result
    assert "#!/bin/bash" in result["script"]
