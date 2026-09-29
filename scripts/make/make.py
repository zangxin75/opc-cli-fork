"""opc make — 一键全链路成片。

阶段链(每步完成即落盘 make_state.json,--resume-from 断点续跑):
  script → tts → asr → avatar-image → avatar-video →
  card-plan → card-render → compose → burn

设计文档: /home/zhy/project/opc/docs/designs/2026-09-27-opc-make-v4.md
"""

import json
import subprocess
import sys
from pathlib import Path

from asr.pipeline import run_pipeline
from avatar.generate import frame_count, render_segment
from avatar.plan import plan_segments, segment_audio_times
from card.compose import compose_cards, parse_srt
from card.plan import plan_cards
from card.render import render_cards
from script.generate import generate_script
from shared.config import load_config
from tts.edge_engine import tts_edge

STAGES = ["script", "tts", "asr", "avatar-image", "avatar-video",
          "card-plan", "card-render", "compose", "burn"]


def _ffprobe_duration(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _patch_ass_style(text: str, style: str) -> str:
    """把第一条 Style 行整体替换为 style(含 Name 字段)。

    回归教训:曾用 first + "," + style 拼接,first 已含 Name 而 style 又以
    Name 开头 → 字段整体错位(Fontsize 变成字体名)→ libass 样式失效,
    全片字幕不渲染。因此这里必须整行替换。
    """
    lines, patched = [], False
    for ln in text.splitlines():
        if ln.startswith("Style:") and not patched:
            ln = "Style: " + style
            patched = True
        lines.append(ln)
    return "\n".join(lines) + "\n"


def _run_burn(video: str, ass: str, out: str):
    """卡拉OK字幕烧录 + 底部样式(沿用 v2 验证过的 Style)。"""
    style = ("Karaoke,Source Han Sans SC,50,&H0000D7FF,&H00FFFFFF,&H00000000,"
             "&H33000000,-1,0,0,0,100,100,0,0,1,3,2,2,10,10,60,1")
    ass_path = Path(ass)
    ass_path.write_text(
        _patch_ass_style(ass_path.read_text(encoding="utf-8"), style),
        encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video, "-vf", f"ass={ass}",
         "-c:v", "libx264", "-crf", "18", "-c:a", "copy", out],
        check=True, capture_output=True,
    )


class Maker:
    def __init__(self, args):
        self.args = args
        self.workdir = Path(args.workdir or Path.cwd() / "opc_make")
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.workdir / "make_state.json"
        self.state = self._load_state()
        self.cfg = load_config()

    # ---- state ---------------------------------------------------------
    def _load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"done": [], "paths": {}}

    def _save(self):
        self.state_path.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _record(self, stage: str, **paths):
        self.state["done"].append(stage)
        # 存绝对路径:resume 时 CWD 可能不同,相对路径会失效
        self.state["paths"].update(
            {k: str(Path(v).resolve()) for k, v in paths.items()})
        self._save()
        print(f"[make] ✓ {stage}")

    def _pending(self) -> list:
        if self.args.resume_from:
            i = STAGES.index(self.args.resume_from)
            return STAGES[i:]
        skip = set(self.state["done"])
        return [s for s in STAGES if s not in skip]

    # ---- stages --------------------------------------------------------
    def stage_script(self):
        p = self.workdir / "script.txt"
        if self.args.script:
            p = Path(self.args.script)
        else:
            text = generate_script(self.args.topic, minutes=self.args.minutes)
            p.write_text(text, encoding="utf-8")
        self.script = p
        self._record("script", script=p)

    def stage_tts(self):
        out = self.workdir / "voice.mp3"
        voice = self.cfg.get("edge_voice", "zh-CN-XiaoxiaoNeural")
        tts_edge(self.script.read_text(encoding="utf-8"), voice, str(out))
        self.voice = out
        self._record("tts", voice=out)

    def stage_asr(self):
        # fmt="all": SRT 给 avatar 切段/card 定位用,ASS 给烧录用
        result = run_pipeline(str(self.voice), str(self.workdir), fmt="all")
        if "check_errors" in result:
            raise RuntimeError(f"ASR check failed: {result['check_errors'][:3]}")
        self.srt = Path(result["srt"])
        self.ass = Path(result["ass"])
        self._record("asr", srt=self.srt, ass=self.ass)

    def stage_avatar_image(self):
        src = Path(self.args.avatar_image)
        if not src.exists():
            raise SystemExit(f"Error: 参考照片不存在: {src}")
        out = self.workdir / "avatar.png"
        # 规范化到 832x480(与 S2V 输出同比例,避免内部变形)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(src),
             "-vf", "scale=832:480:force_original_aspect_ratio=increase,"
                    "crop=832:480", str(out)],
            check=True, capture_output=True,
        )
        self.avatar_png = out
        self._record("avatar-image", avatar_png=out)

    def stage_avatar_video(self):
        entries = parse_srt(self.srt.read_text(encoding="utf-8"))
        voice_dur = _ffprobe_duration(self.voice)
        segs = plan_segments(entries)
        times = segment_audio_times(segs, voice_duration=voice_dur)
        seg_dir = self.workdir / "avatar_segs"
        seg_dir.mkdir(exist_ok=True)
        parts = []
        for i, (ss, to) in enumerate(times):
            mp4 = seg_dir / f"seg_{i:03d}.mp4"
            if not mp4.exists():  # 段级断点:已有则跳过
                mp3 = seg_dir / f"seg_{i:03d}.mp3"
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-ss", f"{ss:.3f}",
                     "-to", f"{to:.3f}", "-i", str(self.voice), str(mp3)],
                    check=True, capture_output=True,
                )
                frames = frame_count(to - ss)
                print(f"[make] avatar seg {i + 1}/{len(times)} "
                      f"({to - ss:.1f}s → {frames}f)")
                got = render_segment(str(self.avatar_png), str(mp3), frames,
                                     str(seg_dir), seed=42 + i,
                                     prefix=f"avatar/seg{i:03d}")
                if got != mp4:
                    got.rename(mp4)
            parts.append(mp4)
        # concat
        out = self.workdir / "base.mp4"
        concat_list = seg_dir / "concat.txt"
        concat_list.write_text(
            "".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
        merged = seg_dir / "merged.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
             "-i", str(concat_list), "-c", "copy", str(merged)],
            check=True, capture_output=True,
        )
        # 音轨重铺:段视频帧数向上取整会累积漂移,用完整原始音轨替换;
        # -shortest 截掉末段多渲染的帧
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(merged),
             "-i", str(self.voice), "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-shortest", str(out)],
            check=True, capture_output=True,
        )
        self.base = out
        self._record("avatar-video", base=out)

    def stage_card_plan(self):
        plan = plan_cards(self.script.read_text(encoding="utf-8"),
                          raw_dump=self.workdir / "card.plan.raw.txt")
        p = self.workdir / "cards.json"
        p.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        self.cards = p
        self._record("card-plan", cards=p)

    def stage_card_render(self):
        plan = json.loads(self.cards.read_text(encoding="utf-8"))
        png_dir = self.workdir / "card_png"
        render_cards(plan["cards"], png_dir)
        self.card_png = png_dir
        self._record("card-render", card_png=png_dir)

    def stage_compose(self):
        plan = json.loads(self.cards.read_text(encoding="utf-8"))
        for t in plan["timing"]:
            t["_png_dir"] = str(self.card_png)
        out = self.workdir / "final.mp4"
        compose_cards(str(self.base), str(self.srt), plan["cards"],
                      plan["timing"], str(out))
        self.final = out
        self._record("compose", final=out)

    def stage_burn(self):
        out = self.args.output or (self.workdir / "final_burned.mp4")
        _run_burn(str(self.final), str(self.ass), str(out))
        self._record("burn", final_burned=out)
        dur = _ffprobe_duration(out)
        print(f"[make] 🎬 done → {out} ({dur:.1f}s)")

    # ---- driver --------------------------------------------------------
    def run(self):
        handlers = {
            "script": self.stage_script, "tts": self.stage_tts,
            "asr": self.stage_asr,
            "avatar-image": self.stage_avatar_image,
            "avatar-video": self.stage_avatar_video,
            "card-plan": self.stage_card_plan, "card-render": self.stage_card_render,
            "compose": self.stage_compose, "burn": self.stage_burn,
        }
        # 恢复上下文:把已产出路径挂回属性(统一转回 Path)
        def P(key):
            v = self.state["paths"].get(key)
            return Path(v) if v else None

        self.script = P("script")
        self.voice = P("voice")
        self.srt = P("srt")
        self.ass = P("ass")
        self.avatar_png = P("avatar_png")
        self.base = P("base")
        self.cards = P("cards")
        self.card_png = P("card_png")
        self.final = P("final")

        pending = self._pending()
        if not pending:
            print("[make] 全部阶段已完成,--resume-from 可重跑指定阶段")
        for stage in pending:
            print(f"[make] running: {stage}")
            handlers[stage]()
        return self.state


def cmd_make(args):
    Maker(args).run()
