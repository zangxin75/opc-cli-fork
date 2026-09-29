"""opc stitch — timeline.json 驱动的多轨视频合成。

EDL(剪辑决策表) → ffmpeg filter_complex:
  clips(口播/录屏,可裁剪) 顺序拼接 → 字卡 overlay → ASS 字幕烧录 → BGM 混音。
设计约束:
  - 全部用 subprocess 参数列表(勿 shell=True,避开转义坑)
  - clips 统一 scale/pad 到目标画布并统一 fps,再 concat
  - 字卡复用 card/compose 的 overlay+fade+enable 模式
"""

from pathlib import Path
import json
import shlex
import shutil
import subprocess


def load_timeline(path: str) -> dict:
    tl = json.loads(Path(path).read_text(encoding="utf-8"))
    if not tl.get("clips"):
        raise ValueError("timeline.json 缺少 clips")
    return tl


def _escape_filter_path(p: str) -> str:
    return p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def build_command(tl: dict, out_path: str) -> list:
    """timeline dict → ffmpeg 完整参数列表(不执行)。"""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found. Install with: sudo apt install ffmpeg")
    w, h = tl.get("width", 832), tl.get("height", 480)
    fps = tl.get("fps", 30)
    fade = tl.get("card_fade", 0.3)

    clips = tl["clips"]
    cards = tl.get("cards", [])
    subs = tl.get("subtitles")
    bgm = tl.get("bgm")

    inputs = []
    for c in clips:
        ss = c.get("in", 0)
        dur = c.get("out") - ss if c.get("out") is not None else None
        inputs += ["-ss", str(ss)]
        if dur is not None:
            inputs += ["-t", f"{dur:.3f}"]
        inputs += ["-i", str(c["src"])]

    # 计算总时长(用于字卡 -loop 输入): 各 clip 时长之和
    def _dur(c):
        if c.get("out") is not None:
            return c["out"] - c.get("in", 0)
        return _ffprobe_duration(str(c["src"])) - c.get("in", 0)
    total = sum(_dur(c) for c in clips)

    for card in cards:
        inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(card["png"])]
    if bgm:
        inputs += ["-i", str(bgm["src"])]

    filters = []
    # 1) 各 clip 归一化 + concat
    for i in range(len(clips)):
        filters.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},"
            f"format=yuv420p[v{i}]"
        )
        filters.append(
            f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=48000:"
            f"channel_layouts=stereo[a{i}]"
        )
    concat_in = "".join(f"[v{i}][a{i}]" for i in range(len(clips)))
    filters.append(f"{concat_in}concat=n={len(clips)}:v=1:a=1[vcat][acat]")

    # 2) 字卡 overlay(时间窗 + alpha 淡入淡出)
    cur = "vcat"
    for j, card in enumerate(cards):
        idx = len(clips) + j
        s, e = card["start"], card["end"]
        if card.get("layout") == "fullscreen":
            scale = f"scale={w}:{h},"
        else:
            cw = card.get("width", 0.4)
            scale = f"scale=iw*{cw}:-1,"
        filters.append(
            f"[{idx}:v]{scale}format=rgba,"
            f"fade=t=in:st={s:.3f}:d={fade}:alpha=1,"
            f"fade=t=out:st={e - fade:.3f}:d={fade}:alpha=1[fc{j}]"
        )
        out = f"vc{j}" if j < len(cards) - 1 else "vcard"
        xy = "0:0" if card.get("layout") == "fullscreen" \
            else "(W-w)/2:H-h-80"
        filters.append(
            f"[{cur}][fc{j}]overlay={xy}:"
            f"enable='between(t,{s:.3f},{e:.3f})'[{out}]"
        )
        cur = out

    # 3) 确定视频最终标签(供字幕/BGM 链接)
    if subs:
        v_label = "[vsub]"
    elif cards:
        v_label = "[vcard]"
    else:
        v_label = "[vcat]"

    # 4) 字幕烧录(基于 concat 后的时间轴,ASS 需按最终时间轴写)
    if subs:
        src_v = "[vcard]" if cards else "[vcat]"
        filters.append(
            f"{src_v}subtitles='{_escape_filter_path(str(subs))}'[vsub]"
        )

    # 5) BGM 混音(以口播轨时长为准)
    audio_out = "[acat]"
    if bgm:
        vol = bgm.get("volume", 0.15)
        filters.append(f"[{len(clips) + len(cards)}:a]volume={vol}[bg]")
        filters.append(
            "[acat][bg]amix=inputs=2:duration=first:normalize=0[amix]"
        )
        audio_out = "[amix]"

    cmd = ["ffmpeg", "-y", *inputs,
           "-filter_complex", ";".join(filters),
           "-map", v_label, "-map", audio_out,
           "-c:v", "libx264", "-crf", "18",
           "-c:a", "aac", "-b:a", "192k",
           str(out_path)]
    return cmd


def _ffprobe_duration(video: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def cmd_stitch(args):
    """opc stitch <timeline.json> [-o out.mp4]"""
    tl = load_timeline(args.timeline)
    out = args.output or str(
        Path(args.timeline).with_suffix("").parent / "stitched.mp4")
    cmd = build_command(tl, out)
    print("[stitch] " + " ".join(shlex.quote(c) for c in cmd[:12]) + " ...")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败:\n{proc.stderr[-2000:]}")
    dur = _ffprobe_duration(out)
    print(f"[stitch] 🎬 done → {out} ({dur:.1f}s)")
