"""Unit tests for script transcript analysis (scripts/script/analyze.py)."""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from script.analyze import analyze_srt, report_text  # noqa: E402

SRT = """1
00:00:00,000 --> 00:00:02,000
第一句开场

2
00:00:02,500 --> 00:00:04,500
紧跟着第二句

3
00:00:10,000 --> 00:00:13,000
停顿后的新段落

4
00:00:13,500 --> 00:00:16,000
段落继续
"""


class AnalyzeSrtTests(unittest.TestCase):
    def test_duration_and_chars(self):
        stats = analyze_srt(SRT)
        self.assertEqual(stats["duration"], 16.0)
        # 5+6+7+4 = 22 chars
        self.assertEqual(stats["chars"], 22)

    def test_rate(self):
        stats = analyze_srt(SRT)
        self.assertAlmostEqual(stats["rate"], 22 / 16.0)

    def test_sections_split_at_gap(self):
        stats = analyze_srt(SRT, gap=1.0)
        # 4.5s -> 10.0s is a 5.5s gap: two sections
        self.assertEqual(len(stats["sections"]), 2)
        self.assertEqual(stats["sections"][0]["start"], 0.0)
        self.assertEqual(stats["sections"][1]["start"], 10.0)
        self.assertIn("第一句开场", stats["sections"][0]["preview"])

    def test_small_gap_no_split(self):
        stats = analyze_srt(SRT, gap=60.0)
        self.assertEqual(len(stats["sections"]), 1)

    def test_per_minute_density(self):
        stats = analyze_srt(SRT)
        self.assertEqual(stats["per_minute"], [(0, 22)])

    def test_empty_srt_raises(self):
        with self.assertRaises(ValueError):
            analyze_srt("")

    def test_report_text(self):
        report = report_text(analyze_srt(SRT, gap=1.0))
        self.assertIn("16s", report)
        self.assertIn("22 字", report)
        self.assertIn("共 2 段", report)


if __name__ == "__main__":
    unittest.main()
