"""Viral-script structure template for narration design.

Pure functions, zero IO. The 8-section skeleton was distilled from
frame-by-frame + transcript analysis of the reference video
(BV1aXQbBcEFk): hook -> intro -> 3x (story/demo/contrast) -> method ->
outro, with the theme phrase repeated 3-5 times as the through-line.
"""

# (key, 中文名, 字数占比, 写作公式)
SECTIONS = [
    ("hook",    "钩子",        0.12, "价值承诺+反差或悬念,30秒内说清'这视频为什么值得看'"),
    ("intro",   "是什么/怎么拿", 0.10, "一句话定义 + 获取或使用路径,降低尝试门槛"),
    ("demo_a",  "场景演示A",    0.20, "痛点故事 → 功能演示 → 前后对比(同一场景两种结果)"),
    ("insight", "升华",        0.08, "从功能跳到方法论,主题词第一次点题"),
    ("demo_b",  "场景演示B",    0.18, "第二个痛点场景 → 演示 → 对比"),
    ("demo_c",  "场景演示C",    0.18, "第三个场景,叠加组合/魔改的想象空间(商机)"),
    ("method",  "方法论",      0.08, "可迁移的习惯或信息源,主题词再次点题"),
    ("outro",   "收尾",        0.06, "点题 + 下期预告 + 评论区互动引导"),
]

DEFAULT_RATE = 5.0  # chars/sec: edge-tts 中文实测 ~4.7,真人口播 ~5.5


def target_words(minutes: float, rate: float = DEFAULT_RATE) -> int:
    """Total script characters for a target duration."""
    return int(minutes * 60 * rate)


def allocate(minutes: float, rate: float = DEFAULT_RATE) -> list:
    """Per-section word budgets. Returns [(key, name, formula, words), ...]."""
    total = target_words(minutes, rate)
    rows = [(k, n, f, int(total * share)) for k, n, share, f in SECTIONS]
    # rounding drift goes to the largest section (demo_a) so sum == total
    drift = total - sum(r[3] for r in rows)
    if drift:
        rows[2] = (rows[2][0], rows[2][1], rows[2][2], rows[2][3] + drift)
    return rows


def outline_text(minutes: float, rate: float = DEFAULT_RATE) -> str:
    """Human-readable outline: section budgets + formulas."""
    lines = [f"目标 {minutes:g} 分钟 × {rate:g} 字/秒 ≈ {target_words(minutes, rate)} 字"]
    for k, name, formula, words in allocate(minutes, rate):
        lines.append(f"  [{k}] {name}: ~{words} 字 — {formula}")
    return "\n".join(lines)
