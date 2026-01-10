from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PromptTarget(str, Enum):
    CHATGPT = "chatgpt"
    CLAUDE_CODE = "claude_code"

    @classmethod
    def from_string(cls, raw: str) -> "PromptTarget":
        value = (raw or "").strip().lower()
        aliases = {
            "gpt": cls.CHATGPT,
            "chat": cls.CHATGPT,
            "chatgpt": cls.CHATGPT,
            "claude": cls.CLAUDE_CODE,
            "claudecode": cls.CLAUDE_CODE,
            "claude_code": cls.CLAUDE_CODE,
            "cc": cls.CLAUDE_CODE,
        }
        if value in aliases:
            return aliases[value]
        raise ValueError(f"unknown target: {raw!r} (expected chatgpt or claude_code)")


@dataclass(frozen=True)
class PromptRequest:
    target: PromptTarget
    task: str
    context: str = ""
    constraints: str = ""
    deliverables: str = ""
    tone: str = ""


def _compact_block(label: str, text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    return f"{label}:\n{t}\n"


def generate_prompt(req: PromptRequest) -> str:
    tone = (req.tone or "").strip()
    tone_line = f"Tone: {tone}\n" if tone else ""

    common = (
        "Goal: Produce a clear, concise, unambiguous response.\n"
        "If anything is missing, ask only the minimum necessary clarifying questions first.\n"
        "Prefer actionable steps and concrete outputs over vague advice.\n"
    )

    body = (
        _compact_block("Task", req.task)
        + _compact_block("Context", req.context)
        + _compact_block("Constraints", req.constraints)
        + _compact_block("Deliverables", req.deliverables)
    ).strip()

    if req.target == PromptTarget.CHATGPT:
        return (
            "You are an expert assistant.\n"
            + common
            + tone_line
            + "\n"
            + body
            + "\n\n"
            + "Response format:\n"
            + "- First: any required clarifying questions (if needed).\n"
            + "- Then: the answer.\n"
            + "- End with: a short checklist of next actions.\n"
        ).strip()

    return (
        "You are Claude Code acting as a senior pair programmer.\n"
        + common
        + tone_line
        + "\n"
        + body
        + "\n\n"
        + "Working rules:\n"
        + "- Make the smallest correct change.\n"
        + "- Prefer implementing over describing.\n"
        + "- If you need codebase context, ask for files/paths or request a search.\n"
        + "- Do not invent APIs; be explicit about assumptions.\n"
        + "\n"
        + "Response format:\n"
        + "- Plan (2-5 milestones).\n"
        + "- Implementation details.\n"
        + "- Summary of what changed / what to do next.\n"
    ).strip()
