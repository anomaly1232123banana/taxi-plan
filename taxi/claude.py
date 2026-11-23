import json
import os
import shutil
import subprocess
from typing import Any


class ClaudeError(Exception):
    pass


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
        raise ClaudeError(f"claude exited {p.returncode} without JSON: {(p.stderr or p.stdout).strip()[:200]}") from None
    if not isinstance(out, dict):
        raise ClaudeError("claude returned unexpected JSON")
    # An auth failure arrives as subtype "success" with is_error true.
    if out.get("is_error") or out.get("subtype") != "success":
        raise ClaudeError(str(out.get("result") or out.get("subtype") or "claude failed")[:200])
    return str(out.get("result", ""))


def extract_json(text: str) -> Any:
    i = min((k for k in (text.find("["), text.find("{")) if k >= 0), default=-1)
    if i < 0:
        raise ClaudeError("no JSON in reply")
    try:
        return json.JSONDecoder().raw_decode(text[i:])[0]
    except ValueError:
        raise ClaudeError("reply JSON did not parse") from None
