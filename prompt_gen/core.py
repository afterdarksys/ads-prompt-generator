from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PromptTarget(str, Enum):
    CHATGPT = "chatgpt"
    GPT_REASONING = "gpt_reasoning"
    CLAUDE_CHAT = "claude_chat"
    CLAUDE_CODE = "claude_code"
    GEMINI = "gemini"
    GROK = "grok"
    LLAMA = "llama"
    DEEPSEEK = "deepseek"
    DEEPSEEK_R1 = "deepseek_r1"
    MISTRAL = "mistral"

    @classmethod
    def from_string(cls, raw: str) -> "PromptTarget":
        key = _normalize(raw)
        target = _ALIASES.get(key)
        if target is None:
            names = ", ".join(profile.id for profile in list_profiles())
            raise ValueError(f"unknown target: {raw!r} (expected {names})")
        return target


@dataclass(frozen=True)
class PromptRequest:
    target: PromptTarget
    task: str
    context: str = ""
    constraints: str = ""
    deliverables: str = ""
    tone: str = ""


@dataclass(frozen=True)
class ModelProfile:
    """How to shape a prompt for one model family.

    `structure` picks the layout:
    - plain: labeled sections and a response format
    - xml: tagged sections, which Claude parses more reliably
    - user_only: one user message, for models that reason internally
      or that degrade when given a system persona and examples
    """

    id: str
    label: str
    family: str
    summary: str
    role: str
    rules: tuple[str, ...]
    response_lines: tuple[str, ...]
    aliases: tuple[str, ...]
    structure: str = "plain"
    goal: str | None = None
    rules_heading: str = "Working rules"
    response_heading: str = "Response format"
    repeat_contract: str = ""


_DEFAULT_GOAL = (
    "Goal: Produce a clear, concise, unambiguous response.\n"
    "If anything is missing, ask only the minimum necessary clarifying questions first.\n"
    "Prefer actionable steps and concrete outputs over vague advice.\n"
)

_DIRECT_GOAL = (
    "Goal: Do the task as written.\n"
    "If a required detail is missing, name it in one line, then stop.\n"
    "Prefer the concrete deliverable over advice about it.\n"
)

_PROFILES: dict[PromptTarget, ModelProfile] = {
    PromptTarget.CHATGPT: ModelProfile(
        id="chatgpt",
        label="ChatGPT",
        family="OpenAI",
        summary="Labeled sections as delimiters, a fixed format, and clarifying questions only when required.",
        role="You are an expert assistant.",
        rules=(
            "Treat each labeled section as a delimiter. Do not mix constraints into the answer.",
            "Follow the response format exactly.",
            "Ask a clarifying question only when the task cannot be completed without it.",
        ),
        response_lines=(
            "First: any required clarifying questions (if needed).",
            "Then: the answer.",
            "End with: a short checklist of next actions.",
        ),
        aliases=("gpt", "chat", "gpt4", "gpt_4", "gpt_4o", "gpt_4_1", "gpt_5", "openai"),
    ),
    PromptTarget.GPT_REASONING: ModelProfile(
        id="gpt_reasoning",
        label="OpenAI reasoning (o-series)",
        family="OpenAI",
        summary="Short and direct. No chain-of-thought instructions; these models reason internally.",
        role="",
        structure="user_only",
        rules=(
            "Keep the request short. Do not add examples unless the task is ambiguous without one.",
            "Return the final answer only. Do not narrate the steps taken.",
            "Keep working until every success criterion is met.",
            "Treat each labeled section as the whole request.",
        ),
        response_lines=(
            "The final answer in the requested format.",
            "One line of assumptions, only if they change the answer.",
        ),
        response_heading="Answer format",
        aliases=("o1", "o3", "o4", "o1_mini", "o3_mini", "o4_mini", "reasoning", "openai_reasoning"),
    ),
    PromptTarget.CLAUDE_CHAT: ModelProfile(
        id="claude_chat",
        label="Claude",
        family="Anthropic",
        summary="XML-tagged sections Claude can tell apart, with direct instructions.",
        role="You are Claude.",
        structure="xml",
        goal="Be clear and direct. Produce exactly what <task> asks for.",
        rules=(
            "Do exactly what <task> asks.",
            "Use <context> as background and <constraints> as requirements.",
            "Be direct. Skip caveats the task did not ask for.",
            "Put the answer in the shape under <formatting>.",
        ),
        response_lines=(
            "The answer, with no preamble.",
            "One question only if a required detail is missing, then stop.",
        ),
        aliases=(
            "claude_chat",
            "claude_sonnet",
            "claude_opus",
            "claude_haiku",
            "sonnet",
            "opus",
            "haiku",
            "anthropic",
        ),
    ),
    PromptTarget.CLAUDE_CODE: ModelProfile(
        id="claude_code",
        label="Claude Code",
        family="Anthropic",
        summary="Smallest correct change, no invented APIs, plan then implement.",
        role="You are Claude Code acting as a senior pair programmer.",
        rules=(
            "Make the smallest correct change.",
            "Prefer implementing over describing.",
            "Read the relevant files before editing them.",
            "If you need codebase context, ask for files/paths or request a search.",
            "Do not invent APIs; be explicit about assumptions.",
        ),
        response_lines=(
            "Plan (2-5 milestones).",
            "Implementation details.",
            "Summary of what changed / what to do next.",
        ),
        aliases=("claude", "claudecode", "cc", "claude_code"),
    ),
    PromptTarget.GEMINI: ModelProfile(
        id="gemini",
        label="Gemini",
        family="Google",
        summary="Complete task first, hard constraints, and an exact output format.",
        role="You are Gemini.",
        goal=_DIRECT_GOAL,
        rules=(
            "Finish the task as stated. Do not widen it.",
            "Treat constraints as requirements, not suggestions.",
            "Match the output format exactly.",
            "When the task has several parts, do them in the order written.",
        ),
        response_lines=(
            "The deliverable.",
            "A short note only where a constraint forced a choice.",
        ),
        aliases=("gemini_pro", "gemini_flash", "gemini_2_5", "google"),
    ),
    PromptTarget.GROK: ModelProfile(
        id="grok",
        label="Grok",
        family="xAI",
        summary="Direct instructions and a fixed format, without an extra persona.",
        role="You are Grok.",
        goal=_DIRECT_GOAL,
        rules=(
            "Use the tone in the prompt. If none is set, be direct.",
            "Do not add a second persona or a side comment.",
            "Follow the response format and stop when it is complete.",
        ),
        response_lines=(
            "The answer in the requested format.",
            "Nothing after the deliverable.",
        ),
        aliases=("grok_3", "grok_4", "grok_4_7", "xai"),
    ),
    PromptTarget.LLAMA: ModelProfile(
        id="llama",
        label="Llama",
        family="Meta",
        summary="Short headings, and the output contract repeated at the end.",
        role="You are a careful assistant.",
        goal=_DIRECT_GOAL,
        rules=(
            "Follow the headings in order.",
            "Do not add a section that was not requested.",
            "If a required detail is missing, name it in one line and stop.",
        ),
        response_lines=(
            "Only the deliverable.",
        ),
        repeat_contract="Output contract: produce only the deliverable above.",
        aliases=("llama_3", "llama_4", "llama3", "meta", "meta_llama"),
    ),
    PromptTarget.DEEPSEEK: ModelProfile(
        id="deepseek",
        label="DeepSeek",
        family="DeepSeek",
        summary="A concrete spec and success criteria, with no unnamed dependencies.",
        role="You are DeepSeek.",
        goal=_DIRECT_GOAL,
        rules=(
            "Produce the deliverable itself, not a plan for producing it.",
            "Do not introduce libraries, APIs, or tools the constraints do not name.",
            "Match the requested format exactly.",
            "Satisfy every deliverable before you stop.",
        ),
        response_lines=(
            "The deliverable.",
            "A checklist of the deliverable items, marked done or not done.",
        ),
        aliases=("deepseek_v3", "deepseek_chat"),
    ),
    PromptTarget.DEEPSEEK_R1: ModelProfile(
        id="deepseek_r1",
        label="DeepSeek R1",
        family="DeepSeek",
        summary="One user message, no examples, and no step-by-step instruction. Math results go in \\boxed{}.",
        role="",
        structure="user_only",
        rules=(
            "State the task plainly. Do not add examples.",
            "Ask only for the final answer.",
            "If the task is math, put the final result in \\boxed{}.",
        ),
        response_lines=(
            "The final answer only.",
        ),
        response_heading="Answer format",
        aliases=("deepseek_reasoner", "r1"),
    ),
    PromptTarget.MISTRAL: ModelProfile(
        id="mistral",
        label="Mistral",
        family="Mistral",
        summary="Imperative instructions, constraints in order, and a hard stop.",
        role="Follow the instruction below.",
        goal=_DIRECT_GOAL,
        rules=(
            "Carry out the task as an instruction, not a conversation.",
            "Apply each constraint in the order written.",
            "Stop when the deliverable is complete. Do not append alternatives.",
        ),
        response_lines=(
            "The deliverable.",
            "No alternatives and no follow-on offer.",
        ),
        aliases=("mixtral", "mistral_large", "pixtral"),
    ),
}


def _normalize(raw: str) -> str:
    return (raw or "").strip().lower().replace("-", "_").replace(".", "_").replace(" ", "")


def _build_aliases() -> dict[str, PromptTarget]:
    mapping: dict[str, PromptTarget] = {}
    for target, profile in _PROFILES.items():
        keys = {profile.id, *profile.aliases}
        for key in keys:
            norm = _normalize(key)
            previous = mapping.get(norm)
            if previous is not None and previous != target:
                raise RuntimeError(f"alias {key!r} maps to both {previous.value} and {target.value}")
            mapping[norm] = target
    return mapping


_ALIASES = _build_aliases()


def list_profiles() -> list[ModelProfile]:
    return list(_PROFILES.values())


def get_profile(target: PromptTarget) -> ModelProfile:
    return _PROFILES[target]


def engineer_system(target: PromptTarget) -> str:
    """System prompt for a model that is writing a prompt for `target`."""
    profile = get_profile(target)
    layout = {
        "plain": "Use labeled sections (Task, Context, Constraints, Deliverables) and an explicit response format.",
        "xml": "Wrap each section in an XML tag and refer to those tags by name inside <instructions>.",
        "user_only": "Write a single user message. No persona preamble, no examples, and no chain-of-thought instruction.",
    }[profile.structure]
    rules = "\n".join(f"- {rule}" for rule in profile.rules)
    return (
        f"You are an expert prompt engineer. Write one prompt optimized for {profile.label}.\n"
        f"{layout}\n"
        f"Model-specific rules:\n{rules}\n"
        f"Why this shape: {profile.summary}\n"
        "Return only the finished prompt."
    )


def _compact_block(label: str, text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    return f"{label}:\n{cleaned}\n"


def _fields(req: PromptRequest) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for label, text in (
        ("Task", req.task),
        ("Context", req.context),
        ("Constraints", req.constraints),
        ("Deliverables", req.deliverables),
    ):
        cleaned = (text or "").strip()
        if cleaned:
            rows.append((label, cleaned))
    return rows


def _render_plain(profile: ModelProfile, req: PromptRequest) -> str:
    tone = (req.tone or "").strip()
    tone_line = f"Tone: {tone}\n" if tone else ""
    goal = profile.goal if profile.goal is not None else _DEFAULT_GOAL
    body = "".join(_compact_block(label, text) for label, text in _fields(req)).strip()
    rules = ""
    if profile.rules:
        bullets = "".join(f"- {rule}\n" for rule in profile.rules)
        rules = f"\n\n{profile.rules_heading}:\n{bullets}"
    response_gap = "\n" if profile.rules else "\n\n"
    response = response_gap + profile.response_heading + ":\n"
    response += "".join(f"- {line}\n" for line in profile.response_lines)
    contract = f"\n{profile.repeat_contract}\n" if profile.repeat_contract else ""
    role = f"{profile.role}\n" if profile.role else ""
    return (role + goal + tone_line + "\n" + body + rules + response + contract).strip()


def _render_xml(profile: ModelProfile, req: PromptRequest) -> str:
    tone = (req.tone or "").strip()
    instruction_lines = [profile.goal or "Be clear and direct."]
    if tone:
        instruction_lines.append(f"Tone: {tone}")
    instruction_lines.append(
        "Use each tagged section by its tag name. <context> is background. <constraints> are requirements."
    )
    instruction_lines.extend(f"- {rule}" for rule in profile.rules)
    parts = [profile.role, "", "<instructions>", "\n".join(instruction_lines), "</instructions>", ""]
    for label, text in _fields(req):
        tag = label.lower()
        parts.extend([f"<{tag}>", text, f"</{tag}>", ""])
    parts.append("<formatting>")
    parts.extend(f"- {line}" for line in profile.response_lines)
    parts.append("</formatting>")
    return "\n".join(parts).strip()


def _render_user_only(profile: ModelProfile, req: PromptRequest) -> str:
    tone = (req.tone or "").strip()
    chunks = [f"{label}:\n{text}" for label, text in _fields(req)]
    if tone:
        chunks.append(f"Tone:\n{tone}")
    if profile.rules:
        chunks.append(profile.rules_heading + ":\n" + "\n".join(f"- {rule}" for rule in profile.rules))
    chunks.append(profile.response_heading + ":\n" + "\n".join(f"- {line}" for line in profile.response_lines))
    if profile.repeat_contract:
        chunks.append(profile.repeat_contract)
    return "\n\n".join(chunks).strip()


_RENDERERS = {
    "plain": _render_plain,
    "xml": _render_xml,
    "user_only": _render_user_only,
}


def generate_prompt(req: PromptRequest) -> str:
    profile = get_profile(req.target)
    render = _RENDERERS[profile.structure]
    return render(profile, req)
