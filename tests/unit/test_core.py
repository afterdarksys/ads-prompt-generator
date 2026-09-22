"""Unit tests for core prompt generation logic."""
from __future__ import annotations

import pytest

from pathlib import Path

from prompt_gen.core import PromptRequest, PromptTarget, generate_prompt, list_profiles


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

    def test_from_string_aliases(self):
        """Aliases normalize to the canonical target, including dotted model names."""
        assert PromptTarget.from_string("gpt-4o") == PromptTarget.CHATGPT
        assert PromptTarget.from_string("o3") == PromptTarget.GPT_REASONING
        assert PromptTarget.from_string("sonnet") == PromptTarget.CLAUDE_CHAT
        assert PromptTarget.from_string("grok-4") == PromptTarget.GROK
        assert PromptTarget.from_string("deepseek-r1") == PromptTarget.DEEPSEEK_R1
        assert PromptTarget.from_string("gemini-2.5") == PromptTarget.GEMINI

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

    @pytest.mark.parametrize("target", list(PromptTarget))
    def test_every_target_includes_the_task(self, target):
        """Each profile renders the task and its own optimization."""
        prompt = generate_prompt(PromptRequest(target=target, task="Ship the report"))
        assert "Ship the report" in prompt
        profile_rules = {
            PromptTarget.CHATGPT: "labeled section",
            PromptTarget.GPT_REASONING: "final answer only",
            PromptTarget.CLAUDE_CHAT: "<task>",
            PromptTarget.CLAUDE_CODE: "smallest correct change",
            PromptTarget.GEMINI: "constraints as requirements",
            PromptTarget.GROK: "second persona",
            PromptTarget.LLAMA: "Output contract:",
            PromptTarget.DEEPSEEK: "libraries, APIs, or tools",
            PromptTarget.DEEPSEEK_R1: "\\boxed{}",
            PromptTarget.MISTRAL: "Do not append alternatives",
        }
        assert profile_rules[target] in prompt

    def test_reasoning_prompts_do_not_request_a_trace(self):
        """Reasoning models already think. The prompt must not ask them to show it."""
        for target in (PromptTarget.GPT_REASONING, PromptTarget.DEEPSEEK_R1):
            prompt = generate_prompt(PromptRequest(target=target, task="Add 2 and 2"))
            lowered = prompt.lower()
            assert "you are" not in lowered
            assert "think step by step" not in lowered
            assert "explain your reasoning" not in lowered

    def test_ui_lists_every_profile(self):
        """The generator dropdown stays in lockstep with the profile registry."""
        html = (Path(__file__).resolve().parents[2] / "templates" / "index.html").read_text(encoding="utf-8")
        for profile in list_profiles():
            assert f'value="{profile.id}"' in html
            assert profile.summary in html
