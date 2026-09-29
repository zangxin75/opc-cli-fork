"""Unit tests for plan.py (mocks claude CLI subprocess)."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from card.plan import plan_cards, _extract_json  # noqa: E402


VALID = {
    "theme": "dark-purple-gold",
    "cards": [{
        "id": "core", "title": "核心观点<em>测试</em>",
        "bullets": ["要点"],
    }],
    "timing": [{"card": "core", "keyword": "核心观点", "duration": 4.0}],
}


def _cli_response(payload):
    return json.dumps({"type": "result", "result": payload, "is_error": False})


class ExtractJsonTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(_extract_json('{"a":1}')["a"], 1)

    def test_fenced(self):
        self.assertEqual(_extract_json('```json\n{"a":1}\n```')["a"], 1)


class PlanCardsTests(unittest.TestCase):
    @patch("card.plan.subprocess.run")
    def test_happy_path(self, run):
        run.return_value.stdout = _cli_response(json.dumps(VALID, ensure_ascii=False))
        plan = plan_cards("口播稿" * 50)
        self.assertEqual(plan["cards"][0]["id"], "core")

    @patch("card.plan.subprocess.run")
    def test_cli_error_reported(self, run):
        run.return_value.stdout = json.dumps(
            {"result": "quota exceeded", "is_error": True})
        with self.assertRaises(RuntimeError) as ctx:
            plan_cards("稿")
        self.assertIn("quota", str(ctx.exception))

    @patch("card.plan.subprocess.run")
    def test_retry_then_success(self, run):
        bad = {"cards": [], "timing": [{"card": "ghost", "keyword": "k"}]}
        good = _cli_response(json.dumps(VALID, ensure_ascii=False))
        run.side_effect = [
            type("P", (), {"stdout": _cli_response(json.dumps(bad)),
                           "stderr": ""})(),
            type("P", (), {"stdout": good, "stderr": ""})(),
        ]
        plan = plan_cards("稿", raw_dump="/tmp/plan-test-dump.txt")
        self.assertEqual(len(plan["cards"]), 1)
        self.assertEqual(run.call_count, 2)

    @patch("card.plan.subprocess.run")
    def test_all_retries_fail_dumps_raw(self, run):
        run.return_value = type("P", (), {
            "stdout": _cli_response("not json at all"),
            "stderr": ""})()
        with self.assertRaises(RuntimeError):
            plan_cards("稿", raw_dump="/tmp/plan-test-dump2.txt")
        self.assertEqual(run.call_count, 2)
        self.assertTrue(Path("/tmp/plan-test-dump2.txt").exists())


if __name__ == "__main__":
    unittest.main()
