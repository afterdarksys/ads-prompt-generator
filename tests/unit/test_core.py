"""Unit tests for core prompt generation logic."""
from __future__ import annotations

import pytest

from prompt_gen.core import PromptRequest, PromptTarget, generate_prompt


class TestPromptTarget:
    """Test PromptTarget enum."""

    def test_from_string_chatgpt(self):
        """Test parsing ChatGPT target aliases."""
        assert PromptTarget.from_string("chatgpt") == PromptTarget.CHATGPT
        assert PromptTarget.from_string("gpt") == PromptTarget.CHATGPT
        assert PromptTarget.from_string("chat") == PromptTarget.CHATGPT
        assert PromptTarget.from_string("ChatGPT") == PromptTarget.CHATGPT

    def test_from_string_claude_code(self):
        """Test parsing Claude Code target aliases."""
        assert PromptTarget.from_string("claude_code") == PromptTarget.CLAUDE_CODE
        assert PromptTarget.from_string("claude") == PromptTarget.CLAUDE_CODE
        assert PromptTarget.from_string("claudecode") == PromptTarget.CLAUDE_CODE
        assert PromptTarget.from_string("cc") == PromptTarget.CLAUDE_CODE

    def test_from_string_invalid(self):
        """Test invalid target raises ValueError."""
        with pytest.raises(ValueError, match="unknown target"):
            PromptTarget.from_string("invalid")

        with pytest.raises(ValueError, match="unknown target"):
            PromptTarget.from_string("")


class TestGeneratePrompt:
    """Test prompt generation."""

    def test_generate_chatgpt_basic(self):
        """Test basic ChatGPT prompt generation."""
        req = PromptRequest(
            target=PromptTarget.CHATGPT,
            task="Test task",
        )
        prompt = generate_prompt(req)

        assert "Test task" in prompt
        assert "expert assistant" in prompt
        assert "clarifying questions" in prompt

    def test_generate_chatgpt_with_all_fields(self):
        """Test ChatGPT prompt with all fields."""
        req = PromptRequest(
            target=PromptTarget.CHATGPT,
            task="Test task",
            context="Test context",
            constraints="Test constraints",
            deliverables="Test deliverables",
            tone="concise",
        )
        prompt = generate_prompt(req)

        assert "Test task" in prompt
        assert "Test context" in prompt
        assert "Test constraints" in prompt
        assert "Test deliverables" in prompt
        assert "Tone: concise" in prompt

    def test_generate_claude_code_basic(self):
        """Test basic Claude Code prompt generation."""
        req = PromptRequest(
            target=PromptTarget.CLAUDE_CODE,
            task="Test task",
        )
        prompt = generate_prompt(req)

        assert "Test task" in prompt
        assert "Claude Code" in prompt
        assert "pair programmer" in prompt

    def test_generate_claude_code_with_all_fields(self):
        """Test Claude Code prompt with all fields."""
        req = PromptRequest(
            target=PromptTarget.CLAUDE_CODE,
            task="Test task",
            context="Test context",
            constraints="Test constraints",
            deliverables="Test deliverables",
            tone="direct",
        )
        prompt = generate_prompt(req)

        assert "Test task" in prompt
        assert "Test context" in prompt
        assert "Test constraints" in prompt
        assert "Test deliverables" in prompt
        assert "Tone: direct" in prompt

    def test_empty_optional_fields_excluded(self):
        """Test that empty optional fields are not included."""
        req = PromptRequest(
            target=PromptTarget.CHATGPT,
            task="Test task",
            context="",
            constraints="",
            deliverables="",
            tone="",
        )
        prompt = generate_prompt(req)

        assert "Context:" not in prompt
        assert "Constraints:" not in prompt
        assert "Deliverables:" not in prompt
        assert "Tone:" not in prompt
