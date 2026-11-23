import json
import subprocess
import unittest
from unittest.mock import patch

from taxi.claude import ClaudeError, claude_args, extract_json, run_claude


def ok(result):
    return subprocess.CompletedProcess([], 0, json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": result}), "")


def reply(**kw):
    return subprocess.CompletedProcess([], kw.pop("code", 0), json.dumps(kw), "")


FAKE = lambda n: "C:/fake/claude.exe"


class ClaudeTests(unittest.TestCase):
    def test_args(self):
        self.assertEqual(claude_args([], 2), ["-p", "--model", "sonnet", "--output-format", "json", "--max-turns", "2",
            "--tools", "", "--permission-prompts", "none", "--safe-mode", "--strict-mcp-config", "--no-session-persistence"])
        self.assertEqual(claude_args(["WebSearch", "WebFetch"], 12), ["-p", "--model", "sonnet", "--output-format", "json", "--max-turns", "12",
            "--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch,WebFetch", "--permission-prompts", "none",
            "--safe-mode", "--strict-mcp-config", "--no-session-persistence"])

    @patch("taxi.claude.subprocess.run")
    def test_run_ok(self, run):
        run.return_value = ok("[1]")
        out = run_claude("PROMPT", ["-p"], 300, token="TOK", which=FAKE)
        self.assertEqual(out, "[1]")
        args, kw = run.call_args
        self.assertEqual(args[0], ["C:/fake/claude.exe", "-p"])
        self.assertEqual(kw["input"], "PROMPT")
        self.assertEqual((kw["timeout"], kw["encoding"]), (300, "utf-8"))
        self.assertEqual(kw["env"]["CLAUDE_CODE_OAUTH_TOKEN"], "TOK")

    @patch("taxi.claude.subprocess.run")
    def test_failures(self, run):
        run.return_value = reply(type="result", subtype="success", is_error=True, result="Failed to authenticate: expired")
        with self.assertRaisesRegex(ClaudeError, "Failed to authenticate"):
            run_claude("p", ["-p"], 5, which=FAKE)
        run.return_value = reply(type="result", subtype="error_max_turns", is_error=False, result="")
        with self.assertRaisesRegex(ClaudeError, "error_max_turns"):
            run_claude("p", ["-p"], 5, which=FAKE)
        run.side_effect = subprocess.TimeoutExpired("claude", 5)
        with self.assertRaisesRegex(ClaudeError, "timed out"):
            run_claude("p", ["-p"], 5, which=FAKE)
        run.side_effect = None
        run.return_value = subprocess.CompletedProcess([], 1, "boom, not json", "bad things")
        with self.assertRaises(ClaudeError):
            run_claude("p", ["-p"], 5, which=FAKE)
        with self.assertRaisesRegex(ClaudeError, "not found"):
            run_claude("p", ["-p"], 5, which=lambda n: None)

    def test_extract_json(self):
        self.assertEqual(extract_json('[{"a":1}]'), [{"a": 1}])
        self.assertEqual(extract_json('```json\n{"a":1}\n```'), {"a": 1})
        self.assertEqual(extract_json("Here you go:\n[1,2]\nThanks"), [1, 2])
        with self.assertRaises(ClaudeError):
            extract_json("no json here")
        self.assertEqual(extract_json("See [ICC](https://x.com/a) and [1]:\n{\"a\": 2}"), {"a": 2})

    def test_clean_strips_query_and_paths(self):
        from taxi.net import clean
        self.assertEqual(clean(r"a C:\Users\x\foo b"), "a <path> b")
        self.assertEqual(clean("see /home/bob/.cfg and /Users/me/x"), "see <path> and <path>")
        self.assertEqual(clean("https://a.com/home/q?k=S"), "https://a.com/home/q")

    @patch("taxi.claude.subprocess.run")
    def test_errors_hide_query_strings(self, run):
        run.return_value = reply(type="result", subtype="success", is_error=True, result="404 at https://api.x.com/v1?apikey=SECRET&b=1 sorry")
        with self.assertRaises(ClaudeError) as cm:
            run_claude("p", ["-p"], 5, which=FAKE)
        self.assertNotIn("SECRET", str(cm.exception))
        self.assertIn("https://api.x.com/v1", str(cm.exception))
        run.return_value = subprocess.CompletedProcess([], 1, "", "failed https://h.com/p?key=SECRET")
        with self.assertRaises(ClaudeError) as cm:
            run_claude("p", ["-p"], 5, which=FAKE)
        self.assertNotIn("SECRET", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
