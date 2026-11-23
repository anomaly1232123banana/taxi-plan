import json
import os
import re
import shutil
import subprocess
from typing import Any

from taxi.net import clean


class ClaudeError(Exception):
    pass


def _clean(text: str) -> str:
    return clean(text)[:200]


def claude_args(tools: list[str], max_turns: int) -> list[str]:
    allow = ["--tools", ",".join(tools)] + (["--allowedTools", ",".join(tools)] if tools else [])
    return ["-p", "--model", "sonnet", "--output-format", "json", "--max-turns", str(max_turns), *allow,
            "--permission-prompts", "none", "--safe-mode", "--strict-mcp-config", "--no-session-persistence"]


def run_claude(prompt: str, args: list[str], timeout_s: int, token: str | None = None, which=shutil.which) -> str:
    exe = which("claude")
    if not exe:
        raise ClaudeError("claude CLI not found")
    env = dict(os.environ)
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    try:
        p = subprocess.run([exe] + args, input=prompt, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout_s, env=env)
    except subprocess.TimeoutExpired:
        raise ClaudeError(f"claude timed out after {timeout_s}s") from None
    except OSError as e:
        raise ClaudeError(f"claude could not start: {e}") from None
    try:
        out = json.loads(p.stdout)
    except ValueError:
        raise ClaudeError(f"claude exited {p.returncode} without JSON: {_clean((p.stderr or p.stdout).strip())}") from None
    if not isinstance(out, dict):
        raise ClaudeError("claude returned unexpected JSON")
    # An auth failure arrives as subtype "success" with is_error true.
    if out.get("is_error") or out.get("subtype") != "success":
        raise ClaudeError(_clean(str(out.get("result") or out.get("subtype") or "claude failed")))
    return str(out.get("result", ""))


def extract_json(text: str) -> Any:
    dec, first = json.JSONDecoder(), None
    for m in re.finditer(r"[\[{]", text):
        try:
            v = dec.raw_decode(text[m.start():])[0]
        except ValueError:
            continue
        # prose can hold stray "[1]" or links before the real payload: prefer objects / lists of objects
        if isinstance(v, dict) or (isinstance(v, list) and v and all(isinstance(i, dict) for i in v)):
            return v
        first = [v] if first is None else first
    if first is None:
        raise ClaudeError("no JSON in reply")
    return first[0]
