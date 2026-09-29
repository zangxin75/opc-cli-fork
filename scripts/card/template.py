"""HTML template filling for video info cards.

Pure functions, zero IO. One built-in theme: dark purple gradient
background with gold glowing emphasis (matching the reference video style).
"""

import html as _html
import re

_EM_RE = re.compile(r"<em>(.*?)</em>", re.DOTALL)


def escape_title(text: str) -> str:
    """Escape title text, preserving only <em>...</em> markup.

    All other angle brackets are escaped so user/LLM content cannot inject
    arbitrary HTML. Unclosed <em> is escaped too.
    """
    # First escape everything, then selectively restore <em> pairs.
    escaped = _html.escape(text, quote=False)
    # After escaping, valid em pairs appear as &lt;em&gt;...&lt;/em&gt;
    # (we escape-then-unescape pairs to also require balanced tags).
    restored = re.sub(
        r"&lt;em&gt;(.*?)&lt;/em&gt;", r"<em>\1</em>", escaped, flags=re.DOTALL
    )
    return restored


_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  width: 1280px; height: 720px;
  font-family: "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Zen Hei", sans-serif;
  background: radial-gradient(circle at 30% 20%, #2b1a5e 0%, #1a1040 45%, #0d0a2a 100%);
  color: #ffffff;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.card {
  width: 1120px; text-align: center;
  padding: 48px 64px;
  border-radius: 24px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
}
.eyebrow {
  font-size: 28px; color: #8b8fb8; letter-spacing: 6px;
  margin-bottom: 24px;
}
h1 {
  font-size: 64px; font-weight: 800; line-height: 1.3;
  margin-bottom: 40px;
}
h1 em {
  font-style: normal; color: #ffd54a;
  text-shadow: 0 0 24px rgba(255,213,74,0.8);
}
ul { list-style: none; }
ul li {
  font-size: 36px; line-height: 1.9; color: #e8e8f4;
}
ul li::before { content: "◆ "; color: #4dd0e1; font-size: 22px; }
.flow {
  display: flex; justify-content: center; align-items: center;
  gap: 18px; flex-wrap: wrap;
}
.flow .step:last-child { margin-right: 0; }
.flow .step {
  background: rgba(77,208,225,0.12);
  border: 1px solid rgba(77,208,225,0.4);
  border-radius: 14px;
  padding: 18px 30px;
  font-size: 34px; font-weight: 600; color: #b2ebf2;
}
.flow .arrow { font-size: 34px; color: #ffd54a; }
.flow .unit { display: inline-flex; align-items: center; gap: 18px; }
.comparison { display: flex; gap: 28px; justify-content: center; }
.comparison .col {
  flex: 1; max-width: 320px;
  background: rgba(255,255,255,0.05);
  border-radius: 16px; padding: 28px 20px;
  border-top: 4px solid #4dd0e1;
}
.comparison .col .head {
  font-size: 40px; font-weight: 800; color: #ffd54a; margin-bottom: 14px;
}
.comparison .col .body { font-size: 30px; color: #e8e8f4; line-height: 1.6; }
.footer {
  margin-top: 44px; font-size: 24px; color: #6a6a92; letter-spacing: 2px;
}
"""

# Fullscreen section style, modeled on the author's product site
# (repo/opc-cli/website/index.html): near-black bg, corner glows, noise
# texture, capsule tag, gradient em text, muted gray body text.
_CSS_FS = """
:root {
  --bg: #0a0a0f; --bg3: #1a1a26; --border: #2a2a3a;
  --cyan: #00f5d4; --purple: #9b5de5; --pink: #f15bb5;
  --t1: #ffffff; --t2: #a0a0b0; --t3: #606070;
  --grad1: linear-gradient(135deg, #00f5d4 0%, #9b5de5 50%, #f15bb5 100%);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  width: 1280px; height: 720px;
  font-family: "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Zen Hei", sans-serif;
  background: var(--bg);
  color: var(--t1);
  display: flex; align-items: center; justify-content: center;
  overflow: hidden; position: relative;
}
body::before {
  content: ''; position: absolute; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  opacity: 0.03;
}
.glow { position: absolute; border-radius: 50%; }
.glow-a {
  top: -180px; left: -120px; width: 640px; height: 640px;
  background: radial-gradient(circle, rgba(155,93,229,0.16) 0%, transparent 65%);
}
.glow-b {
  bottom: -200px; right: -140px; width: 680px; height: 680px;
  background: radial-gradient(circle, rgba(0,245,212,0.10) 0%, transparent 65%);
}
.sec {
  position: relative; text-align: center; max-width: 1080px;
  display: flex; flex-direction: column; align-items: center;
}
.tag {
  display: inline-block; padding: 10px 28px; margin-bottom: 30px;
  background: var(--bg3); border: 1px solid var(--border);
  border-radius: 100px; font-size: 22px; color: var(--purple);
  letter-spacing: 6px;
}
h1 {
  font-size: 72px; font-weight: 800; line-height: 1.25;
  letter-spacing: 2px; margin-bottom: 44px;
}
h1 em {
  font-style: normal;
  background: var(--grad1);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; color: transparent;
}
ul { list-style: none; }
ul li { font-size: 32px; line-height: 2.0; color: var(--t2); }
ul li::before { content: "— "; color: var(--cyan); }
.flow {
  display: flex; justify-content: center; align-items: center;
  gap: 20px; flex-wrap: wrap;
}
.flow .step {
  background: var(--bg3); border: 1px solid var(--border);
  border-radius: 14px; padding: 18px 30px;
  font-size: 32px; font-weight: 600; color: var(--t1);
}
.flow .arrow { font-size: 32px; color: var(--cyan); }
.flow .unit { display: inline-flex; align-items: center; gap: 20px; }
.comparison { display: flex; gap: 28px; justify-content: center; }
.comparison .col {
  flex: 1; max-width: 330px; text-align: left;
  background: var(--bg3); border: 1px solid var(--border);
  border-radius: 16px; padding: 28px 24px;
  border-top: 3px solid transparent;
  border-image: linear-gradient(90deg, #00f5d4, #9b5de5) 1;
}
.comparison .col .head {
  font-size: 38px; font-weight: 800; margin-bottom: 14px;
  background: var(--grad1);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; color: transparent;
}
.comparison .col .body { font-size: 26px; color: var(--t2); line-height: 1.7; }
.foot { margin-top: 46px; font-size: 22px; color: var(--t3); letter-spacing: 3px; }
"""


def _render_bullets(items):
    lis = "".join(f"<li>{_html.escape(str(i))}</li>" for i in items)
    return f"<ul>{lis}</ul>"


def _render_steps(items):
    parts = [f'<span class="step">{_html.escape(str(items[0]))}</span>']
    for s in items[1:]:
        # Arrow and step wrapped as one unit: if the row is full, BOTH wrap
        # to the next line together, so no arrow ever dangles at line end.
        parts.append(
            f'<span class="unit"><span class="arrow">→</span>'
            f'<span class="step">{_html.escape(str(s))}</span></span>'
        )
    return f'<div class="flow">{"".join(parts)}</div>'


def _render_comparison(comp):
    cols = "".join(
        f'<div class="col"><div class="head">{_html.escape(str(c["head"]))}</div>'
        f'<div class="body">{_html.escape(str(c["body"]))}</div></div>'
        for c in comp["cols"]
    )
    return f'<div class="comparison">{cols}</div>'


def _card_body_parts(card: dict) -> list:
    """Shared body blocks for both layouts: title + one content type."""
    body_parts = []
    if card.get("eyebrow"):
        body_parts.append(f'<p class="eyebrow">{_html.escape(str(card["eyebrow"]))}</p>')
    body_parts.append(f"<h1>{escape_title(str(card['title']))}</h1>")

    if card.get("bullets"):
        body_parts.append(_render_bullets(card["bullets"]))
    elif card.get("steps"):
        body_parts.append(_render_steps(card["steps"]))
    elif card.get("comparison"):
        body_parts.append(_render_comparison(card["comparison"]))

    if card.get("footer"):
        body_parts.append(f'<p class="footer">{_html.escape(str(card["footer"]))}</p>')
    return body_parts


def _fill_fullscreen(card: dict) -> str:
    """Author-site-style fullscreen section (replaces the video frame)."""
    parts = []
    if card.get("eyebrow"):
        parts.append(f'<p class="tag">{_html.escape(str(card["eyebrow"]))}</p>')
    parts.append(f"<h1>{escape_title(str(card['title']))}</h1>")
    if card.get("bullets"):
        parts.append(_render_bullets(card["bullets"]))
    elif card.get("steps"):
        parts.append(_render_steps(card["steps"]))
    elif card.get("comparison"):
        parts.append(_render_comparison(card["comparison"]))
    if card.get("footer"):
        parts.append(f'<p class="foot">{_html.escape(str(card["footer"]))}</p>')
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<style>{_CSS_FS}</style></head><body>"
        '<div class="glow glow-a"></div><div class="glow glow-b"></div>'
        f'<main class="sec">{"".join(parts)}</main>'
        "</body></html>"
    )


def fill_card(card: dict) -> str:
    """Render one card dict into a complete 1280x720 HTML page string.

    layout: "card" (default, bottom-overlay mini card) or
    "fullscreen" (author-site section style, replaces the frame).
    """
    if card.get("layout") == "fullscreen":
        return _fill_fullscreen(card)
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<style>{_CSS}</style></head><body>"
        f'<div class="card">{"".join(_card_body_parts(card))}</div>'
        "</body></html>"
    )
