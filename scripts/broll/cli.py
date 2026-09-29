"""broll subcommand handlers: plan / generate / bg."""

import json
from pathlib import Path

from card.compose import find_keyword_span, parse_srt
from image.comfyui import check_connection
from shared.config import load_config

from .bg import build_bg
from .generate import DEFAULT_WORKFLOW, generate_broll
from .plan import plan_broll


def cmd_broll_plan(args):
    script = Path(args.script)
    plan = plan_broll(script.read_text(encoding="utf-8"),
                      raw_dump=script.parent / "broll.plan.raw.txt")
    out = Path(args.output or script.parent / "broll.json")
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[broll] planned {len(plan['shots'])} shots → {out}")


def cmd_broll_generate(args):
    cfg = load_config()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if not check_connection(cfg):
        raise SystemExit("Error: ComfyUI 未运行,先启动 ~/comfyui/start.sh")
    generate_broll(plan, args.outdir or Path(args.plan).parent / "broll_png",
                   cfg, workflow_alias=args.workflow,
                   on_shot=lambda i, kw, png: print(f"[broll] {i + 1}/{len(plan['shots'])} {kw} → {png}"))


def cmd_broll_bg(args):
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    srt_text = Path(args.srt).read_text(encoding="utf-8")
    entries = parse_srt(srt_text)
    pngs = sorted(Path(args.png_dir).glob("*.png"))
    if not pngs:
        raise SystemExit(f"Error: {args.png_dir} 下没有 PNG")

    # shots 与 PNG 按序号对应(生成时用 00_ 01_ 前缀)
    segments, misses = [], []
    for shot, png in zip(plan["shots"], pngs):
        try:
            start, end = find_keyword_span(entries, shot["keyword"])
        except ValueError:
            misses.append(shot["keyword"])
            continue
        segments.append((png, start, end))
    if misses:
        print(f"[broll] warning: {len(misses)} 个 keyword 未命中,已跳过: {misses[:3]}",
              file=sys.stderr)
    segments.sort(key=lambda s: s[1])
    total = entries[-1].end + 1.0  # 收尾留 1s
    out = args.output or str(Path(args.plan).parent / "base.mp4")
    build_bg(segments, args.voice, total, out, dry_run=args.dry_run)
    print(f"[broll] bg: {len(segments)} 段 × xfade → {out}")


def cmd_broll(args):
    action = getattr(args, "broll_action", None)
    if action == "plan":
        cmd_broll_plan(args)
    elif action == "generate":
        cmd_broll_generate(args)
    elif action == "bg":
        cmd_broll_bg(args)
    else:
        print("Usage: opc broll <plan|generate|bg>")
        print("  plan <script.txt> [-o broll.json]     LLM-plan B-roll shots")
        print("  generate <broll.json> [--workflow w]  Generate PNGs via ComfyUI")
        print("  bg <broll.json> <srt> <voice.mp3>     Multi-image background video")
