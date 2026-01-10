"""Database models for prompt library and API key management."""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from cryptography.fernet import Fernet
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from config import config

Base = declarative_base()


class SavedPrompt(Base):
    """Saved prompt in the library."""

    __tablename__ = "saved_prompts"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target = Column(String(50), nullable=False)
    task = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    constraints = Column(Text, nullable=True)
    deliverables = Column(Text, nullable=True)
    tone = Column(String(255), nullable=True)
    generated_prompt = Column(Text, nullable=True)
    tags = Column(String(500), nullable=True)  # Comma-separated
    is_favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "target": self.target,
            "task": self.task,
            "context": self.context,
            "constraints": self.constraints,
            "deliverables": self.deliverables,
            "tone": self.tone,
            "generated_prompt": self.generated_prompt,
            "tags": self.tags.split(",") if self.tags else [],
            "is_favorite": self.is_favorite,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class APIKey(Base):
    """Stored API key for AI providers."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)  # anthropic, openai, openrouter
    key_name = Column(String(255), nullable=False)
    encrypted_key = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    def to_dict(self, include_key: bool = False) -> dict:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "provider": self.provider,
            "key_name": self.key_name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
        if include_key:
            result["key_preview"] = f"...{self.encrypted_key[-8:]}"
        return result


class PlaygroundSession(Base):
    """Playground execution session."""

    __tablename__ = "playground_sessions"

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)  # anthropic, openai, openrouter, detached
    model = Column(String(100), nullable=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "provider": self.provider,
            "model": self.model,
            "prompt": self.prompt,
            "response": self.response,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Database setup
engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in config.DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Encryption utilities
class KeyEncryption:
    """API key encryption/decryption."""

    def __init__(self):
        """Initialize with encryption key from config."""
        # In production, store this securely (e.g., AWS KMS, HashiCorp Vault)
        encryption_key = config.ENCRYPTION_KEY.encode()
        # Ensure key is proper length for Fernet
        if len(encryption_key) < 32:
            # Pad key to 32 bytes
            encryption_key = encryption_key.ljust(32, b"0")
        # Convert to base64 for Fernet
        import base64

        self.cipher = Fernet(base64.urlsafe_b64encode(encryption_key[:32]))

    def encrypt(self, plaintext: str) -> str:
        """Encrypt API key."""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt API key."""
        return self.cipher.decrypt(ciphertext.encode()).decode()


key_encryption = KeyEncryption()
