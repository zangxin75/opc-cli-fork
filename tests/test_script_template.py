"""Unit tests for script template word allocation (scripts/script/template.py)."""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from script.template import SECTIONS, allocate, outline_text, target_words  # noqa: E402


class TargetWordsTests(unittest.TestCase):
    def test_ten_minutes_at_default_rate(self):
        self.assertEqual(target_words(10), 3000)

    def test_rate_scales_linearly(self):
        self.assertEqual(target_words(10, rate=4.7), 2820)


class AllocateTests(unittest.TestCase):
    def test_shares_sum_to_one(self):
        total = sum(s[2] for s in SECTIONS)
        self.assertAlmostEqual(total, 1.0)

    def test_budgets_sum_to_total(self):
        for minutes in (3, 10, 12.5):
            rows = allocate(minutes)
            self.assertEqual(sum(r[3] for r in rows), target_words(minutes))

    def test_all_sections_present_in_order(self):
        keys = [r[0] for r in allocate(10)]
        self.assertEqual(
            keys,
            ["hook", "intro", "demo_a", "insight", "demo_b", "demo_c",
             "method", "outro"],
        )

    def test_hook_budget(self):
        rows = dict((r[0], r[3]) for r in allocate(10))
        self.assertEqual(rows["hook"], 360)  # 12% of 3000

    def test_outline_mentions_budget_and_formula(self):
        text = outline_text(10)
        self.assertIn("3000 字", text)
        self.assertIn("钩子", text)
        self.assertIn("痛点故事", text)


if __name__ == "__main__":
    unittest.main()
