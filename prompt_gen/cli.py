from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prompt_gen.console import PromptGenConsole
from prompt_gen.core import PromptRequest, PromptTarget, generate_prompt


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prompt-gen")
    p.add_argument("--target", default="chatgpt", help="chatgpt | claude_code")
    p.add_argument("--task", default="", help="Required unless --console")
    p.add_argument("--context", default="")
    p.add_argument("--constraints", default="")
    p.add_argument("--deliverables", default="")
    p.add_argument("--tone", default="")
    p.add_argument("--json", dest="json_out", action="store_true", help="Output JSON {prompt: ...}")
    p.add_argument("--out", default="", help="Write prompt to a file")
    p.add_argument("--console", action="store_true", help="Drop into prompt-gen> interactive shell")
    return p


def _write_out(path: str, text: str) -> None:
    p = Path(path).expanduser()
    p.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.console:
        PromptGenConsole().cmdloop()
        return 0

    if not args.task.strip():
        print("error: --task is required unless --console", file=sys.stderr)
        return 2

    target = PromptTarget.from_string(args.target)
    prompt = generate_prompt(
        PromptRequest(
            target=target,
            task=args.task,
            context=args.context,
            constraints=args.constraints,
            deliverables=args.deliverables,
            tone=args.tone,
        )
    )

    if args.out:
        _write_out(args.out, prompt + "\n")

    if args.json_out:
        print(json.dumps({"prompt": prompt}, ensure_ascii=False))
    else:
        print(prompt)

    return 0
