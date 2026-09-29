"""Render filled card HTML to PNG via headless Chrome.

Notes from live testing on this machine:
- Must use legacy `--headless` (not --headless=new): the new mode fails with
  a mojo error and produces no file on this environment.
- dbus/mojo noise on stderr is normal; success is judged solely by
  "PNG file exists and is >10KB".
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .template import fill_card


def find_chrome() -> str:
    """Resolve Chrome binary: $CHROME_BIN, then common names on PATH."""
    env = os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError(
        "Chrome/Chromium not found. Install it or set CHROME_BIN. "
        "(e.g. sudo apt install chromium-browser, or export CHROME_BIN=/path/to/chrome)"
    )


def render_card(html_str: str, out_png) -> None:
    """Render one HTML string to a 1280x720 PNG."""
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome()
    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html_str)
        html_path = f.name
    try:
        cmd = [
            chrome,
            "--headless",  # legacy mode: --headless=new fails on this machine
            "--no-sandbox",
            "--disable-gpu",
            f"--screenshot={out_png}",
            "--window-size=1280,720",
            "--hide-scrollbars",
            "--virtual-time-budget=3000",
            f"file://{html_path}",
        ]
        subprocess.run(cmd, capture_output=True, timeout=60)
        if not out_png.exists() or out_png.stat().st_size < 10_000:
            raise RuntimeError(
                f"Chrome did not produce a valid PNG at {out_png}. "
                "Check that fonts (Noto CJK) are installed."
            )
    finally:
        os.unlink(html_path)


def render_cards(cards: list, out_dir) -> list:
    """Validate + render all cards. Returns list of PNG paths.

    Validation (schema): id/title required, id matches [a-z0-9-]+ and is
    unique, exactly one of bullets/steps/comparison is non-empty.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seen = set()
    for card in cards:
        cid = card.get("id")
        if not cid or not isinstance(cid, str) or not cid:
            raise ValueError(f"card missing required 'id': {card!r:.80}")
        import re

        if not re.fullmatch(r"[a-z0-9-]+", cid):
            raise ValueError(f"card id must match [a-z0-9-]+, got: {cid!r}")
        if cid in seen:
            raise ValueError(f"duplicate card id: {cid}")
        seen.add(cid)
        if not card.get("title"):
            raise ValueError(f"card {cid}: 'title' is required")
        layout = card.get("layout", "card")
        if layout not in ("card", "fullscreen"):
            raise ValueError(
                f"card {cid}: layout must be 'card' or 'fullscreen', got {layout!r}"
            )
        bodies = [b for b in ("bullets", "steps", "comparison") if card.get(b)]
        if len(bodies) != 1:
            raise ValueError(
                f"card {cid}: exactly one of bullets/steps/comparison required, "
                f"got {len(bodies)}"
            )
        render_card(fill_card(card), out_dir / f"{cid}.png")
    return [str(out_dir / f"{c['id']}.png") for c in cards]
