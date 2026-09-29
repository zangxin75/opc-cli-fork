"""Unit tests for card template filling (scripts/card/template.py)."""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from card.template import fill_card, escape_title  # noqa: E402


class EscapeTitleTests(unittest.TestCase):
    def test_plain_text_untouched(self):
        self.assertEqual(escape_title("真正值钱的直觉"), "真正值钱的直觉")

    def test_em_preserved(self):
        self.assertEqual(escape_title("值钱的是<em>组合</em>"), "值钱的是<em>组合</em>")

    def test_other_tags_escaped(self):
        out = escape_title("a<script>b</script>c")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_unclosed_em_escaped(self):
        out = escape_title("值钱的是<em>组合")
        self.assertNotIn("<em>", out)

    def test_bare_angle_bracket_escaped(self):
        out = escape_title("3 < 5 > 2")
        self.assertIn("&lt; 5 &gt;", out)


class FillCardTests(unittest.TestCase):
    def base_card(self, **over):
        card = {
            "id": "test-card",
            "title": "标题",
            "bullets": ["要点一", "要点二"],
        }
        card.update(over)
        return card

    def test_basic_html_structure(self):
        html = fill_card(self.base_card())
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("1280", html)  # canvas size in CSS
        self.assertIn("720", html)
        self.assertIn("标题", html)
        self.assertIn("要点一", html)

    def test_em_in_title_becomes_gold_span(self):
        html = fill_card(self.base_card(title="值钱的是<em>组合</em>"))
        self.assertIn("值钱的是<em>", html)

    def test_eyebrow_optional(self):
        html_with = fill_card(self.base_card(eyebrow="顶部引导"))
        html_without = fill_card(self.base_card())
        self.assertIn("顶部引导", html_with)
        self.assertNotIn("顶部引导", html_without)

    def test_steps_render_as_flow(self):
        html = fill_card(
            self.base_card(bullets=None, steps=["ASR", "TTS", "Agent"])
        )
        self.assertIn("ASR", html)
        # flow container present, bullet list absent
        self.assertIn("flow", html)

    def test_comparison_renders_columns(self):
        html = fill_card(
            self.base_card(
                bullets=None,
                comparison={
                    "cols": [
                        {"head": "高", "body": "产品"},
                        {"head": "中", "body": "编排"},
                        {"head": "低", "body": "单点"},
                    ]
                },
            )
        )
        self.assertIn("高", html)
        self.assertIn("产品", html)

    def test_footer_optional(self):
        html = fill_card(self.base_card(footer="下期预告"))
        self.assertIn("下期预告", html)

    def test_bullets_text_escaped(self):
        html = fill_card(self.base_card(bullets=["<b>bold</b>"]))
        self.assertNotIn("<b>bold</b>", html)
        self.assertIn("&lt;b&gt;", html)


class FillCardFullscreenTests(unittest.TestCase):
    def fs_card(self, **over):
        card = {
            "id": "fs",
            "layout": "fullscreen",
            "eyebrow": "章节标签",
            "title": "全屏卡 <em>强调</em>",
            "bullets": ["要点一", "要点二"],
        }
        card.update(over)
        return card

    def test_tag_capsule_and_gradient_css(self):
        html = fill_card(self.fs_card())
        self.assertIn('class="tag"', html)
        self.assertIn("linear-gradient(135deg, #00f5d4", html)

    def test_em_kept_for_gradient_text(self):
        html = fill_card(self.fs_card(title="值钱的是<em>组合</em>"))
        self.assertIn("<em>", html)

    def test_card_layout_default(self):
        html = fill_card(self.fs_card(layout="card"))
        self.assertIn('class="card"', html)
        self.assertNotIn('class="tag"', html)

    def test_footer_uses_foot_class(self):
        html = fill_card(self.fs_card(footer="下期预告"))
        self.assertIn('class="foot"', html)

    def test_glow_and_noise_layers(self):
        html = fill_card(self.fs_card())
        self.assertIn("glow", html)
        self.assertIn("feTurbulence", html)


if __name__ == "__main__":
    unittest.main()
