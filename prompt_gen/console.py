from __future__ import annotations

import cmd
import json
import shlex
from pathlib import Path

import pyperclip

from prompt_gen.core import PromptRequest, PromptTarget, generate_prompt, list_profiles


class PromptGenConsole(cmd.Cmd):
    intro = "Prompt generator console. Type help or ? to list commands."
    prompt = "prompt-gen> "

    def __init__(self):
        super().__init__()
        self._state = {
            "target": "chatgpt",
            "task": "",
            "context": "",
            "constraints": "",
            "deliverables": "",
            "tone": "",
        }
        self._last_prompt = ""

    def do_new(self, arg: str) -> None:
        self._state.update(
            {
                "target": "chatgpt",
                "task": "",
                "context": "",
                "constraints": "",
                "deliverables": "",
                "tone": "",
            }
        )
        self._last_prompt = ""
        print("ok")

    def do_fields(self, arg: str) -> None:
        print("target, task, context, constraints, deliverables, tone")

    def do_set(self, arg: str) -> None:
        parts = shlex.split(arg)
        if len(parts) < 2:
            print("usage: set <field> <value>")
            return
        field = parts[0]
        value = " ".join(parts[1:])
        if field not in self._state:
            print(f"unknown field: {field}")
            return
        self._state[field] = value
        print("ok")

    def do_targets(self, arg: str) -> None:
        for profile in list_profiles():
            print(f"{profile.id}\t{profile.label}")
            print(f"  {profile.summary}")

    def do_target(self, arg: str) -> None:
        raw = (arg or "").strip()
        if not raw:
            print(self._state["target"])
            return
        try:
            PromptTarget.from_string(raw)
        except ValueError as e:
            print(str(e))
            return
        self._state["target"] = raw
        print("ok")

    def do_show(self, arg: str) -> None:
        print(json.dumps(self._state, indent=2, ensure_ascii=False))

    def do_generate(self, arg: str) -> None:
        task = (self._state.get("task") or "").strip()
        if not task:
            print("error: task is empty (use: set task \"...\")")
            return
        target = PromptTarget.from_string(self._state.get("target") or "chatgpt")
        self._last_prompt = generate_prompt(
            PromptRequest(
                target=target,
                task=self._state.get("task") or "",
                context=self._state.get("context") or "",
                constraints=self._state.get("constraints") or "",
                deliverables=self._state.get("deliverables") or "",
                tone=self._state.get("tone") or "",
            )
        )
        print(self._last_prompt)

    def do_copy(self, arg: str) -> None:
        if not self._last_prompt:
            print("error: nothing generated yet (run: generate)")
            return
        try:
            pyperclip.copy(self._last_prompt)
        except Exception as e:
            print(f"error: failed to copy to clipboard: {e}")
            return
        print("ok")

    def do_save(self, arg: str) -> None:
        path = (arg or "").strip()
        if not path:
            print("usage: save <path>")
            return
        if not self._last_prompt:
            print("error: nothing generated yet (run: generate)")
            return
        p = Path(path).expanduser()
        p.write_text(self._last_prompt + "\n", encoding="utf-8")
        print("ok")

    def do_load(self, arg: str) -> None:
        path = (arg or "").strip()
        if not path:
            print("usage: load <path>")
            return
        p = Path(path).expanduser()
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            print("error: expected a JSON object")
            return
        for k in self._state.keys():
            if k in data and isinstance(data[k], str):
                self._state[k] = data[k]
        self._last_prompt = ""
        print("ok")

    def do_export(self, arg: str) -> None:
        path = (arg or "").strip()
        if not path:
            print("usage: export <path>")
            return
        p = Path(path).expanduser()
        p.write_text(json.dumps(self._state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("ok")

    def do_exit(self, arg: str) -> bool:
        return True

    def do_quit(self, arg: str) -> bool:
        return True

    def do_EOF(self, arg: str) -> bool:
        print()
        return True
