"""avatar 切段:按 SRT 句子边界把口播音频聚合成渲染段。

Wan2.2 S2V 每窗口 77 帧(≈4.8s),段内可串 extend 窗口;段间硬切。
切段对齐句子边界,唇形不会词中断裂。
"""

FPS = 16
MAX_SEG_SECONDS = 15.0   # 段上限(≈3 个 77 帧窗口)


def plan_segments(entries, max_seconds: float = MAX_SEG_SECONDS):
    """SRT 条目序列 → [(start, end), ...] 渲染段列表。

    entries: card.compose.SrtEntry 列表(start/end 秒,升序)。
    贪心聚合:不断并入当前段,直到超过 max_seconds 才开新段;
    单句超上限时独立成段(不截断句子)。
    """
    if not entries:
        return []
    segs = []
    start = entries[0].start
    end = entries[0].end
    for e in entries[1:]:
        if e.end - start <= max_seconds:
            end = e.end
        else:
            segs.append((start, end))
            start, end = e.start, e.end
    segs.append((start, end))
    return segs


def segment_audio_times(segs, voice_duration: float):
    """段列表 → [(ss, to), ...] 音频切割参数,末段对齐语音全长。"""
    out = []
    for i, (s, e) in enumerate(segs):
        to = voice_duration if i == len(segs) - 1 else e
        out.append((s, to))
    return out
