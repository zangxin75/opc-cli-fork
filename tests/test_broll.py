"""broll 模块测试:shot 校验、ffmpeg 命令构造(dry-run)、span 定位。"""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from broll.bg import XFADE_SECONDS, build_bg_command, normalize_segments  # noqa: E402
from broll.plan import validate_shots  # noqa: E402
from card.compose import SrtEntry, find_keyword_span  # noqa: E402


class ValidateShotsTests(unittest.TestCase):
    def test_valid(self):
        validate_shots([
            {"keyword": "流水线思维", "prompt": "a cinematic workspace with subtitle panels"},
            {"keyword": "开源仓库", "prompt": "a glowing server rack in dark room"},
        ])

    def test_ascii_keyword_rejected(self):
        with self.assertRaises(ValueError):
            validate_shots([{"keyword": "OPC工具箱", "prompt": "some valid prompt"}])

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            validate_shots([
                {"keyword": "流水线思维", "prompt": "a cinematic workspace"},
                {"keyword": "流水线思维", "prompt": "another prompt"},
            ])

    def test_empty_prompt_rejected(self):
        with self.assertRaises(ValueError):
            validate_shots([{"keyword": "流水线思维", "prompt": "x"}])


class BgCommandTests(unittest.TestCase):
    def test_two_segments_structure(self):
        segs = [("/tmp/a.png", 0.0, 10.0), ("/tmp/b.png", 10.0, 20.0)]
        cmd = build_bg_command(segs, "/tmp/v.mp3", 20.0, "/tmp/out.mp4")
        s = " ".join(cmd)
        # 每图 -loop 1 -t(首段含 fade 余量)
        self.assertIn("-loop 1 -t 11.000 -i /tmp/a.png", s)
        self.assertIn("-loop 1 -t 10.000 -i /tmp/b.png", s)
        # xfade offset 为第二段绝对起点
        self.assertIn(f"xfade=transition=fade:duration={XFADE_SECONDS}:offset=10.000", s)
        # 音轨在视频输入之后,映射正确
        self.assertIn("-map [x1]", s)
        self.assertIn("-map 2:a", s)

    def test_leading_trailing_gap_stretched(self):
        segs = [("/tmp/a.png", 5.0, 10.0)]
        cmd = build_bg_command(segs, "/tmp/v.mp3", 30.0, "/tmp/out.mp4")
        s = " ".join(cmd)
        # 单段被拉伸覆盖 0~30s
        self.assertIn("-loop 1 -t 30.000 -i /tmp/a.png", s)
        self.assertNotIn("xfade", s)

    def test_empty_segments_rejected(self):
        with self.assertRaises(ValueError):
            build_bg_command([], "/tmp/v.mp3", 10.0, "/tmp/out.mp4")

    def test_gap_between_segments_filled_by_previous(self):
        # 回归:缝隙(10→17.5)曾导致 xfade 链在 14.5s 提前 EOF、视频流截断
        segs = [("/tmp/a.png", 0.0, 10.0), ("/tmp/b.png", 17.5, 27.5)]
        cmd = build_bg_command(segs, "/tmp/v.mp3", 27.5, "/tmp/out.mp4")
        s = " ".join(cmd)
        # a 被拉长到 17.5(显示到 b 开始淡入),b 的 -t 覆盖余下全部
        self.assertIn("-loop 1 -t 18.500 -i /tmp/a.png", s)
        self.assertIn("offset=17.500", s)

    def test_overlapping_segments_kept_both(self):
        # 重叠段(0-12 与 8-20):两张都保留,前一张只显示到后一张起点
        segs = [("/tmp/a.png", 0.0, 12.0), ("/tmp/b.png", 8.0, 20.0)]
        cmd = build_bg_command(segs, "/tmp/v.mp3", 20.0, "/tmp/out.mp4")
        s = " ".join(cmd)
        self.assertIn("offset=8.000", s)
        self.assertIn("-loop 1 -t 9.000 -i /tmp/a.png", s)

    def test_equal_start_second_dropped(self):
        # 同起点(两 keyword 命中同一句):丢弃后者,避免零显示窗口
        segs = [("/tmp/a.png", 362.2, 374.2), ("/tmp/b.png", 362.2, 374.2),
                ("/tmp/c.png", 380.0, 392.0)]
        cmd = build_bg_command(segs, "/tmp/v.mp3", 392.0, "/tmp/out.mp4")
        s = " ".join(cmd)
        self.assertEqual(s.count("-i /tmp/"), 3)  # a + c + 音频,b 被丢
        self.assertNotIn("/tmp/b.png", s)


class NormalizeSegmentsTests(unittest.TestCase):
    def test_tiles_the_timeline(self):
        segs = normalize_segments(
            [("/a.png", 3.5, 13.5), ("/b.png", 17.5, 27.5), ("/c.png", 25.8, 35.8)],
            total_duration=36.0)
        # 缝隙由前一张补上,重叠截断前一张,末段铺到片尾
        # (首段向前铺到 0 由 build_bg_command 负责)
        self.assertEqual(segs, [("/a.png", 3.5, 17.5),
                                ("/b.png", 17.5, 25.8),
                                ("/c.png", 25.8, 36.0)])

    def test_too_close_starts_drop_later(self):
        segs = normalize_segments(
            [("/a.png", 0.0, 12.0), ("/b.png", 1.0, 10.0)], total_duration=12.0)
        self.assertEqual(segs, [("/a.png", 0.0, 12.0)])


class SpanMappingTests(unittest.TestCase):
    def test_shot_keyword_maps_to_sentence(self):
        es = [
            SrtEntry(1, 0.0, 2.0, "开场白。"),
            SrtEntry(2, 2.0, 3.0, "接下来讲"),
            SrtEntry(3, 3.0, 5.0, "流水线思维。"),
        ]
        start, end = find_keyword_span(es, "接下来讲")
        self.assertAlmostEqual(start, 2.0)
        self.assertAlmostEqual(end, 5.0)


if __name__ == "__main__":
    unittest.main()
