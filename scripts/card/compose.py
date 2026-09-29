"""Compose rendered card PNGs onto a video at SRT-derived timestamps.

Filter chain validated live on this machine:
- `-loop 1 -t <video duration>` is REQUIRED for each PNG input: without it
  the PNG stream EOFs early and fade=t=out never fires (overlay freezes on
  the last frame).
- fade st values are video-timeline coordinates (the looped PNG stream
  shares the video's timeline).
- subprocess list args only (never shell=True): `iw*0.4` contains `*`.
"""

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_PUNCT_RE = re.compile(r"[\s，。！？；：、""''「」『』（）(),.!?;:\"'<>《》　]")


@dataclass
class SrtEntry:
    index: int
    start: float
    end: float
    text: str


def _ts_to_seconds(ts: str) -> float:
    h, m, rest = ts.split(":")
    s = float(rest.replace(",", "."))
    return int(h) * 3600 + int(m) * 60 + s


def parse_srt(content: str) -> list:
    """Parse SRT text into SrtEntry list. Handles BOM/CRLF/dot-ms/HTML tags."""
    if content.startswith("﻿"):
        content = content[1:]
    entries = []
    blocks = re.split(r"\r?\n\s*\r?\n", content.strip())
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m = re.search(r"(\d+:\d+[:\d]*[,.]\d+)\s*-->\s*(\d+:\d+[:\d]*[,.]\d+)", lines[1] if "-->" in lines[1] else lines[0])
        if not m:
            # first line may be index; try line after it
            if len(lines) >= 2:
                m = re.search(r"(\d+:\d+[:\d]*[,.]\d+)\s*-->\s*(\d+:\d+[:\d]*[,.]\d+)", lines[0])
            if not m:
                continue
        text_lines = lines[2:] if "-->" in lines[1] else lines[1:]
        text = " ".join(re.sub(r"<[^>]+>", "", t) for t in text_lines)
        entries.append(
            SrtEntry(len(entries) + 1, _ts_to_seconds(m.group(1)), _ts_to_seconds(m.group(2)), text.strip())
        )
    return entries


def _strip_punct(s: str) -> str:
    return _PUNCT_RE.sub("", s)


_SENT_END_RE = re.compile(r"[。!?…;!?;]")
MIN_CARD_SECONDS = 3.0
MAX_CARD_SECONDS = 12.0


def _find_keyword_owner(entries: list, keyword: str):
    """Return the (owner_entry, char_pos_in_concatenation) of the first
    keyword hit, trying the three matching passes. Raises if not found.

    Passes (shared by find_keyword_start / find_keyword_span):
    1. raw concatenation
    2. punctuation/space stripped on both sides
    3. long-keyword fallback: >=4-char substrings, longest first.
    """
    joined, owners = "", []
    for e in entries:
        t = e.text
        joined += t
        owners.extend([e] * len(t))
    pos = joined.find(keyword)
    if pos >= 0 and owners:
        return owners[pos], pos, owners, joined
    # Pass 2: punctuation/space stripped on both sides
    sj, sowners = "", []
    for e in entries:
        t = _strip_punct(e.text)
        sj += t
        sowners.extend([e] * len(t))
    kw = _strip_punct(keyword)
    pos = sj.find(kw)
    if pos >= 0:
        return sowners[pos], pos, sowners, sj
    # Pass 3: n-gram fallback for long keywords that only partially overlap
    # what ASR actually transcribed (e.g. LLM took a whole clause, ASR heard
    # a shorter variant). Try every >=4-char substring of the keyword,
    # longest first, first hit wins.
    if len(kw) > 6:
        ngrams = sorted(
            (kw[i:j] for i in range(len(kw) - 3) for j in range(i + 4, len(kw) + 1)),
            key=len, reverse=True,
        )
        for chunk in ngrams:
            pos = sj.find(chunk)
            if pos >= 0:
                return sowners[pos], pos, sowners, sj
    listing = "\n".join(f"  [{e.index}] {e.start:.1f}s {e.text}" for e in entries)
    raise ValueError(
        f"keyword {keyword!r} not found in any subtitle line. Full listing:\n{listing}"
    )


def find_keyword_start(entries: list, keyword: str) -> float:
    """Find video timestamp where keyword first appears."""
    owner, _, _, _ = _find_keyword_owner(entries, keyword)
    return owner.start


def find_keyword_span(entries: list, keyword: str) -> tuple:
    """Find (start, end) of the spoken sentence containing the keyword.

    The card should stay on screen exactly as long as the narrator speaks
    the sentence the card summarizes: from the keyword's first entry to
    the first following entry that ends with sentence-final punctuation
    (。!?…;), clamped to [MIN_CARD_SECONDS, MAX_CARD_SECONDS]. When the
    keyword's own entry ends a sentence, its end time is the span end.
    """
    owner, pos, owners, _ = _find_keyword_owner(entries, keyword)
    idx = entries.index(owner)
    end = owner.end
    for e in entries[idx:]:
        end = e.end
        if _SENT_END_RE.search(e.text[-2:]):
            break
    span = end - owner.start
    if span < MIN_CARD_SECONDS:
        end = owner.start + MIN_CARD_SECONDS
    elif span > MAX_CARD_SECONDS:
        end = owner.start + MAX_CARD_SECONDS
    return owner.start, end


def _ffprobe_duration(video: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _ffprobe_size(video: str) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0", video],
        capture_output=True, text=True, check=True,
    )
    w, h = out.stdout.strip().split(",")
    return int(w), int(h)


def validate_timing(cards: list, timing: list) -> None:
    """Schema checks for timing section (design contract §4)."""
    ids = {c["id"] for c in cards}
    seen_kw = set()
    for t in timing:
        if t["card"] not in ids:
            raise ValueError(f"timing.card {t['card']!r} does not match any card id")
        kw = t.get("keyword")
        if not kw:
            raise ValueError(f"timing for {t['card']}: keyword required")
        if kw in seen_kw:
            raise ValueError(f"duplicate keyword in timing: {kw!r}")
        seen_kw.add(kw)


def compose_cards(
    video: str,
    srt_path: str,
    cards: list,
    timing: list,
    out_path: str,
    card_width: float = 0.4,
    margin: int = 80,
    fade: float = 0.3,
) -> str:
    """Overlay card PNGs onto video at keyword-matched timestamps."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found. Install with: sudo apt install ffmpeg")
    validate_timing(cards, timing)
    entries = parse_srt(Path(srt_path).read_text(encoding="utf-8-sig"))
    duration_total = _ffprobe_duration(video)
    vw, vh = _ffprobe_size(video)
    layout_of = {c["id"]: c.get("layout", "card") for c in cards}

    spots = []  # (start, end, png_path, card_id, layout)
    for t in timing:
        # 需求2:卡片停留时长 = 语音表述该句的实际时长(SRT span 推导),
        # LLM 给的 duration 仅作 fallback(无 SRT 或 span 异常时)。
        start, end = find_keyword_span(entries, t["keyword"])
        fallback = float(t.get("duration", 4.0))
        if not (MIN_CARD_SECONDS <= end - start <= MAX_CARD_SECONDS):
            end = start + fallback
        if end > duration_total:
            end = duration_total
            print(f"[card] warning: {t['card']} truncated at video end ({duration_total:.1f}s)")
        png = Path(t.get("_png_dir", ".")) / f"{t['card']}.png" if t.get("_png_dir") else Path(f"{t['card']}.png")
        spots.append((start, end, str(png), t["card"], layout_of.get(t["card"], "card")))
    # overlap check
    spots.sort()
    for (s1, e1, _, n1, _), (s2, _, _, n2, _) in zip(spots, spots[1:]):
        if s2 < e1:
            raise ValueError(
                f"cards {n1} [{s1:.1f}-{e1:.1f}s] and {n2} [{s2:.1f}s..] overlap"
            )

    inputs = ["ffmpeg", "-y", "-i", video]
    for _, _, png, _, _ in spots:
        inputs += ["-loop", "1", "-t", f"{duration_total:.3f}", "-i", png]

    filters, cur = [], "0:v"
    for idx, (s, e, _, _, layout) in enumerate(spots, start=1):
        if layout == "fullscreen":
            # PNG 渲染为 1280x720,视频画布可能是任意分辨率(如 S2V 的
            # 832x480),必须缩放到视频实际尺寸,否则四边被裁
            scale, xy = f"scale={vw}:{vh},", "0:0"
        else:
            scale, xy = f"scale=iw*{card_width}:-1,", f"(W-w)/2:H-h-{margin}"
        filters.append(
            f"[{idx}:v]{scale}format=rgba,"
            f"fade=t=in:st={s:.3f}:d={fade}:alpha=1,"
            f"fade=t=out:st={e - fade:.3f}:d={fade}:alpha=1[f{idx}]"
        )
        out_label = f"v{idx}" if idx < len(spots) else "v"
        filters.append(
            f"[{cur}][f{idx}]overlay={xy}:"
            f"enable='between(t,{s:.3f},{e:.3f})'[{out_label}]"
        )
        cur = out_label

    cmd = inputs + [
        "-filter_complex", ";".join(filters),
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-crf", "18", "-c:a", "copy",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path
