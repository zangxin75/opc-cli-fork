"""L3 planning: generate cards.json from a narration script via claude CLI.

Uses `claude -p --output-format json` (no --model override: the local CLI is
proxy-routed and explicit model names are unreliable). Retries once on
schema failure, then dumps raw output for manual fixing — never silently
produces invalid JSON.
"""

import json
import re
import subprocess
from pathlib import Path

from .compose import validate_timing

PROMPT_TEMPLATE = """你是视频知识卡片策划。根据下面的口播稿，生成用于渲染 1280x720 知识卡片的 JSON。

要求：
1. 只输出一个 JSON 对象，不要 markdown 围栏、不要解释。
2. 结构：{{"theme":"dark-purple-gold","cards":[...],"timing":[...]}}
3. 每张卡：{{"id":"小写英文短横线","layout":"fullscreen","eyebrow":"顶部引导语(可省略)","title":"主标题，可用<em>强调</em>标记一处","bullets"/"steps"/"comparison" 三选一,"footer":"底部注释(可省略)"}}
   - layout: "fullscreen"（默认，整屏排版卡，替换画面）或 "card"（底部小卡片，叠加在画面上）
   - bullets: 要点列表（字符串数组）
   - steps: 流程步骤（字符串数组，渲染为箭头流程图）
   - comparison: {{"cols":[{{"head":"栏头","body":"栏内容"}}]}}，2~3 栏，body 为短文本
4. timing: 每张卡一条 {{"card":"对应卡id","keyword":"定位短语"}}
   - keyword 必须逐字取自口播稿原文的 4~10 字名词短语（不能改写、不能加标点、不要整句）
   - 优先挑不含英文字母和数字的短语（ASR 对英文/数字的转写不稳定）
   - 同一 keyword 不得出现两次
   - duration 字段可省略——停留时长由系统按该句语音实际时长自动推导
5. 卡片数量：口播稿每 200~400 字一张，最多 8 张；只提炼真正值得做成卡片的核心观点/流程/对比。
6. 卡上文字必须精炼（每条不超过 20 字），卡片不是字幕。

口播稿：
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


def plan_cards(script_text: str, raw_dump=None) -> dict:
    prompt = PROMPT_TEMPLATE.format(script=script_text)
    last_err = None
    for attempt in range(2):
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
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
            cards = plan["cards"]
            timing = plan.get("timing", [])
            if not isinstance(cards, list) or not cards:
                raise ValueError("empty cards array")
            validate_timing(cards, timing)  # id refs + keyword uniqueness
            return {"theme": plan.get("theme", "dark-purple-gold"),
                    "cards": cards, "timing": timing}
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            last_err = str(e)
            if raw_dump:
                Path(raw_dump).write_text(outer.get("result", proc.stdout),
                                          encoding="utf-8")
    raise RuntimeError(
        f"plan_cards failed after retry: {last_err}. "
        + (f"Raw model output saved to {raw_dump}" if raw_dump else "")
    )
