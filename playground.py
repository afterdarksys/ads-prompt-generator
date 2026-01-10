"""Playground service for testing prompts with AI providers."""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx
from anthropic import Anthropic
from openai import OpenAI

from errors import ValidationError
from logging_config import get_logger

log = get_logger(__name__)


class PlaygroundProvider:
    """Base class for playground providers."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize provider with API key."""
        self.api_key = api_key

    async def execute(self, prompt: str, model: Optional[str] = None) -> dict[str, Any]:
        """Execute prompt and return response."""
        raise NotImplementedError


class AnthropicProvider(PlaygroundProvider):
    """Anthropic Claude provider."""

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    async def execute(self, prompt: str, model: Optional[str] = None) -> dict[str, Any]:
        """Execute prompt with Anthropic API."""
        if not self.api_key:
            raise ValidationError("Anthropic API key is required")

        start_time = time.time()

        try:
            client = Anthropic(api_key=self.api_key)

            response = client.messages.create(
                model=model or self.DEFAULT_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "response": response.content[0].text,
                "model": model or self.DEFAULT_MODEL,
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            log.error("anthropic_api_error", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
            }


class OpenAIProvider(PlaygroundProvider):
    """OpenAI ChatGPT provider."""

    DEFAULT_MODEL = "gpt-4o"

    async def execute(self, prompt: str, model: Optional[str] = None) -> dict[str, Any]:
        """Execute prompt with OpenAI API."""
        if not self.api_key:
            raise ValidationError("OpenAI API key is required")

        start_time = time.time()

        try:
            client = OpenAI(api_key=self.api_key)

            response = client.chat.completions.create(
                model=model or self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "response": response.choices[0].message.content,
                "model": model or self.DEFAULT_MODEL,
                "tokens_used": response.usage.total_tokens if response.usage else None,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            log.error("openai_api_error", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
            }


class OpenRouterProvider(PlaygroundProvider):
    """OpenRouter provider."""

    DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"

    async def execute(self, prompt: str, model: Optional[str] = None) -> dict[str, Any]:
        """Execute prompt with OpenRouter API."""
        if not self.api_key:
            raise ValidationError("OpenRouter API key is required")

        start_time = time.time()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model or self.DEFAULT_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=120.0,
                )
                response.raise_for_status()
                data = response.json()

                duration_ms = int((time.time() - start_time) * 1000)

                return {
                    "success": True,
                    "response": data["choices"][0]["message"]["content"],
                    "model": model or self.DEFAULT_MODEL,
                    "tokens_used": data.get("usage", {}).get("total_tokens"),
                    "duration_ms": duration_ms,
                }
        except Exception as e:
            log.error("openrouter_api_error", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
            }


class DetachedProvider(PlaygroundProvider):
    """Detached mode - no actual API calls."""

    async def execute(self, prompt: str, model: Optional[str] = None) -> dict[str, Any]:
        """Return prompt without executing."""
        return {
            "success": True,
            "response": None,
            "model": "detached",
            "tokens_used": None,
            "duration_ms": 0,
            "detached": True,
            "message": "Detached mode: Prompt generated but not executed",
        }


def get_provider(provider: str, api_key: Optional[str] = None) -> PlaygroundProvider:
    """Get provider instance."""
    providers = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "openrouter": OpenRouterProvider,
        "detached": DetachedProvider,
    }

    provider_class = providers.get(provider)
    if not provider_class:
        raise ValidationError(f"Unknown provider: {provider}")

    return provider_class(api_key=api_key)


# Model lists for each provider
PROVIDER_MODELS = {
    "anthropic": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
    ],
    "openrouter": [
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o",
        "google/gemini-pro-1.5",
        "meta-llama/llama-3.1-405b-instruct",
        "anthropic/claude-3-opus",
    ],
    "detached": ["detached"],
}
