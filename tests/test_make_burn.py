"""make 烧录阶段测试:ASS Style patch 纯函数。

回归背景:旧拼接逻辑 first + "," + style 导致 Style 行字段错位
(Fontname=Name、Fontsize=字体名),libass 样式失效、全片字幕消失。
"""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from make.make import _patch_ass_style  # noqa: E402

STYLE = ("Karaoke,Source Han Sans SC,50,&H0000D7FF,&H00FFFFFF,&H00000000,"
         "&H33000000,-1,0,0,0,100,100,0,0,1,3,2,2,10,10,60,1")

SAMPLE = """[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,你好
"""


class PatchAssStyleTests(unittest.TestCase):
    def test_replaces_first_style_line_whole(self):
        out = _patch_ass_style(SAMPLE, STYLE)
        # 整行替换:恰好一条 Style 行,首字段为 Name,无重复字段
        style_lines = [ln for ln in out.splitlines() if ln.startswith("Style:")]
        self.assertEqual(len(style_lines), 1)
        self.assertEqual(style_lines[0], "Style: " + STYLE)

    def test_field_count_matches_format(self):
        # Style 行字段数必须与 Format 一致(23),错位即字体/字号解析失败
        out = _patch_ass_style(SAMPLE, STYLE)
        fmt = next(ln for ln in out.splitlines() if ln.startswith("Format: Name,"))
        style = next(ln for ln in out.splitlines() if ln.startswith("Style: "))
        self.assertEqual(
            len(style.split(",")), len(fmt.split(",")),
            "Style 字段数与 Format 不一致 → 字段错位,字幕会消失")

    def test_idempotent(self):
        # 重复烧录(重跑 burn)不能让 Style 行叠加坏掉
        once = _patch_ass_style(SAMPLE, STYLE)
        twice = _patch_ass_style(once, STYLE)
        self.assertEqual(once, twice)

    def test_dialogue_untouched(self):
        out = _patch_ass_style(SAMPLE, STYLE)
        self.assertIn("Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,你好", out)


if __name__ == "__main__":
    unittest.main()
