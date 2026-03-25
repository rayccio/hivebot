import pytest
import asyncio
import asyncpg
import os
from pathlib import Path

# Override log directory to prevent permission issues
os.environ['HIVEBOT_LOG_DIR'] = str(Path(__file__).parent / "test_logs")

# Database settings – same as the test environment
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_USER = os.getenv("POSTGRES_USER", "hivebot")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "hivebot")
POSTGRES_DB = os.getenv("POSTGRES_DB", "hivebot_test")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}"


def create_tables():
    """Create all tables needed for worker tests (synchronous)."""
    async def _create():
        conn = await asyncpg.connect(DATABASE_URL)

        # Create skills table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id VARCHAR PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create skill_versions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_versions (
                id VARCHAR PRIMARY KEY,
                skill_id VARCHAR NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create tasks table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id VARCHAR PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create agents table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id VARCHAR PRIMARY KEY,
                data JSONB NOT NULL,
                container_id VARCHAR,
                status VARCHAR DEFAULT 'IDLE',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create goals table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id VARCHAR PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create task_edges table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS task_edges (
                from_task VARCHAR NOT NULL,
                to_task VARCHAR NOT NULL,
                PRIMARY KEY (from_task, to_task)
            )
        """)

        # Create layer_roles table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS layer_roles (
                layer_id VARCHAR NOT NULL,
                role_name VARCHAR NOT NULL,
                soul_md TEXT NOT NULL,
                identity_md TEXT NOT NULL,
                tools_md TEXT NOT NULL,
                role_type VARCHAR DEFAULT 'specialized',
                priority INT DEFAULT 0,
                PRIMARY KEY (layer_id, role_name)
            )
        """)

        # Create layers table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS layers (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                description TEXT,
                version VARCHAR NOT NULL,
                author VARCHAR,
                dependencies JSONB DEFAULT '[]',
                enabled BOOLEAN DEFAULT TRUE,
                lifecycle JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create loop_handlers table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS loop_handlers (
                id VARCHAR PRIMARY KEY,
                layer_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                class_path VARCHAR NOT NULL
            )
        """)

        # Create a core layer if not exists (for default loop handler)
        await conn.execute("""
            INSERT INTO layers (id, name, description, version, author, enabled)
            VALUES ('core', 'HiveBot Core', 'Core system', '1.0.0', 'system', true)
            ON CONFLICT (id) DO NOTHING
        """)

        # Insert default loop handler
        await conn.execute("""
            INSERT INTO loop_handlers (id, layer_id, name, class_path)
            VALUES ('default', 'core', 'default', 'worker.loop_handler.DefaultLoopHandler')
            ON CONFLICT (id) DO NOTHING
        """)

        await conn.close()

    # Run the async function synchronously
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_create())


# Session-scoped fixture that runs once before any tests
@pytest.fixture(scope="session", autouse=True)
def setup_db():
    create_tables()
    yield
    # Optionally drop tables after tests? Not necessary for CI.
