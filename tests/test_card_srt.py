"""Unit tests for SRT parsing and keyword sliding-window matching."""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from card.compose import parse_srt, find_keyword_start  # noqa: E402


SRT = """1
00:00:01,000 --> 00:00:03,000
今天讲一下组合

2
00:00:03,200 --> 00:00:06,000
能力为什么这么值钱

3
00:00:06,500 --> 00:00:10,000
以及怎么用它做产品
"""


class ParseSrtTests(unittest.TestCase):
    def test_basic(self):
        entries = parse_srt(SRT)
        self.assertEqual(len(entries), 3)
        self.assertAlmostEqual(entries[0].start, 1.0)
        self.assertAlmostEqual(entries[0].end, 3.0)
        self.assertEqual(entries[0].text, "今天讲一下组合")

    def test_dot_milliseconds(self):
        entries = parse_srt("1\n00:00:01.500 --> 00:00:02.000\nhi\n")
        self.assertAlmostEqual(entries[0].start, 1.5)

    def test_bom_and_crlf(self):
        entries = parse_srt("﻿1\r\n00:00:01,000 --> 00:00:02,000\r\nhi\r\n")
        self.assertEqual(entries[0].text, "hi")

    def test_html_tags_stripped(self):
        entries = parse_srt("1\n00:00:01,000 --> 00:00:02,000\n<i>hi</i>\n")
        self.assertEqual(entries[0].text, "hi")

    def test_multiline_text_joined(self):
        entries = parse_srt("1\n00:00:01,000 --> 00:00:02,000\nline one\nline two\n")
        self.assertEqual(entries[0].text, "line one line two")


class KeywordMatchTests(unittest.TestCase):
    def setUp(self):
        self.entries = parse_srt(SRT)

    def test_keyword_within_one_entry(self):
        t = find_keyword_start(self.entries, "怎么用")
        self.assertAlmostEqual(t, 6.5)

    def test_keyword_across_two_entries(self):
        # "组合能力" spans entry 1 tail and entry 2 head
        t = find_keyword_start(self.entries, "组合能力")
        self.assertAlmostEqual(t, 1.0)  # start of the entry containing 组合

    def test_keyword_with_punctuation(self):
        t = find_keyword_start(self.entries, "「组合能力」")
        self.assertAlmostEqual(t, 1.0)

    def test_no_match_raises_with_context(self):
        with self.assertRaises(ValueError) as ctx:
            find_keyword_start(self.entries, "不存在的词")
        self.assertIn("组合", str(ctx.exception))  # error lists subtitle lines


if __name__ == "__main__":
    unittest.main()


class LongKeywordShrinkTests(unittest.TestCase):
    def test_long_keyword_prefix_match(self):
        # LLM-style clause keyword: prefix exists, tail differs from ASR text
        entries = parse_srt(
            "1\n00:00:02,000 --> 00:00:04,000\nAgent 编排流程\n"
        )
        t = find_keyword_start(entries, "Agent 负责决定什么时候用哪个")
        self.assertAlmostEqual(t, 2.0)  # prefix "Agent" matched after shrink

    def test_no_match_still_raises(self):
        entries = parse_srt("1\n00:00:01,000 --> 00:00:02,000\n完全无关\n")
        with self.assertRaises(ValueError):
            find_keyword_start(entries, "一个根本不存在的话题关键词")
