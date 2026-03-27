import os
from pydantic import Field, PrivateAttr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from pathlib import Path
from .secrets import SecretsManager

class Settings(BaseSettings):
    APP_NAME: str = "HiveBot Orchestrator"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: str = "http://localhost,http://localhost:3000"

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # PostgreSQL settings
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "hivebot"
    POSTGRES_PASSWORD: str = "hivebot"
    POSTGRES_DB: str = "hivebot"

    DOCKER_NETWORK: str = "hivebot_network"

    # Base data directory (can be overridden by env)
    HIVEBOT_DATA: str = Field(default_factory=lambda: os.getenv('HIVEBOT_DATA', '/app/data'))

    # Default UID for agent containers
    DEFAULT_AGENT_UID: str = "10001"

    # File upload limits
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB

    # Scheduler flags (NEW)
    SCHEDULER_ENABLED: bool = False
    SCHEDULER_AUTO_ASSIGN: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def SECRETS_DIR(self) -> Path:
        return Path(self.HIVEBOT_DATA) / "secrets"

    @property
    def AGENTS_DIR(self) -> Path:
        return Path(self.HIVEBOT_DATA) / "agents"

    @property
    def GLOBAL_FILES_DIR(self) -> Path:
        return Path(self.HIVEBOT_DATA) / "global_files"

    @property
    def DATA_DIR(self) -> Path:
        return Path(self.HIVEBOT_DATA) / "data"

    @property
    def LAYERS_DIR(self) -> Path:
        return Path("/app/layers")

    _secrets: SecretsManager = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        self.AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.GLOBAL_FILES_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        # LAYERS_DIR is not created here – it's mounted from the host

        self._secrets = SecretsManager(
            secrets_path=self.SECRETS_DIR / "secrets.enc",
            master_key_path=self.SECRETS_DIR / "master.key"
        )

    @property
    def secrets(self) -> SecretsManager:
        return self._secrets

    @property
    def cors_origins(self) -> List[str]:
        if not self.BACKEND_CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
