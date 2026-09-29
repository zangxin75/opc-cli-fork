"""Reverse-engineer a narration transcript: rate, density, section breaks.

The analyze side of script design — turn any SRT (e.g. from `opc asr`)
into the same stats we used to study the reference video by hand:
chars/sec rate, per-minute density, and section breaks at pause gaps.
"""

from card.compose import parse_srt

# Adjacent subtitle gap larger than this starts a new section (a speech
# pause / edit point). Tuned on the reference video: its tightest
# inter-section pauses are ~0.6-0.75s, so 0.85s separates real sections
# without fragmenting normal sentence pauses.
SECTION_GAP = 0.85

PREVIEW_LEN = 48


def analyze_srt(content: str, gap: float = SECTION_GAP) -> dict:
    """SRT text -> stats dict. Pure function (parse_srt is pure)."""
    entries = parse_srt(content)
    if not entries:
        raise ValueError("no subtitle entries found in input")

    duration = entries[-1].end
    chars = sum(len([c for c in e.text if not c.isspace()]) for e in entries)
    # sections split at pause gaps
    sections, cur_start, cur_end, cur_texts = [], entries[0].start, entries[0].end, [entries[0].text]
    for prev, e in zip(entries, entries[1:]):
        if e.start - prev.end >= gap:
            sections.append((cur_start, cur_end, cur_texts))
            cur_start, cur_texts = e.start, []
        cur_end = e.end
        cur_texts.append(e.text)
    sections.append((cur_start, cur_end, cur_texts))

    per_minute = []
    for m in range(int(duration // 60) + 1):
        lo, hi = m * 60, (m + 1) * 60
        c = sum(
            len([ch for ch in e.text if not ch.isspace()])
            for e in entries
            if e.start < hi and e.end > lo
        )
        if c:
            per_minute.append((m, c))

    return {
        "duration": duration,
        "chars": chars,
        "rate": chars / duration if duration else 0.0,
        "per_minute": per_minute,
        "sections": [
            {
                "start": s, "end": e, "chars": sum(len(t) for t in texts),
                "preview": " ".join(texts)[:PREVIEW_LEN],
            }
            for s, e, texts in sections
        ],
    }


def report_text(stats: dict) -> str:
    """Stats dict -> human-readable report."""
    lines = [
        f"时长 {stats['duration']:.0f}s · {stats['chars']} 字 · 语速 {stats['rate']:.1f} 字/秒",
        f"段落(按 >={SECTION_GAP}s 停顿切分,共 {len(stats['sections'])} 段):",
    ]
    for s in stats["sections"]:
        mm, ss = int(s["start"] // 60), int(s["start"] % 60)
        lines.append(f"  [{mm:02d}:{ss:02d}] {s['chars']:4d} 字 | {s['preview']}…")
    if stats["per_minute"]:
        peak = max(stats["per_minute"], key=lambda x: x[1])
        lines.append(f"峰值密度: 第 {peak[0]} 分钟 {peak[1]} 字")
    return "\n".join(lines)
