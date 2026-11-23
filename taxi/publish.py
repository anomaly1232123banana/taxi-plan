import json
import os
import subprocess
from datetime import date
from pathlib import Path

GIT_TIMEOUT_S = 120
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


def publish(root: Path, today: date, run=subprocess.run) -> str:
    """Commit and push site/plan.json. The result never carries git output (a remote URL could hold a token)."""
    def step(argv: list[str]):
        try:
            return run(argv, cwd=root, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
        except (subprocess.TimeoutExpired, OSError):
            return None

    r = step(["git", "add", PLAN_PATH])
    if r is None or r.returncode != 0:
        return "error: add failed"
    r = step(["git", "diff", "--cached", "--quiet"])
    if r is None or r.returncode not in (0, 1):
        return "error: diff failed"
    if r.returncode == 0:
        return "no changes"
    for name, argv in (("commit", ["git", "commit", "-m", f"plan: {today.isoformat()}"]),
                       ("push", ["git", "push", "origin", BRANCH])):
        r = step(argv)
        if r is None or r.returncode != 0:
            return f"error: {name} failed"
    return "ok"
