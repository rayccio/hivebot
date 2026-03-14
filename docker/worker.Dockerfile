FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy the entire worker directory (includes main.py, tool_executor.py, etc.)
COPY worker/ .

# Set Python to run unbuffered
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
