import json
import logging
import os
import subprocess
import time
from datetime import date
from pathlib import Path

from taxi.net import clean

log = logging.getLogger(__name__)

GIT_TIMEOUT_S = 120
REPLACE_RETRY_S = 2
GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}  # a scheduled run has nobody to answer a prompt
PLAN_PATH = "site/plan.json"
BRANCH = "main"


def write_plan(plan: dict, path: Path) -> None:
    """Atomic UTF-8 write; one retry because OneDrive can briefly lock a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(plan, ensure_ascii=False, indent=1)
    for attempt in (1, 2):
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
            return
        except OSError:
            tmp.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(REPLACE_RETRY_S)


def publish(root: Path, today: date, run=subprocess.run) -> str:
    """Commit and push site/plan.json. The result never carries git output (a remote URL could hold a token)."""
    def step(argv: list[str]):
        try:
            return run(argv, cwd=root, capture_output=True, text=True, timeout=GIT_TIMEOUT_S,
                       stdin=subprocess.DEVNULL, env={**os.environ, **GIT_ENV})
        except (subprocess.TimeoutExpired, OSError) as e:
            log.warning("%s: %s", argv[1], type(e).__name__)
            return None

    r = step(["git", "add", PLAN_PATH])
    if r is None or r.returncode != 0:
        return "error: add failed"
    r = step(["git", "diff", "--cached", "--quiet", "--", PLAN_PATH])
    if r is None or r.returncode not in (0, 1):
        return "error: diff failed"
    if r.returncode == 0:
        return "no changes"
    for name, argv in (("commit", ["git", "commit", "-m", f"plan: {today.isoformat()}", "--", PLAN_PATH]),  # only the plan, never staged dev work
                       ("push", ["git", "push", "origin", f"HEAD:{BRANCH}"])):
        r = step(argv)
        if r is None or r.returncode != 0:
            if r is not None:
                log.warning("git %s failed: %s", name, clean((r.stderr or "").strip()))
            return f"error: {name} failed"
    return "ok"
