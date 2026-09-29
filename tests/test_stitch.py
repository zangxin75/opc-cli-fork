"""stitch 模块单测: timeline.json → ffmpeg 命令构造逻辑。"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from stitch import build_command, load_timeline  # noqa: E402


def _fake_which(*a, **k):
    return "/usr/bin/ffmpeg"


def test_build_command_basic(tmp_path):
    tl = {
        "width": 832, "height": 480,
        "clips": [{"src": "a.mp4"}, {"src": "b.mp4", "in": 2, "out": 6}],
        "cards": [{"png": "c.png", "start": 3, "end": 6, "layout": "fullscreen"}],
        "subtitles": "s.ass",
        "bgm": {"src": "m.mp3", "volume": 0.1},
    }
    with patch("stitch.shutil.which", _fake_which), \
         patch("stitch._ffprobe_duration", lambda v: 10.0):
        cmd = build_command(tl, "out.mp4")
    s = " ".join(cmd)
    assert cmd[0] == "ffmpeg" and "-y" in cmd
    # clip2 有裁剪参数
    i = cmd.index("-ss", cmd.index("a.mp4"))
    assert cmd[i + 1] == "2" and cmd[i + 3] == "4.000"
    # 输入数: 2 clips + 1 card + 1 bgm = 4 个 -i
    assert cmd.count("-i") == 4
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=1" in fc
    assert "scale=832:480," in fc            # fullscreen 卡缩放到画布
    assert "overlay=0:0" in fc               # fullscreen 锚左上
    assert "subtitles=" in fc
    assert "amix=inputs=2" in fc
    assert "out.mp4" == cmd[-1]


def test_build_command_no_cards_no_bgm(tmp_path):
    tl = {"clips": [{"src": "a.mp4", "out": 5}]}
    with patch("stitch.shutil.which", _fake_which), \
         patch("stitch._ffprobe_duration", lambda v: 10.0):
        cmd = build_command(tl, "o.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=1" in fc
    assert "overlay" not in fc and "amix" not in fc and "subtitles" not in fc
    assert "-map" in cmd and "[acat]" in cmd


def test_load_timeline_rejects_empty(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"clips": []}), encoding="utf-8")
    try:
        load_timeline(str(p))
        assert False, "should raise"
    except ValueError:
        pass
