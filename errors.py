"""Custom exceptions for the application."""
from __future__ import annotations


class PromptGeneratorError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ValidationError(PromptGeneratorError):
    """Input validation failed."""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class RateLimitError(PromptGeneratorError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, status_code=429)


class ConfigurationError(PromptGeneratorError):
    """Application configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(message, status_code=500)


class CacheError(PromptGeneratorError):
    """Cache operation failed."""

    def __init__(self, message: str):
        super().__init__(message, status_code=500)
