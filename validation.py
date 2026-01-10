"""Input validation schemas and utilities."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing_extensions import Literal

from config import config
from errors import ValidationError


class GenerateRequest(BaseModel):
    """Request schema for prompt generation."""

    target: Literal["chatgpt", "claude_code"] = "chatgpt"
    task: str = Field(..., min_length=1, max_length=config.MAX_TASK_LENGTH)
    context: str = Field(default="", max_length=config.MAX_CONTEXT_LENGTH)
    constraints: str = Field(default="", max_length=config.MAX_FIELD_LENGTH)
    deliverables: str = Field(default="", max_length=config.MAX_FIELD_LENGTH)
    tone: str = Field(default="", max_length=config.MAX_TONE_LENGTH)

    @field_validator("task")
    @classmethod
    def task_not_empty(cls, v: str) -> str:
        """Ensure task is not just whitespace."""
        if not v.strip():
            raise ValueError("task cannot be empty")
        return v.strip()

    @field_validator("context", "constraints", "deliverables", "tone")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace from optional fields."""
        return v.strip()

    class Config:
        """Pydantic configuration."""

        str_strip_whitespace = True


def validate_generate_request(data: dict) -> GenerateRequest:
    """Validate and parse a generate request.

    Args:
        data: Raw request data dictionary

    Returns:
        Validated GenerateRequest object

    Raises:
        ValidationError: If validation fails
    """
    try:
        return GenerateRequest(**data)
    except Exception as e:
        # Convert pydantic validation errors to our custom error
        raise ValidationError(str(e)) from e
