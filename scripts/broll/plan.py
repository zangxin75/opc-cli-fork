"""B-roll planning: narration script → broll.json shot list via claude CLI.

Mirrors card/plan.py's calling convention: `claude -p --output-format json`,
retry once on schema failure, raw dump on final failure.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

PROMPT_TEMPLATE = """你是视频配图(B-roll)策划。根据下面的口播稿,规划一组随内容切换的配图,用于 1280x720 视频。

要求:
1. 只输出一个 JSON 对象,不要 markdown 围栏、不要解释。
2. 结构:{{"style":"统一风格前缀(英文,与画面描述拼接)","shots":[...]}}
3. 每个镜头:{{"keyword":"定位短语","prompt":"英文画面描述"}}
   - keyword 必须逐字取自口播稿原文的 4~10 字名词短语(不能改写、不能加标点、不要整句)
   - 优先挑不含英文字母和数字的短语(ASR 对英文/数字的转写不稳定)
   - 同一 keyword 不得出现两次,且不能与口播稿里的卡片定位短语重复使用同一句
   - prompt:15~40 个英文单词,具体、有画面感,与该段口播内容直接相关(比如口播讲"字幕流水线",画面就是字幕滚动的工作台,不要画不相干的风景)
4. 密度:每 60~100 字一个镜头,覆盖全篇;10 分钟视频约 18~28 张,最多 30 张。
   - keyword 再强调:必须是纯中文!不能含 AI、CLI、OPC 这类英文缩写(ASR 转写会变,匹配会失败)。
     ✗ "AI 创作工作室" ✓ "创作工作室"
     ✗ "OPC工具箱"    ✓ "命令行工具"
5. style:全组统一的后缀风格描述(如 "cinematic lighting, dark purple and gold tones, high detail, no text"),保证整片视觉一致。
6. prompt 里禁止出现文字类要求(画面中不要出现文字、字幕、水印)。

口播稿:
---
{script}
---"""


def _extract_json(text: str) -> dict:
    """Parse model output as JSON, tolerating stray markdown fences."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def _shot_problem(s, seen: set) -> str | None:
    """Return why a shot is invalid, or None if it's fine."""
    kw = s.get("keyword", "")
    if not (4 <= len(kw) <= 10) or not kw.strip():
        return f"keyword {kw!r} 长度需 4~10 字"
    if any(c.isascii() and c.isalnum() for c in kw):
        return f"keyword {kw!r} 含英文字母/数字(ASR 匹配会失败)"
    if kw in seen:
        return f"keyword {kw!r} 重复"
    if not s.get("prompt") or len(s["prompt"]) < 10:
        return f"keyword {kw!r} 的 prompt 过短"
    return None


def validate_shots(shots: list) -> None:
    """Schema check: keyword 4~10 chars, prompts non-empty, keywords unique."""
    if not isinstance(shots, list) or not shots:
        raise ValueError("empty shots array")
    seen = set()
    problems = []
    for s in shots:
        p = _shot_problem(s, seen)
        if p:
            problems.append(p)
        else:
            seen.add(s["keyword"])
    if problems:
        raise ValueError("; ".join(problems[:5]))


def filter_valid_shots(shots: list, min_keep: int = 3, max_keep: int = 30) -> list:
    """Drop invalid shots individually (graceful degradation) instead of
    failing the whole plan. Raises only if fewer than min_keep survive;
    over max_keep, keeps an evenly-spaced subset covering the whole script."""
    seen, kept, dropped = set(), [], []
    for s in shots:
        p = _shot_problem(s, seen)
        if p:
            dropped.append(p)
        else:
            seen.add(s.get("keyword", ""))
            kept.append(s)
    if len(kept) < min_keep:
        raise ValueError(
            f"only {len(kept)}/{len(shots)} shots valid: {'; '.join(dropped[:5])}"
        )
    if dropped:
        print(f"[broll] dropped {len(dropped)} invalid shots: "
              f"{'; '.join(dropped[:3])}{'…' if len(dropped) > 3 else ''}",
              file=sys.stderr)
    if len(kept) > max_keep:
        step = len(kept) / max_keep
        kept = [kept[min(int(i * step), len(kept) - 1)] for i in range(max_keep)]
        print(f"[broll] capped to {max_keep} shots (evenly spaced)",
              file=sys.stderr)
    return kept


def plan_broll(script_text: str, raw_dump=None) -> dict:
    prompt = PROMPT_TEMPLATE.format(script=script_text)
    last_err = None
    for attempt in range(3):
        # 重试时把校验错误回喂,提示模型修正 keyword
        attempt_prompt = prompt
        if attempt > 0 and last_err:
            attempt_prompt = (
                f"{prompt}\n\n【注意】上一版的 keyword 有问题:{last_err}\n"
                f"keyword 必须逐字取自口播稿、纯中文、4~10 字。请修正后重新输出完整 JSON。"
            )
        proc = subprocess.run(
            ["claude", "-p", attempt_prompt, "--output-format", "json"],
            capture_output=True, text=True, timeout=300,
        )
        try:
            outer = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            last_err = f"claude CLI output not JSON: {e}; stderr={proc.stderr[:200]}"
            continue
        if outer.get("is_error"):
            last_err = f"claude CLI error: {outer.get('result', '')[:300]}"
            continue
        try:
            plan = _extract_json(outer["result"])
            shots = filter_valid_shots(plan["shots"])
            return {"style": plan.get(
                "style",
                "cinematic lighting, dark purple tones, high detail, no text"),
                "shots": shots}
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            last_err = str(e)
            if raw_dump:
                Path(raw_dump).write_text(outer.get("result", proc.stdout),
                                          encoding="utf-8")
    raise RuntimeError(
        f"plan_broll failed after retry: {last_err}. "
        + (f"Raw model output saved to {raw_dump}" if raw_dump else "")
    )
