"""Wan2.2 S2V 数字人渲染:API 工作流构造 + ComfyUI 提交/下载。"""

import math
import time
from pathlib import Path

CHUNK = 77   # 每窗口帧数(官方模板默认,4.8s @ 16fps)
FPS = 16     # S2V 输出帧率

UNET = "wan2.2_s2v_14B_fp8_scaled.safetensors"
CLIP = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
VAE = "wan_2.1_vae.safetensors"
AENC = "wav2vec2_large_english_fp16.safetensors"
LORA = "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors"

NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，"
       "整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，"
       "画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，"
       "静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")


def chunks_for(length: int) -> int:
    """帧数 → 窗口数(每窗口 CHUNK 帧)。"""
    return max(1, math.ceil(length / CHUNK))


def frame_count(seconds: float) -> int:
    """秒 → 帧数(16fps,4 的倍数,至少 CHUNK=77 ≈ 4.8s)。"""
    return max(CHUNK, math.ceil(seconds * FPS / 4) * 4)


def build_s2v_workflow(*, ref_image: str, audio: str, length: int,
                       width: int = 832, height: int = 480,
                       steps: int = 4, cfg: float = 1.0, shift: float = 8.0,
                       seed: int = 42, lora: str | None = LORA,
                       fps: int = FPS, prefix: str = "avatar/seg",
                       prev_latent: str | None = None,
                       last_window: bool = False,
                       ) -> dict:
    """构造 S2V 单窗口 API 工作流(77 帧/窗口)。

    多窗口采用逐 prompt 提交(官方模板模式):每窗口一个 graph,
    窗口间用 SaveLAT/LoadLAT 落盘衔接,避免单 graph 串联多窗口
    导致所有中间 latent 常驻 GPU 而 OOM(8G 卡实测)。

    - prev_latent=None → 首窗口(WanSoundImageToVideo)
    - prev_latent=<文件名> → Extend 窗口,从累计 latent 推 frame_offset
    - last_window=True → 末窗口追加 VAEDecode+SaveVideo 出片
    - 中间窗口落盘 SaveLatent,供下一窗口 LoadLatent
    """
    if lora:
        steps, cfg = 4, 1.0

    wf = {}
    counter = [0]

    def add(cls, **inputs):
        counter[0] += 1
        nid = str(counter[0])
        wf[nid] = {"class_type": cls, "inputs": inputs}
        return nid

    def R(nid, slot=0):
        return [nid, slot]

    unet = add("UNETLoader", unet_name=UNET, weight_dtype="default")
    model = R(unet)
    if lora:
        lora_n = add("LoraLoaderModelOnly", model=R(unet), lora_name=lora,
                     strength_model=1.0)
        model = R(lora_n)
    ms = add("ModelSamplingSD3", model=model, shift=shift)

    clip = add("CLIPLoader", clip_name=CLIP, type="wan", device="default")
    pos = add("CLIPTextEncode", clip=R(clip), text="")
    neg = add("CLIPTextEncode", clip=R(clip), text=NEG)
    vae = add("VAELoader", vae_name=VAE)
    aenc = add("AudioEncoderLoader", audio_encoder_name=AENC)
    audio_node = add("LoadAudio", audio=audio)
    feats = add("AudioEncoderEncode", audio_encoder=R(aenc),
                audio=R(audio_node))
    ref = add("LoadImage", image=ref_image)

    if prev_latent is None:
        src = add("WanSoundImageToVideo", positive=R(pos), negative=R(neg),
                  vae=R(vae), width=width, height=height, length=length,
                  batch_size=1, audio_encoder_output=R(feats),
                  ref_image=R(ref))
    else:
        load = add("LoadLatent", latent=prev_latent)
        src = add("WanSoundImageToVideoExtend", positive=R(pos),
                  negative=R(neg), vae=R(vae), length=length,
                  video_latent=R(load),
                  audio_encoder_output=R(feats), ref_image=R(ref))
    ks = add("KSampler", seed=seed, steps=steps, cfg=cfg,
             sampler_name="uni_pc", scheduler="simple", denoise=1.0,
             model=R(ms), positive=R(src, 0), negative=R(src, 1),
             latent_image=R(src, 2))
    if prev_latent is None:
        acc = ks
    else:
        # Extend 窗口:ks 只产新窗口 latent,必须与累计 latent 拼接;
        # 否则下一窗口 frame_offset(按传入 latent 长度推算)会漂移
        acc = add("LatentConcat", samples1=R(load), samples2=R(ks), dim="t")
    if last_window:
        decode = add("VAEDecode", samples=R(acc), vae=R(vae))
        video = add("CreateVideo", images=R(decode), fps=fps,
                    audio=R(audio_node))
        add("SaveVideo", video=R(video), filename_prefix=prefix, format="auto")
    else:
        # SaveLatent 落盘到 output/,文件名带自动 counter;render_segment
        # 负责搬运到 input/ 供下一窗口 LoadLatent 读取
        add("SaveLatent", samples=R(acc),
            filename_prefix=f"opc_s2v_latent_{seed:05d}")
    return wf


def render_segment(ref_png: str, mp3: str, length: int, out_dir: str,
                   width: int = 832, height: int = 480, seed: int = 42,
                   prefix: str = "avatar/seg", server_url: str | None = None,
                   start_window: int = 0):
    """渲染单段:上传/就位文件 → 提交工作流 → 等待 → 返回 mp4 路径。

    ref_png/mp3 会被复制进 ComfyUI input 目录(本机部署,免 HTTP 上传)。
    start_window>0 为窗口级断点续跑:要求 input/ 已就位 start_window-1
    窗口的累计 latent(input/opc_s2v_latent_<seed>.latent)。
    """
    import shutil

    from image.comfyui import (
        get_server_url, queue_prompt, wait_for_completion,
    )
    from shared.config import load_config

    cfg_obj = load_config()
    server_url = server_url or get_server_url(cfg_obj)
    import urllib.request
    try:
        with urllib.request.urlopen(f"{server_url}/system_stats",
                                    timeout=5) as resp:
            resp.read()
    except Exception:
        raise SystemExit("Error: ComfyUI 未运行,先启动 ~/comfyui/start.sh")

    input_dir = Path("~/comfyui/input").expanduser()
    input_dir.mkdir(parents=True, exist_ok=True)
    ref_name = f"opc_ref_{Path(ref_png).name}"
    aud_name = f"opc_seg_{Path(mp3).name}"
    shutil.copy(ref_png, input_dir / ref_name)
    shutil.copy(mp3, input_dir / aud_name)

    # 逐窗口提交(每窗口一个 prompt,窗口间 SaveLatent→LoadLatent 衔接):
    # 首窗口 WanSoundImageToVideo,其余 Extend;仅末窗口 VAEDecode 出片。
    # SaveLatent 产出 output/opc_s2v_latent_<seed>_NNNNN_.latent(带 counter),
    # 每窗口完成后 Python 侧搬运到 input/ 固定名供下一窗口读取。
    n_win = chunks_for(length)
    latent_in = f"opc_s2v_latent_{seed:05d}.latent"
    # 断点自动检测:input/ 已有本段累计 latent 时按大小推算已完成窗口数,
    # 避免段级重试时把已渲染的窗口再烧一遍(每窗口 ~10 分钟)
    latent_path = input_dir / latent_in
    if start_window == 0 and latent_path.exists():
        per_win = 7989088  # 实测 77 帧 ≈ 7989088B(20 latent_t)
        done_w = round(latent_path.stat().st_size / per_win)
        if 0 < done_w < n_win:
            start_window = done_w
            print(f"[s2v] 检测残留 latent {latent_path.stat().st_size}B "
                  f"≈ {done_w} 窗口,从窗口 {done_w + 1} 续跑", flush=True)
    # 末窗口只采剩余帧(4 的倍数,≥4),避免整窗 77 帧导致每段多 ~4.8s 尾巴
    rem = max(4, math.ceil((length - (n_win - 1) * CHUNK) / 4) * 4) if n_win > 1 else length
    for w in range(start_window, n_win):
        wl = rem if w == n_win - 1 else min(length, CHUNK)
        wf = build_s2v_workflow(
            ref_image=ref_name, audio=aud_name,
            length=wl,
            width=width, height=height, seed=seed + w,
            prefix=prefix, last_window=(w == n_win - 1),
            prev_latent=None if w == 0 else latent_in)
        prompt_id = queue_prompt(wf, server_url)
        wait_for_completion(prompt_id, server_url)
        print(f"[s2v] 窗口 {w + 1}/{n_win} complete", flush=True)
        if w < n_win - 1:
            # 窗口 w 用 seed+w 采样,SaveLatent 前缀含 seed+w → 按当窗
            # seed glob 最新 latent → input/ 固定名供下一窗口读取
            out_root = Path("~/comfyui/output").expanduser()
            newest = sorted(
                out_root.glob(f"opc_s2v_latent_{seed + w:05d}_*.latent"),
                key=lambda p: p.stat().st_mtime)[-1]
            shutil.move(str(newest), str(input_dir / latent_in))
    # ComfyUI SaveVideo filename_prefix="<sub>/<name>" → 产出 <out_root>/<sub>/<name>_00001_.mp4
    # 拆分 prefix:子目录 + 文件名 glob
    out_root = Path("~/comfyui/output").expanduser()
    if "/" in prefix:
        subdir, name = prefix.split("/", 1)
    else:
        subdir, name = "", prefix
    search = out_root / subdir if subdir else out_root
    vids = sorted(search.glob(f"{name}*.mp4"), key=lambda p: p.stat().st_mtime)
    if not vids:
        raise RuntimeError(f"S2V 渲染无输出: {search}/{name}*.mp4")
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"seg_{int(time.time())}.mp4"
    shutil.copy(vids[-1], target)
    return target
