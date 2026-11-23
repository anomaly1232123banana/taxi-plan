import json
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from taxi.publish import publish, write_plan

TODAY = date(2026, 11, 23)


class Runner:
    def __init__(self, **codes):
        self.codes, self.argvs = codes, []

    def __call__(self, argv, **kw):
        self.argvs.append(argv)
        assert kw["capture_output"] and kw["text"] and kw["timeout"] == 120 and kw["cwd"]
        assert kw["stdin"] == subprocess.DEVNULL
        assert kw["env"]["GIT_TERMINAL_PROMPT"] == "0" and kw["env"]["GCM_INTERACTIVE"] == "never"
        return subprocess.CompletedProcess(argv, self.codes.get(argv[1], 0), "", "")


class TestPublish(unittest.TestCase):
    def test_publish_commits_and_pushes(self):
        r = Runner(diff=1)
        self.assertEqual(publish(Path("."), TODAY, run=r), "ok")
        self.assertEqual(r.argvs, [["git", "add", "site/plan.json"], ["git", "diff", "--cached", "--quiet"],
                                   ["git", "commit", "-m", "plan: 2026-11-23", "--", "site/plan.json"],
                                   ["git", "push", "origin", "HEAD:main"]])

    def test_no_changes(self):
        r = Runner(diff=0)
        self.assertEqual(publish(Path("."), TODAY, run=r), "no changes")
        self.assertEqual(len(r.argvs), 2)

    def test_push_fails(self):
        r = Runner(diff=1, push=128)
        self.assertEqual(publish(Path("."), TODAY, run=r), "error: push failed")
        self.assertEqual(len(r.argvs), 4)

    def test_add_fails_and_timeout(self):
        self.assertEqual(publish(Path("."), TODAY, run=Runner(add=128)), "error: add failed")

        def hang(argv, **kw):
            raise subprocess.TimeoutExpired(argv, 120)
        self.assertEqual(publish(Path("."), TODAY, run=hang), "error: add failed")

    def test_push_failure_logs_stderr_without_query(self):
        def r(argv, **kw):
            return subprocess.CompletedProcess(argv, {"push": 128, "diff": 1}.get(argv[1], 0), "",
                                               "fatal: https://h.example/r.git?token=SECRET unreachable")
        with self.assertLogs("taxi.publish", "WARNING") as cm:
            self.assertEqual(publish(Path("."), TODAY, run=r), "error: push failed")
        out = " ".join(cm.output)
        self.assertIn("unreachable", out)
        self.assertNotIn("SECRET", out)

    def test_write_plan_retries_after_lock(self):
        with tempfile.TemporaryDirectory() as d, patch("taxi.publish.time.sleep") as sl, \
                patch("taxi.publish.os.replace", side_effect=[PermissionError("locked"), None]) as rp:
            write_plan({"a": 1}, Path(d) / "plan.json")
        self.assertEqual(rp.call_count, 2)
        sl.assert_called_once_with(2)

    def test_write_plan_atomic(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "site" / "plan.json"
            write_plan({"a": "✓"}, p)
            self.assertIn("✓", p.read_text("utf-8"))
            self.assertEqual(json.loads(p.read_text("utf-8")), {"a": "✓"})
            write_plan({"a": 2}, p)
            self.assertEqual(json.loads(p.read_text("utf-8")), {"a": 2})
            self.assertEqual([f.name for f in p.parent.iterdir()], ["plan.json"])


if __name__ == "__main__":
    unittest.main()
