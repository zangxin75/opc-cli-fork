"""B-roll image generation: broll.json shots → PNG files via ComfyUI.

Reuses image/workflow.py (load_workflow + inject_params) and
image/comfyui.py (generate_image). Images come back at 1280x720 to match
the video canvas.
"""

import json
from pathlib import Path

# ops scripts live in scripts/, import as image.* / card.*
from image.comfyui import generate_image
from image.workflow import inject_params, load_workflow

DEFAULT_WORKFLOW = "juggernaut"
DEFAULT_NEGATIVE = "text, watermark, subtitle, letters, blurry, low quality, deformed"
WIDTH, HEIGHT = 1280, 720


def _slug(keyword: str, i: int) -> str:
    keep = "".join(c for c in keyword if not c.isspace())
    return f"{i:02d}_{keep or 'shot'}"


def generate_broll(plan: dict, out_dir, cfg: dict, workflow_alias: str = DEFAULT_WORKFLOW,
                   on_shot=None) -> list:
    """Generate one PNG per shot into out_dir. Returns [ {keyword, png} ]."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    style = plan.get("style", "")

    results = []
    for i, shot in enumerate(plan["shots"]):
        wf, meta = load_workflow(workflow_alias)
        wf = inject_params(wf, meta, {
            "prompt": f"{style}, {shot['prompt']}",
            "negative_prompt": DEFAULT_NEGATIVE,
            "width": WIDTH,
            "height": HEIGHT,
        })
        name = _slug(shot["keyword"], i)
        result = generate_image(wf, cfg, filename_prefix=name,
                                prompt=shot["prompt"], register_gallery=False)
        if not result.get("filepaths"):
            raise RuntimeError(f"no image returned for shot {name}")
        png = Path(result["filepaths"][0])
        target = out_dir / f"{name}.png"
        if png != target:
            png.replace(target)
        results.append({"keyword": shot["keyword"], "png": str(target)})
        if on_shot:
            on_shot(i, shot["keyword"], str(target))
    return results
