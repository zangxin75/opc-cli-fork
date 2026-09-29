"""CLI entrypoints for `opc script` subcommand."""

import subprocess
from pathlib import Path

from .analyze import analyze_srt, report_text
from .template import outline_text


def cmd_script_template(args):
    print(outline_text(args.minutes, args.rate))


def cmd_script_new(args):
    from .generate import generate_script

    reference = None
    if args.reference:
        reference = Path(args.reference).read_text(encoding="utf-8")
    out = Path(args.output or "script.txt")
    draft = generate_script(
        args.topic, minutes=args.minutes, rate=args.rate,
        reference=reference,
        raw_dump=out.with_suffix(".raw.txt"),
    )
    out.write_text(draft + "\n", encoding="utf-8")
    n = len([c for c in draft if not c.isspace()])
    print(f"[script] {n} chars (~{n / args.rate / 60:.1f} min at {args.rate:g} chars/s) → {out}")
    print(f"[script] next: opc tts --stdin -i {out} ... && opc card auto <video> {out}")


def cmd_script_analyze(args):
    src = Path(args.input)
    if src.suffix.lower() == ".srt":
        srt_path = src
    else:
        # audio/video: extract 16k mono wav, run ASR pipeline, then analyze
        from asr.pipeline import run_pipeline

        workdir = Path(args.workdir or src.parent / "opc_script_analyze")
        workdir.mkdir(parents=True, exist_ok=True)
        wav = workdir / (src.stem + ".wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-vn", "-ar", "16000", "-ac", "1", str(wav)],
            check=True, capture_output=True,
        )
        result = run_pipeline(str(wav), str(workdir), fmt="srt")
        if "check_errors" in result:
            print(f"[script] warning: ASR check issues: {result['check_errors'][:2]}")
        srt_path = Path(result["srt"])
        print(f"[script] asr → {srt_path}")

    stats = analyze_srt(srt_path.read_text(encoding="utf-8-sig"), gap=args.gap)
    report = report_text(stats)
    print(report)
    if args.output:
        Path(args.output).write_text(report + "\n", encoding="utf-8")
        print(f"[script] report → {args.output}")
