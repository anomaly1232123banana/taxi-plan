import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


def _empty() -> dict:
    return {"estimates": {}, "gapfill": {}}


def load_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("estimates"), dict) and isinstance(data.get("gapfill"), dict):
            return data
        raise ValueError("unexpected shape")
    except FileNotFoundError:
        return _empty()
    except (OSError, ValueError) as e:
        log.warning("estimate cache unreadable (%s); moved to .bad", e)
        try:
            os.replace(path, path.with_name(path.name + ".bad"))
        except OSError:
            log.warning("could not move bad cache aside")
        return _empty()


def save_cache(cache: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def prune(cache: dict, today: date, keep_days: int) -> None:
    cutoff = (today - timedelta(days=keep_days)).isoformat()
    for k in [k for k, v in cache["estimates"].items() if v.get("seen", "") < cutoff]:
        del cache["estimates"][k]
    for k in [k for k, v in cache["gapfill"].items() if v["event"].get("date", "") < today.isoformat()]:
        del cache["gapfill"][k]
