---
name: opc
description: "多引擎 AI 创作工具链。TTS 语音合成、ASR 与字幕、MiniMax Music3 音乐生成、音频压缩分析、ComfyUI 图片生成与编辑、MiniMax H3 和 LTX 视频生成、SeedVR2 超分、视频转录/理解和字幕级剪辑。使用场景：(1) 文本转语音，(2) 音频转录与字幕，(3) 音乐生成与音频处理，(4) AI 图片生成和编辑，(5) H3 文生视频/图生视频/全能参考视频，(6) LTX 图生视频与首尾帧视频，(7) 视频超分、理解和剪辑。触发词：语音、TTS、ASR、字幕、音乐生成、Music3、音频压缩、图片生成、图片编辑、视频生成、H3、LTX、SeedVR2、视频理解、prompt、知识图谱、KG、视频剪辑"
---

# opc - AI 创作工具链

TTS + ASR + 音频处理 + AI 图片生成/编辑 + MiniMax H3/LTX 视频生成与理解 + 视频剪辑。

## 环境安装

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
cd ~/.claude/skills/opc-cli
uv sync
```

跨平台：Linux 用 CUDA，macOS 用 MLX，命令一致。

**模型下载源：**
```bash
opc config --set-model-source modelscope   # 默认
opc config --set-model-source huggingface  # 备选
opc config --set-model-cache-dir /vol2/1000/llm/models
```

## 快速开始

```bash
opc discover --set-default          # 发现播放设备
opc tts "你好" -e edge-tts          # 生成语音
opc say "你好"                       # 生成并播放
opc asr audio.mp3 --format srt      # 生成字幕
opc music --caption "Warm indie pop" --lyrics-file lyrics.txt  # 生成音乐
opc image -w ernie-turbo -p "a cat"  # AI 生图
opc video -w h3-t2v -p "a rainy neon street"  # H3 视频
opc video-gen i2v --image frame.png -p "slow camera push-in"  # 图生视频
opc image kg skeleton subject:food style:photography  # KG prompt 规划
```

所有命令通过 `uv run python scripts/opc.py` 执行。

## TTS 命令

### `opc tts <text>` — 生成语音文件

```bash
opc tts "你好" -e edge-tts                           # edge-tts
opc tts "你好" -e edge-tts --rate +20% --pitch +5Hz  # 带语速/音调
opc tts "你好" -e qwen --speaker Vivian              # qwen 内置音色
opc tts "你好" -e qwen --instruct "用愤怒的语气说"    # 情绪指令
opc tts "你好" -e qwen --mode voice_design --instruct "温柔的女声"  # 声音设计
opc tts "你好" -e qwen --mode voice_clone --ref-audio ref.wav --ref-text "参考"  # 克隆
```

**参数：** `-e` 引擎(edge-tts|qwen)、`-v` 音色、`-l` 语言、`-o` 输出路径、`--stdin` 从 stdin 读
**edge-tts：** `--rate`、`--pitch`、`--volume`
**qwen：** `-m` 模式(custom_voice|voice_design|voice_clone)、`-s` 音色、`-i` 情绪指令、`--ref-audio`、`--ref-text`

### `opc say <text>` — 生成并播放

参数同 `tts`，额外 `-d` 指定播放设备。

### `opc voices` / `opc discover`

```bash
opc voices -e edge-tts   # 322 个音色
opc voices -e qwen       # 9 个内置音色
opc discover --set-default
```

## ASR Pipeline

4 阶段 Pipeline：ASR + Forced Alignment → Sentence Breaking → CSV Fix → Render

```bash
opc asr audio.mp3                    # 转录到 stdout
opc asr audio.mp3 --format srt       # 生成 SRT + ASS
opc asr audio.mp3 --format json -o result.json
opc asr audio.mp3 --format srt --fix-dir ./fixes             # CSV 修正
opc asr audio.mp3 --format srt --resume-from break           # 从断句阶段恢复
```

**参数：** `--format`(text|json|srt|ass)、`--language`、`--model-size`(1.7B|0.6B)、`--style`、`--fix-dir`、`--resume-from`(asr|break|fix|render)

### 断句规则

两遍扫描：Pass 1 按句号分段，Pass 2 按逗号断行。**没有标点绝对不断行。** 超长行由 Check 标记，用 `opc asr-split` 手动拆分：

```bash
opc asr-split audio.lines.json --line 10 --after "理解，"
opc asr audio.mp3 --format srt --resume-from render
```

### CSV 修正格式

在 `--fix-dir` 放 `fix_1.csv`, `fix_2.csv`...，格式：`原文本，新文本`（新文本留空=删除行）。`#` 开头为注释。

## Image 命令

AI 图片生成 + 图片编辑 + Prompt 知识图谱 + 模板系统。**详见 [references/image.md](references/image.md)**。

工作流从 `~/.opc_cli/opc/workflows/` 和仓库内置目录合并发现，用户目录中的同名 alias 优先。用 `opc image list` 查看本机实际可用的图片和视频工作流。

核心流程：
```bash
opc image list                                        # 列出可用工作流
opc image -w ernie-full -p "..."                      # 文生图
opc image -w ideogram4 --text -p "poster design"       # Ideogram 4 生图
opc image-edit --image photo.png -p "add a red hat"   # 图片编辑
opc image kg skeleton subject:food style:photography   # KG 规划
opc image analyze output.png --describe               # 分析
```

### `opc image list` / `info` / `import` — 工作流管理

```bash
opc image list                    # 列出可用工作流
opc image info ernie-turbo        # 查看工作流参数详情
opc image import workflow.json --name my-workflow  # 导入工作流
```

### `opc image analyze` — 图片/工作流分析

```bash
opc image analyze output.png --describe     # 视觉模型描述图片
opc image analyze output.png --describe --compare ref.png  # 对比两张图片
opc image analyze workflow.json             # 分析工作流 JSON 结构
```

### `opc image test` — 工作流连通性测试

```bash
opc image test ernie-turbo --prompt "test image"  # 测试工作流连通性
```

### `opc image` — 文生图

```bash
opc image -w ernie-turbo -p "a cat sitting on a windowsill"
opc image -w ernie-full -p '{"subject":"美食摄影","style":"photography"}'
opc image -w klein -p "a beautiful landscape"
```

**参数：** `-w` 工作流别名、`-p` 提示词、`-P` 工作流参数 `key=value`、`--text` 纯文本模式

### `opc image-edit` — 图片编辑

基于 Klein-Edit 等工作流的图片编辑，需要提供输入图片和编辑指令。

```bash
opc image-edit --image photo.png -p "add a red hat to the person"
opc image-edit -w klein-edit --image photo.png -p "make it look like a painting"
opc image-edit --image ref1.png --image ref2.png -p "blend these two images"
opc image-edit --image photo.png -p "add sunset" --param steps=30 --param seed=42
```

**参数：** `-w` 工作流别名(默认 `klein-edit`)、`--image/-i` 输入图片(可多次)、`-p` 编辑指令(必需)、`-P` 工作流参数、`--text` 纯文本模式

### `opc image kg` — Prompt 知识图谱

```bash
opc image kg list                              # 列出所有实体分类
opc image kg list --category style             # 按分类筛选
opc image kg info style:photography            # 实体详情
opc image kg search portrait                   # 模糊搜索
opc image kg query style:cyberpunk            # 查询搭配推荐
opc image kg skeleton subject:food lighting:neon  # 生成 prompt 骨架
opc image kg validate subject:cat style:photography lighting:dramatic  # 验证组合
opc image kg similar subject:cat               # 查找相似 prompt
opc image kg templates                         # 列出模板
opc image kg templates --entity style:cyberpunk  # 按实体查模板
```

## Video 命令

视频生成依赖 ComfyUI 工作流。默认 alias 为 `ltx-i2v` 和 `ltx-flf`，需先确认它们出现在 `opc image list` 中。

```bash
# 单图动画化
opc video-gen i2v --image frame.png -p "camera slowly zooms in"

# 首尾帧过渡
opc video-gen flf --first-frame start.png --last-frame end.png -p "smooth cinematic transition"

# 更快的蒸馏模式
opc video-gen i2v --image frame.png -p "slow motion" --turbo

# 下载在线视频并用 Qwen3-ASR 转录（需要 yt-dlp 和 ffmpeg）
opc video-transcribe "https://example.com/video"

# 使用 OpenAI-compatible 视觉接口理解本地视频
opc video-describe video.mp4
```

**生成参数：** `--workflow/-w` 工作流、`--prompt/-p` 运动描述、`--param/-P key=value` 参数覆盖、`--output/-o` 输出目录、`--turbo` 快速模式。

**视频理解配置：** `opc config --set-video-desc-api-url <url>`、`--set-video-desc-model <name>`，API key 可单独设置，也可复用图片视觉模型配置。

## Audio 命令

音频压缩与分析工具。

```bash
opc audio compress input.mp3 --preset voice   # 人声压缩预设
opc audio compress input.mp3 -t -20 -r 4 -a 10 --release 130  # 自定义参数
opc audio analyze input.mp3                   # 分析响度 (LUFS)
opc audio presets                              # 列出可用预设
```

**压缩参数：** `-t, --threshold` 阈值 dB (默认 -20.0)、`-r, --ratio` 压缩比 (默认 4.0)、`-a, --attack` 启动时间 ms (默认 10.0)、`--release` 释放时间 ms (默认 130.0)、`--knee` 拐点宽度 dB (默认 0.0)、`--makeup` 补偿增益 dB (默认 0.0)、`--mix` 干湿比 0-1 (默认 1.0)、`--preset` 预设名称

**预设：** `voice` 人声优化 (-20dB, 4:1, 10ms, 130ms)、`music` 音乐轻压缩 (-18dB, 2.5:1, 15ms, 200ms)、`limiter` 硬限制器 (-6dB, 20:1, 1ms, 50ms)、`punch` 打击乐冲击感 (-12dB, 6:1, 3ms, 80ms)、`gentle` 极轻压缩 (-24dB, 1.8:1, 30ms, 300ms)

## Music 命令

MiniMax Music3 本地歌曲与纯音乐生成。详细格式与参数见 [references/music.md](references/music.md)。

创建、改写或扩写 Music3 Caption 时，必须优先使用 MiniMax 官方 `music-caption-rewriter` skill。把用户的音乐 brief、原始段落标签、目标时长和排除项交给该 Skill；将它返回的三段式英文 Caption 作为 `--caption`，原歌词或纯器乐结构标签仍单独传入 Music3。官方 Skill 只负责编曲描述，不替代 OPC 的真实时长和音频完整性验收。

```bash
opc music --caption-file caption.txt --lyrics-file lyrics.txt --duration 120 -o song.mp3
opc music --caption "Cinematic orchestral score" --instrumental --format flac
opc music --caption-file caption.txt --lyrics-file lyrics.txt --dry-run
```

官方 Rewriter 必须返回英文三段式 Structured Caption：`Global Metadata`、`Vocal Details`、`Arrangement`，通常为 250–450 词；歌词单独传入并保留 `[Verse]`、`[Chorus]` 等段落标签。默认 30 steps、CFG 1.7、top-k 50，支持 0.04-360 秒非流式生成。输出默认必须达到目标时长的 95%，不足或音频损坏会自动换 seed 重试三次；`--min-duration` 和 `--attempts` 可调整验收门槛。

## Cut 命令

基于 ASR 字词级时间戳的视频剪辑。**详见 [references/cut.md](references/cut.md)**。

```bash
opc cut --video video.mp4        # 启动剪辑 Web 界面
```

## Stitch 命令（EDL 多轨合成）

`timeline.json` 剪辑决策表 → ffmpeg 一条命令合成：口播/录屏片段（可裁剪）拼接 → 字卡 overlay → ASS 字幕烧录 → BGM 混音。

```bash
opc stitch timeline.json -o out.mp4
```

timeline.json 结构：

```json
{
  "width": 832, "height": 480, "fps": 30,
  "clips": [
    {"src": "host_ch01.mp4"},
    {"src": "screen_S3.mp4", "in": 3, "out": 8}
  ],
  "cards": [
    {"png": "card.png", "start": 2, "end": 5, "layout": "fullscreen"},
    {"png": "card2.png", "start": 16, "end": 19, "width": 0.4}
  ],
  "subtitles": "final.ass",
  "bgm": {"src": "bgm.mp3", "volume": 0.15}
}
```

- clips 的 in/out 为素材内秒数（裁剪），拼接后时间轴从 0 重新计算
- cards 的 start/end 基于**合成后**的时间轴；layout=fullscreen 缩放铺满，否则按 width 比例缩放居中靠底
- subtitles 的 ASS 时间轴也需按合成后时间轴写（各章字幕合并偏移）
- bgm 以口播轨时长为准，volume 建议 0.1-0.2

## Card 命令（知识卡片流水线）

「口播稿 → 字卡渲染 → 按 SRT 时间码合成进视频」的自动化流水线。卡片为 1280×720 深紫金主题（HTML+headless Chrome 渲染），合成用 ffmpeg overlay + 淡入淡出。

```bash
# L3 一条命令全链（ASR + claude LLM 提炼卡片 + 渲染 + 合成）
opc card auto video.mp4 script.txt -o out.mp4

# L2 手动流程
opc card plan script.txt -o cards.json        # LLM 从口播稿生成卡片计划
opc card render cards.json -o png/            # 渲染 PNG
opc card compose video.mp4 subs.srt cards.json --png-dir png/ -o out.mp4
```

cards.json 契约：`cards[]`（id/title 必填，bullets|steps|comparison 三选一，title 支持 `<em>` 强调；`layout` 可选：`"fullscreen"` 整屏排版卡替换画面（官网 section 风格：近黑底+角落光晕+胶囊标签+青紫粉渐变强调字，plan 默认产出），`"card"` 底部小卡叠加（旧行为，默认缺省值））+ `timing[]`（card/keyword/duration，keyword 逐字取自口播稿，滑窗匹配 SRT 时间码，跨行自动处理）。中间产物（srt/cards.json/png）写在 `--workdir`（默认 `<视频目录>/opc_card_auto/`），断点可单独重跑 L2 命令。fullscreen 假定 1280x720 画布。

依赖：ffmpeg、Chrome/Chromium（或 `CHROME_BIN` 环境变量）、`claude` CLI（仅 auto/plan 需要）。

## Script 命令（爆款文稿设计）

「主题 → 口播文稿」与「任意视频 → 文稿结构逆向」两个方向。结构模板是对参考视频（BV1aXQbBcEFk）逐帧+转写逆向提炼的八段式骨架：钩子 → 是什么 → 场景演示×3（痛点故事→演示→前后对比）→ 升华/方法论点题 → 收尾预告。字数按「目标分钟 × 语速」分配（TTS ~4.7 字/秒，真人口播 ~5.5 字/秒）。

```bash
# 生成 10 分钟口播稿(主题自由文本,LLM 按八段模板+字数预算写作)
opc script new "你的视频主题" -m 10 -o script.txt
opc script new "主题" -r reference.txt          # 带参考文稿学风格

# 逆向分析任何文稿/视频(语速、字数、停顿分段、密度峰值)
opc script analyze origin_audio.srt
opc script analyze any_video.mp4               # 音视频自动先跑 ASR

# 查看八段骨架与字数预算
opc script template --minutes 10
```

全链工作流：`opc make` 一键跑完（见下）；或手动串 `opc script new`(文稿）→ `opc tts`(配音）→ `opc make` 数字人段（出镜口播）→ `opc card auto`(字卡合成）→ ffmpeg 烧录 `.ass` 卡拉OK字幕。

文稿硬性要求(生成时强制)：口语化去AI味——禁书面套话(首先/其次/总之等)、平均句长 ≤18 字、第一人称+具体数字，`_validate` 自动检测不达标重写。

依赖：`claude` CLI（仅 new 需要）、ffmpeg + ASR 模型（analyze 传音视频时）。

## Make 命令（一键全链路）

```bash
opc make --topic "视频主题" --minutes 10            # 从主题到烧字幕成片
opc make --script script.txt --workdir demo/v4      # 用已有文稿跑全链
opc make --script s.txt --avatar-image me.png       # 数字人出镜(自备半身照)
opc make --resume-from avatar-video --workdir demo/v4 # 从指定阶段断点续跑
```

阶段链：script → tts → asr → avatar-image → avatar-video → card-plan → card-render → compose → burn。每阶段完成即写 `<workdir>/make_state.json`，中断后重跑自动跳过已完成阶段。

关键语义：
- **数字人出镜**（v4）：`--avatar-image` 半身照经 ffmpeg 规范化 832×480 → Wan2.2 S2V-14B(ComfyUI, 蒸馏LoRA 4步) 按 SRT 句子边界切 ≤15s 段逐段渲染(照片+音频→口播视频,段级断点续跑) → concat + 原始音轨重铺成 base.mp4
- **卡片停留时长 = 该句语音实际时长**（SRT 句末标点推导 span，clamp 3~12s），不再用固定 4s
- 字幕烧录沿用 v2 验证过的底部样式（Alignment 2 / MarginV 60；Style 整行替换,勿拼接）

依赖：ComfyUI 运行中（`~/comfyui/start.sh`）且已下载 Wan2.2 S2V 四件套（diffusion_models/wan2.2_s2v_14B_fp8_scaled、text_encoders/umt5_xxl_fp8、vae/wan_2.1_vae、audio_encoders/wav2vec2、loras/lightx2v_4steps）。

## Broll 命令（配图流水线，v3 遗留，默认链已不用）

```bash
opc broll plan script.txt -o broll.json    # LLM 规划镜头(keyword+画面描述)
opc broll generate broll.json              # ComfyUI 逐张生成 → broll_png/
opc broll bg broll.json voice.srt voice.mp3  # 多图 xfade 拼背景视频(--dry-run 看命令)
```

依赖：ComfyUI 运行中（`~/comfyui/start.sh`，就绪标志 http://127.0.0.1:8188）。

## Video 命令

MiniMax H3 本地文生视频、首尾帧图生视频、参考图视频，以及 SeedVR2 超分。详见 [references/video.md](references/video.md)。

### H3 创意规划路由

- 创建、改写或扩写任何 H3 Prompt 时，必须优先使用 MiniMax 官方 `h3-prompt-writing` skill，并读取与输入模式对应的官方 reference。不要自行改动官方字段名、字段顺序、媒体标签或时间格式。
- 模式映射：`h3-t2v` 使用 T2VA；`h3-i2v` 仅首帧使用 I2VA、首尾帧使用 FL2VA、仅尾帧使用 L2VA；`h3-r2v` 使用 Ref2VA。
- 用户还需要创意策划、参考素材分工、审美设计、测试矩阵或生成后质检时，在官方 Skill 之后读取内置 [H3 Guide](references/h3-guide/SKILL.md)。内置指南补充创意决策，不替换官方 Prompt 结构。
- 用户只查询工作流、参数、安装、连接、缓存和报错，或已经给出符合官方结构的完整 Prompt 要直接执行时，读取 [references/video.md](references/video.md)。
- 冲突优先级：官方 `h3-prompt-writing` 管 Prompt 结构；[references/video.md](references/video.md) 管 CLI 与本机工作流能力；内置 `h3-guide` 管创意规划和质检。
- H3 默认采用两阶段生成：抽卡、试 Prompt 和筛选 seed 时使用 `--turbo`；确定方案后保持 Prompt、参考素材和 seed 不变，移除 `--turbo`，使用 Base 20 steps 按目标分辨率最终出片。不要把 Turbo 预览直接当最终交付。

```bash
opc video list
opc video -w h3-t2v -p "..." --width 864 --height 480 --duration 5
opc video -w h3-t2v -p "..." --width 608 --height 352 --duration 5 --seed 42 --turbo  # 抽卡/筛 Prompt
opc video -w h3-t2v -p "..." --width 1376 --height 768 --duration 5 --seed 42 --steps 20  # 最终出片，不用 Turbo
opc video -w h3-i2v -p "..." --first-frame first.png --last-frame last.png
opc video -w h3-r2v -p "..." --reference-image subject.png
opc video -w h3-t2v-upscale -p "..." --upscale-factor 2
opc video -w h3-t2v -p "..." --no-fbc  # 无近似缓存的精确基线
opc video -w h3-t2v -p "..." --duration 20  # 实验性原生 20 秒（481 帧）
```

CLI 支持 5–20 秒。超过 15 秒属于 ComfyUI 节点允许、但超出 H3 已验证训练区间的实验模式；需要预留更多显存并重点检查长时一致性。

H3 默认启用独立 FirstBlockCache 的 `H3 Safe` 预设。`--no-fbc` 可关闭；
显式启用 `--easy-cache` 时会自动省略 FBC，避免两个近似缓存叠加。

## Dashboard

技能管理面板。**详见 [references/dashboard.md](references/dashboard.md)**。

## 配置

配置文件：`~/.opc_cli/opc/config.json`

| 键 | 默认值 | 说明 |
|---|---|---|
| `tts_engine` | `edge-tts` | 默认 TTS 引擎 |
| `edge_voice` | `zh-CN-XiaoxiaoNeural` | edge-tts 音色 |
| `qwen_speaker` | `Vivian` | qwen 音色 |
| `default_device` | | 播放设备 |
| `asr_model_size` | `1.7B` | ASR 模型 |
| `workspace_dir` | `~/opc-workspace` | 工作目录 |
| `comfyui_host` | `127.0.0.1` | ComfyUI 地址 |
| `comfyui_port` | `8188` | ComfyUI 端口 |
| `video_output_dir` | 空 | 视频下载目录，空时复用 output_dir |
| `image_output_dir` | | 图片输出目录 |
| `vision_api_url` | | 视觉模型 API URL |
| `vision_model` | | 视觉模型名称 |
| `video_desc_api_url` | | 视频理解 API URL；为空时复用 `vision_api_url` |
| `video_desc_model` | | 视频理解模型；为空时复用 `vision_model` |
| `video_desc_max_frames` | `8` | 非原生视频模型的抽帧数量 |
| `dashboard_host` | `0.0.0.0` | Dashboard 监听地址 |
| `dashboard_port` | `12080` | Dashboard 端口 |
| `model_source` | `modelscope` | 模型下载源 |

```bash
opc config --show
opc config --set-engine qwen
opc config --set-comfyui-host 192.168.100.10
```
