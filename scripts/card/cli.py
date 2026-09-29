"""CLI entrypoints for `opc card` subcommand."""

import json
import subprocess
from pathlib import Path

from .compose import compose_cards
from .render import render_cards


def _load_cards(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cards = data.get("cards")
    if not cards:
        raise ValueError(f"no 'cards' array in {path}")
    return data, cards


def cmd_card_render(args):
    data, cards = _load_cards(args.cards_json)
    pngs = render_cards(cards, args.outdir)
    for p in pngs:
        print(f"[card] rendered {p}")
    if data.get("timing"):
        print(f"[card] {len(data['timing'])} timing entries found; "
              f"compose with: opc card compose <video> <srt> {args.cards_json}")


def cmd_card_compose(args):
    data, cards = _load_cards(args.cards_json)
    timing = data.get("timing")
    if not timing:
        raise ValueError(
            "cards.json has no 'timing' section. Add timing "
            "[{card, keyword, duration}] or use manual --at."
        )
    for t in timing:
        t["_png_dir"] = str(Path(args.outdir or Path(args.cards_json).parent).resolve())
    out = compose_cards(
        video=args.video,
        srt_path=args.srt,
        cards=cards,
        timing=timing,
        out_path=args.output or str(Path(args.video).with_name(
            Path(args.video).stem + "_cards.mp4")),
        card_width=args.card_width,
        margin=args.margin,
    )
    print(f"[card] composed → {out}")


def cmd_card_plan(args):
    from .plan import plan_cards

    script = Path(args.script).read_text(encoding="utf-8")
    result = plan_cards(script, raw_dump=Path(args.script).with_suffix(".raw.txt"))
    out = Path(args.output or Path(args.script).with_suffix(".cards.json"))
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[card] planned {len(result['cards'])} cards → {out}")


def cmd_card_auto(args):
    """Full L3 chain: extract audio → asr → plan → render → compose."""
    from asr.pipeline import run_pipeline

    video = Path(args.video)
    script = Path(args.script)
    workdir = Path(args.workdir or video.parent) / "opc_card_auto"
    workdir.mkdir(parents=True, exist_ok=True)

    # 1. audio extraction
    audio = workdir / (video.stem + ".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vn", "-ar", "16000", "-ac", "1", str(audio)],
        check=True, capture_output=True,
    )
    # 2. ASR → SRT
    result = run_pipeline(str(audio), str(workdir), fmt="srt")
    if "check_errors" in result:
        raise RuntimeError(
            "ASR check failed (lines too long); run 'opc asr-split' on the "
            f"audio then retry. Details: {result['check_errors'][:3]}"
        )
    srt = result["srt"]
    print(f"[card] asr → {srt}")
    # 3. plan
    from .plan import plan_cards

    plan = plan_cards(script.read_text(encoding="utf-8"),
                      raw_dump=workdir / "plan.raw.txt")
    (workdir / "cards.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[card] plan → {len(plan['cards'])} cards")
    # 4. render
    png_dir = workdir / "png"
    render_cards(plan["cards"], png_dir)
    # 5. compose
    for t in plan["timing"]:
        t["_png_dir"] = str(png_dir)
    out = args.output or str(workdir / (video.stem + "_cards.mp4"))
    compose_cards(str(video), srt, plan["cards"], plan["timing"], out,
                  card_width=args.card_width, margin=args.margin)
    print(f"[card] auto done → {out}")
