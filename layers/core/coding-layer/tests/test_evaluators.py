import pytest
from training.evaluators import WebEvaluator, BackendEvaluator, DatabaseEvaluator

@pytest.mark.asyncio
async def test_web_evaluator_good():
    evaluator = WebEvaluator()
    agent_output = """
    <!DOCTYPE html>
    <html>
    <head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body><style>body{color:red;}</style><script>console.log('hi');</script></body>
    </html>
    """
    score, message = await evaluator.evaluate(agent_output, None, {})
    assert score >= 0.9
    assert "Good job" in message

@pytest.mark.asyncio
async def test_web_evaluator_missing():
    evaluator = WebEvaluator()
    agent_output = "<div>Hello</div>"
    score, message = await evaluator.evaluate(agent_output, None, {})
    assert score < 0.5
    assert "Missing" in message

@pytest.mark.asyncio
async def test_backend_evaluator_good():
    evaluator = BackendEvaluator()
    agent_output = """
    from fastapi import FastAPI
    app = FastAPI()
    @app.get('/')
    def root():
        return {"message": "Hello"}
    """
    score, message = await evaluator.evaluate(agent_output, None, {})
    assert score >= 0.9

@pytest.mark.asyncio
async def test_database_evaluator_good():
    evaluator = DatabaseEvaluator()
    agent_output = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name VARCHAR(100)
    );
    """
    score, message = await evaluator.evaluate(agent_output, None, {})
    assert score >= 0.8
