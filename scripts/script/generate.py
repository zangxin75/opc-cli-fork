"""LLM narration-script generation via the claude CLI.

Same invocation pattern as card/plan.py: `claude -p` (no model override —
the local CLI is proxy-routed), retry once on validation failure, dump raw
output on failure — never silently return an off-brief script.
"""

import re
import subprocess
from pathlib import Path

from .template import allocate, target_words, DEFAULT_RATE

PROMPT_TEMPLATE = """你是爆款知识类视频文稿策划。按下面的结构与公式,为主题写一篇口播稿。

结构(共 {n_sections} 段,段间空行分隔,不要写段名/序号/任何标记):
{outline}

硬性要求:
1. 全文约 {words} 字(允许 ±10%),这是 {minutes:g} 分钟视频的口播量,每段字数按上面分配执行。
2. 口语化短句,像对朋友讲解,可以有"对吧/你看/说白了"这类语气词,但不要书面语。
3. 去 AI 味(重点,写完自查,交稿前把命中的词全部替换掉):
   - 零容忍书面套话:首先/其次/综上所述/值得注意的是/众所周知/总而言之/不难发现/毋庸置疑——一个都不许出现
   - "然后/最后/总之"合计不超过 4 次,多用别的接法:
     ✗ "首先我们来看原理。其次演示功能。最后总结。"
     ✓ "先说原理啊,其实特简单。功能呢,我直接给你跑一遍。到这儿你大概就明白了。"
   - 不用三段排比、不用"总分总"套路开头结尾
   - 多用第一人称("我试了一下""我当时就愣住了")和具体数字("折腾了一下午""三十多秒出图")
   - 允许自问自答、插入语、说半句话再补("这玩意儿,怎么说呢,很离谱")
4. 平均句长不超过 18 字,像说话的自然停顿,不是写文章。交稿前数一下:按。!?…切句,平均超 18 字就继续拆短。
5. 每个"场景演示"段必须是完整闭环:谁的痛点故事 → 演示过程 → 前后对比(同一输入两种结果)。
6. 选定一个主题词(2~6字,如"技术洞察力"),在升华段首次点题,全篇重复 3~5 次。
7. 收尾段必须有:点题 + 下期预告 + 评论区互动引导。
8. 只输出文稿正文,不要标题、不要 markdown、不要解释。

主题:{topic}
{reference_block}"""

_REFERENCE_BLOCK = """
参考范例(学习其节奏与口吻,不要抄内容):
---
{reference}
---"""


def _validate(text: str, words: int) -> str | None:
    """Return error message if the draft misses the brief, else None."""
    body = text.strip()
    n = len([c for c in body if not c.isspace()])
    if not (0.7 * words <= n <= 1.4 * words):
        return f"字数 {n} 超出目标区间 [{int(0.7 * words)}, {int(1.4 * words)}]"
    if body.startswith(("#", "```", "【")):
        return "输出包含标题/标记,需要纯文稿正文"
    formal = count_formal_markers(body)
    if formal > 0:
        return f"含 {formal} 处书面套话(首先/其次/综上所述/值得注意的是等),需口语化重写"
    soft = count_soft_markers(body)
    if soft > 4:
        return f"连接词 然后/最后/总共出现 {soft} 次,太机械,请换表达"
    avg_len = avg_sentence_length(body)
    if avg_len > 22:
        return f"平均句长 {avg_len:.1f} 字(>22),句子过长不适合口播"
    return None


# 硬禁的书面套话(议论文/报告腔,口播里出现就是 AI 味)
_FORMAL_MARKERS = ("首先", "其次", "综上所述", "值得注意的是", "众所周知", "总而言之", "不难发现", "毋庸置疑")
# 口语里自然但高频出现就机械的连接词(轻限)
_SOFT_MARKERS = ("然后", "最后", "总之")


def count_formal_markers(text: str) -> int:
    """Count bookish transition phrases that mark AI-flavored writing."""
    return sum(text.count(m) for m in _FORMAL_MARKERS)


def count_soft_markers(text: str) -> int:
    return sum(text.count(m) for m in _SOFT_MARKERS)


def avg_sentence_length(text: str) -> float:
    """Mean sentence length in chars, split on 。!?;… (口播的自然停顿)。"""
    sentences = [s for s in re.split(r"[。!?;…]+", text) if s.strip()]
    if not sentences:
        return 0.0
    total = sum(len([c for c in s if not c.isspace()]) for s in sentences)
    return total / len(sentences)


def generate_script(topic: str, minutes: float = 10.0, rate: float = DEFAULT_RATE,
                    reference: str | None = None, raw_dump=None) -> str:
    """Topic -> narration script text. Retries once on validation failure."""
    words = target_words(minutes, rate)
    rows = allocate(minutes, rate)
    outline = "\n".join(f"{i+1}. {name}(~{w} 字):{formula}"
                        for i, (_, name, formula, w) in enumerate(rows))
    reference_block = (_REFERENCE_BLOCK.format(reference=reference.strip())
                       if reference else "")
    prompt = PROMPT_TEMPLATE.format(
        n_sections=len(rows), outline=outline, words=words,
        minutes=minutes, topic=topic, reference_block=reference_block,
    )
    last_err = None
    for attempt in range(3):
        # 重试时把上次的校验失败原因回喂给模型,避免同样的错误再犯
        attempt_prompt = prompt
        if attempt > 0 and last_err:
            attempt_prompt = (
                f"{prompt}\n\n【注意】上一稿未通过审核,原因:{last_err}\n"
                f"请重写一稿,必须解决上述问题(尤其逐句检查,不要出现禁用词,"
                f"句子改短,改成说话的语气)。只输出文稿正文。"
            )
        proc = subprocess.run(
            ["claude", "-p", attempt_prompt],
            capture_output=True, text=True, timeout=600,
        )
        draft = proc.stdout.strip()
        err = _validate(draft, words) if draft else f"empty output; stderr={proc.stderr[:200]}"
        if err is None:
            return draft
        last_err = err
        if raw_dump:
            Path(raw_dump).write_text(draft, encoding="utf-8")
    raise RuntimeError(
        f"generate_script failed after retry: {last_err}. "
        + (f"Raw model output saved to {raw_dump}" if raw_dump else "")
    )
