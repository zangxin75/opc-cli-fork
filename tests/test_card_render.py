"""Integration test for card rendering via headless Chrome (slow: runs a browser)."""

import sys
import struct
import unittest
import zlib
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from card.template import fill_card  # noqa: E402
from card.render import render_card, find_chrome  # noqa: E402


def _png_size(path):
    """Read PNG width/height from IHDR chunk without Pillow."""
    data = Path(path).read_bytes()
    # PNG signature 8 bytes + IHDR length(4)+type(4), width at offset 16
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    w, h = struct.unpack(">II", data[16:24])
    return w, h


class RenderTests(unittest.TestCase):
    def test_find_chrome(self):
        # On this machine google-chrome exists; CHROME_BIN may override
        chrome = find_chrome()
        self.assertTrue(chrome and Path(chrome).exists(), f"chrome not found: {chrome}")

    def test_render_card_produces_1280x720_png(self):
        html = fill_card({
            "id": "it",
            "title": "渲染测试 <em>OK</em>",
            "bullets": ["要点一", "要点二"],
        })
        out = Path("/tmp/opc-card-test.png")
        render_card(html, out)
        self.assertTrue(out.exists(), "PNG not produced")
        self.assertGreater(out.stat().st_size, 10_000, "PNG suspiciously small")
        w, h = _png_size(out)
        self.assertEqual((w, h), (1280, 720))

    def test_render_fullscreen_card_produces_png(self):
        html = fill_card({
            "id": "itfs",
            "layout": "fullscreen",
            "eyebrow": "TEST",
            "title": "全屏渲染 <em>OK</em>",
            "bullets": ["要点一", "要点二"],
        })
        out = Path("/tmp/opc-card-test-fs.png")
        render_card(html, out)
        self.assertTrue(out.exists(), "PNG not produced")
        self.assertGreater(out.stat().st_size, 10_000, "PNG suspiciously small")
        w, h = _png_size(out)
        self.assertEqual((w, h), (1280, 720))

    def test_invalid_layout_rejected_before_chrome(self):
        from card.render import render_cards
        with self.assertRaises(ValueError):
            render_cards(
                [{"id": "bad", "title": "t", "bullets": ["b"], "layout": "huge"}],
                "/tmp/opc-card-bad-layout",
            )


if __name__ == "__main__":
    unittest.main()
