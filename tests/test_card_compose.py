"""Integration test for compose_cards (slow: runs ffmpeg end-to-end)."""

import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from card.compose import compose_cards, parse_srt  # noqa: E402

WORK = Path("/tmp/opc-card-compose-test")


def _gray_max_at(video, t):
    """Extract frame at t, return max luma of a 100x100 crop at bottom-center."""
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(t), "-i", video,
         "-frames:v", "1", "-vf", "crop=100:100:270:170,format=gray",
         "-f", "rawvideo", str(WORK / "frame.raw")],
        capture_output=True, check=True,
    )
    d = (WORK / "frame.raw").read_bytes()
    return max(d) if d else 0


class ComposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(exist_ok=True)
        # 6s 640x360 red test video with silent audio track
        cls.video = WORK / "base.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=640x360:d=6",
             "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "6",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             str(cls.video)],
            capture_output=True, check=True,
        )
        # solid green card PNG 640x360 (card sits at bottom-center after scale)
        cls.card_png = WORK / "green-card.png"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x00cc44:s=640x360:d=1",
             "-frames:v", "1", str(cls.card_png)],
            capture_output=True, check=True,
        )
        cls.srt = WORK / "test.srt"
        cls.srt.write_text(
            "1\n00:00:00,500 --> 00:00:02,000\n关键词开始。\n\n"
            "2\n00:00:02,000 --> 00:00:04,000\n中间内容。\n\n"
            "3\n00:00:04,000 --> 00:00:06,000\n结尾。\n",
            encoding="utf-8",
        )
        cls.cards = [{"id": "green-card", "title": "t", "bullets": ["b"]}]
        cls.timing = [{"card": "green-card", "keyword": "关键词开始", "duration": 2.0}]

    def test_compose_fade_behavior(self):
        out = str(WORK / "out.mp4")
        compose_cards(
            video=str(self.video),
            srt_path=str(self.srt),
            cards=self.cards,
            timing=[dict(self.timing[0], _png_dir=str(WORK))],
            out_path=out,
            card_width=1.0,   # card fills 640x360 fully
            margin=0,
        )
        self.assertTrue(Path(out).exists())
        # red is luma ~84; green card luma ~130; black is 0.
        # span 语义(需求2):keyword 句 0.5-2.0s,MIN clamp 后卡片窗口 0.5-3.5s
        # before fade-in (t=0.2): crop shows red  → max ≈ 84 (no card)
        self.assertLess(_gray_max_at(out, 0.2), 100)
        # mid fade-in (t=0.65~0.75): partially blended → between red and green
        mid = _gray_max_at(out, 0.72)
        self.assertGreater(mid, 100, f"fade-in not visible at t=0.6 (max={mid})")
        self.assertLess(mid, 190, f"card fully visible too early at t=0.6 (max={mid})")
        # fully shown (t=1.5): green → max ≈ 130+
        self.assertGreater(_gray_max_at(out, 1.5), 110)
        # after fade-out (t=4.2, card window ends 3.5s + fade): red again
        self.assertLess(_gray_max_at(out, 4.2), 100)
        # duration preserved
        dur = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", out],
            capture_output=True, text=True, check=True,
        )
        self.assertAlmostEqual(float(dur.stdout.strip()), 6.0, delta=0.5)

    def test_compose_fullscreen_layout(self):
        # 1280x720 bright card overlaid at 0:0 must cover the 640x360 frame
        fs_png = WORK / "fs-card.png"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0xffe000:s=1280x720:d=1",
             "-frames:v", "1", str(fs_png)],
            capture_output=True, check=True,
        )
        cards = [{"id": "fs-card", "title": "t", "bullets": ["b"],
                  "layout": "fullscreen"}]
        timing = [{"card": "fs-card", "keyword": "中间内容", "duration": 2.0,
                   "_png_dir": str(WORK)}]
        out = str(WORK / "out_fs.mp4")
        compose_cards(
            video=str(self.video), srt_path=str(self.srt),
            cards=cards, timing=timing, out_path=out,
        )
        self.assertTrue(Path(out).exists())
        # span 语义(需求2):"中间内容。" 句 2.0-4.0s,MIN clamp 后窗口 2.0-5.0s
        # before (t=1.0): red ~84
        self.assertLess(_gray_max_at(out, 1.0), 100)
        # fully shown (t=3.0): yellow card covers whole frame, luma ~207
        self.assertGreater(_gray_max_at(out, 3.0), 190)
        # after fade-out (t=5.7, card window ends 5.0s + fade): red again
        self.assertLess(_gray_max_at(out, 5.7), 100)


if __name__ == "__main__":
    unittest.main()
