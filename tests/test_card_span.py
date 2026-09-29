"""find_keyword_span 单元测试:卡片停留时长与语音句子对齐。"""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from card.compose import (  # noqa: E402
    MAX_CARD_SECONDS, MIN_CARD_SECONDS, SrtEntry,
    find_keyword_span, find_keyword_start,
)


def entries(*rows):
    """rows: (start, end, text) -> [SrtEntry]"""
    return [
        SrtEntry(index=i + 1, start=s, end=e, text=t)
        for i, (s, e, t) in enumerate(rows)
    ]


class SpanTests(unittest.TestCase):
    def test_same_entry_sentence_end(self):
        # keyword 所在 entry 自带句末标点 → span 即该 entry
        es = entries((0.0, 2.0, "流水线思维。"), (2.0, 4.0, "下一句。"))
        start, end = find_keyword_span(es, "流水线思维")
        self.assertAlmostEqual(start, 0.0)
        self.assertAlmostEqual(end, MIN_CARD_SECONDS)  # 2s 句子被抬到 MIN 3s

    def test_swallow_until_sentence_end(self):
        # ASR 断行把一句话拆成多条,keyword 在句首,句号在第三条
        es = entries(
            (10.0, 11.0, "你会发现所谓"),
            (11.0, 12.0, "的流水线思维"),
            (12.0, 13.5, "就在脚下。"),
            (13.5, 15.0, "无关内容。"),
        )
        start, end = find_keyword_span(es, "你会发现")
        self.assertAlmostEqual(start, 10.0)
        self.assertAlmostEqual(end, 13.5)  # 吞到句末标点所在 entry

    def test_keyword_mid_sentence(self):
        es = entries(
            (20.0, 21.0, "前面铺垫"),
            (21.0, 22.0, "中间是关键词"),
            (22.0, 24.0, "后面结束!"),
        )
        start, end = find_keyword_span(es, "中间是关键词")
        self.assertAlmostEqual(start, 21.0)
        self.assertAlmostEqual(end, 24.0)

    def test_no_punctuation_swallow_everything_then_clamp(self):
        # 全程无句末标点 → span 会超过 MAX,被 clamp
        es = entries(*[(i * 1.0, i * 1.0 + 1.0, f"第{i}行没有标点") for i in range(20)])
        start, end = find_keyword_span(es, "第0行没有标点")
        self.assertAlmostEqual(start, 0.0)
        self.assertAlmostEqual(end, MAX_CARD_SECONDS)

    def test_min_clamp(self):
        # 命中 entry 只有 0.5s 且立即句末 → span 抬到 MIN
        es = entries((5.0, 5.5, "短。"), (6.0, 8.0, "其他。"))
        start, end = find_keyword_span(es, "短")
        self.assertAlmostEqual(start, 5.0)
        self.assertAlmostEqual(end, 5.0 + MIN_CARD_SECONDS)

    def test_cross_line_keyword_uses_stripped_pass(self):
        # keyword 跨行拼接(标点被去掉后匹配)
        es = entries(
            (0.0, 1.0, "好家伙,"),
            (1.0, 2.5, "这也能行?"),
        )
        start, _ = find_keyword_span(es, "好家伙这也能行")
        self.assertAlmostEqual(start, 0.0)

    def test_not_found_raises(self):
        es = entries((0.0, 1.0, "完全无关。"))
        with self.assertRaises(ValueError):
            find_keyword_span(es, "不存在的词组")

    def test_start_consistent_with_legacy(self):
        # span 的 start 与旧 find_keyword_start 一致
        es = entries((3.0, 4.0, "一条命令行"), (4.0, 6.0, "搞定一切。"))
        _, span_start = None, find_keyword_span(es, "一条命令行")[0]
        self.assertAlmostEqual(span_start, find_keyword_start(es, "一条命令行"))


if __name__ == "__main__":
    unittest.main()
