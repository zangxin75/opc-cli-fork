"""Multi-image background: PNG timeline + voice → base.mp4 via ffmpeg xfade.

Each shot's PNG backs exactly the SRT-derived time span of its sentence;
adjacent shots cross-fade over XFADE_SECONDS. Replaces the old
single-still background.
"""

import subprocess
from pathlib import Path

WIDTH, HEIGHT = 1280, 720
XFADE_SECONDS = 1.0
# 相邻两张图起点的最小间隔,小于此值丢弃后者(否则 xfade 显示窗口为零)
MIN_SHOT_SECONDS = 2.0


def normalize_segments(segments, total_duration):
    """把 keyword 定位出的时间段(可能有缝隙/重叠/同起点)整理成铺满时间轴的镜头序列。

    xfade 链要求第 k 张图从 S_k 一直显示到 S_{k+1}(缝隙由前一张补上,重叠截断前一张);
    起点间隔小于 MIN_SHOT_SECONDS 的镜头丢弃后者,保证每张图至少完整可见一会儿。
    """
    segs = sorted(((p, max(0.0, float(s)), float(e)) for p, s, e in segments),
                  key=lambda t: t[1])
    picked = []
    for png, s, e in segs:
        if picked and s - picked[-1][1] < MIN_SHOT_SECONDS:
            continue
        picked.append((png, s, e))
    if not picked:
        raise ValueError("no segments left after normalization")
    out = []
    for i, (png, s, e) in enumerate(picked):
        end = picked[i + 1][1] if i + 1 < len(picked) else max(e, total_duration)
        out.append((png, s, end))
    return out


def build_bg_command(segments, voice, total_duration, out_path):
    """Build the ffmpeg argv for the multi-image background video.

    segments: [(png_path, start, end), ...] sorted by start, covering
    [0, total_duration] (leading gap is stretched from the first PNG,
    trailing gap from the last).
    Returns the argv list (dry-run testable; does not execute).
    """
    if not segments:
        raise ValueError("no segments")
    # keyword 定位的时间段可能有缝隙/重叠,先正规化成铺满时间轴的序列
    # (缝隙由前一张图补上;这同时修复了缝隙导致 xfade 链提前 EOF 的 bug)
    segs = normalize_segments(segments, total_duration)
    first = segs[0]
    if first[1] > 0:
        segs[0] = (first[0], 0.0, first[2])

    cmd = ["ffmpeg", "-y"]
    inputs = []
    for i, (png, start, end) in enumerate(segs):
        dur = end - start + (XFADE_SECONDS if i < len(segs) - 1 else 0.0)
        if dur <= 0:
            raise ValueError(f"segment {i} ({png}) has non-positive span {start}..{end}")
        # 本机陷阱:PNG 输入必须 -loop 1 -t <时长>,否则流提前 EOF
        cmd += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(png)]
        inputs.append((png, start, end))
    cmd += ["-i", str(voice)]

    n = len(segs)
    parts = []
    for i in range(n):
        parts.append(
            f"[{i}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT},setsar=1,format=pix_fmts=yuv420p[v{i}]"
        )
    prev = "v0"
    for k in range(1, n):
        out = f"x{k}"
        parts.append(
            f"[{prev}][v{k}]xfade=transition=fade:duration={XFADE_SECONDS}:"
            f"offset={segs[k][1]:.3f}[{out}]"
        )
        prev = out
    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", f"[{prev}]", "-map", f"{n}:a",
        "-t", f"{total_duration:.3f}",
        "-tune", "stillimage", "-crf", "20",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out_path),
    ]
    return cmd


def build_bg(segments, voice, total_duration, out_path, dry_run=False):
    """Build (and unless dry_run, execute) the background video."""
    cmd = build_bg_command(segments, voice, total_duration, out_path)
    if dry_run:
        return cmd
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True, capture_output=True)
    return cmd
