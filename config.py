"""Application configuration management."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Application configuration with environment variable support."""

    # Server configuration
    HOST: str = os.getenv("FLASK_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("FLASK_PORT", "5000"))
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    ENV: str = os.getenv("FLASK_ENV", "production")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", "1048576"))  # 1MB

    # Input limits
    MAX_TASK_LENGTH: int = int(os.getenv("MAX_TASK_LENGTH", "10240"))  # 10KB
    MAX_CONTEXT_LENGTH: int = int(os.getenv("MAX_CONTEXT_LENGTH", "51200"))  # 50KB
    MAX_FIELD_LENGTH: int = int(os.getenv("MAX_FIELD_LENGTH", "51200"))  # 50KB
    MAX_TONE_LENGTH: int = int(os.getenv("MAX_TONE_LENGTH", "256"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # json or text

    # Redis (for caching)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() in ("true", "1", "yes")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    # Monitoring
    METRICS_ENABLED: bool = os.getenv("METRICS_ENABLED", "true").lower() in ("true", "1", "yes")

    # CORS
    CORS_ORIGINS: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(",")
    )

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./prompt_generator.db")

    # Encryption (for API keys)
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", SECRET_KEY)

    @classmethod
    def validate(cls) -> None:
        """Validate configuration values."""
        config = cls()

        if config.ENV == "production" and config.SECRET_KEY == "change-me-in-production":
            raise ValueError("SECRET_KEY must be set in production")

        if config.DEBUG and config.ENV == "production":
            raise ValueError("DEBUG must be False in production")

        if config.MAX_CONTENT_LENGTH < 1024:
            raise ValueError("MAX_CONTENT_LENGTH must be at least 1KB")


# Singleton instance
config = Config()
