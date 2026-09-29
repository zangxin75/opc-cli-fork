"""script/generate.py 的 AI 味检测与 prompt 硬性要求测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from script.generate import (
    PROMPT_TEMPLATE, _validate, avg_sentence_length, count_formal_markers,
    count_soft_markers,
)


class TestFormalMarkers:
    def test_clean_text_zero(self):
        assert count_formal_markers("说白了,这玩意儿很好用,你试试看。") == 0

    def test_each_marker_counted(self):
        text = "首先这样。其次那样。综上所述不错。"
        assert count_formal_markers(text) == 3

    def test_spoken_connectors_are_soft_not_formal(self):
        # 然后/最后 属于口语自然连接词,不计入硬禁的书面套话
        assert count_formal_markers("然后我试了一下。最后成了。") == 0
        assert count_soft_markers("然后我试了一下。最后成了。然后又跑一遍。") == 3


class TestAvgSentenceLength:
    def test_split_on_punctuation(self):
        assert avg_sentence_length("你好。再见。") == 2.0

    def test_empty(self):
        assert avg_sentence_length("") == 0.0

    def test_long_sentence(self):
        assert avg_sentence_length("今天我们来聊一个非常非常非常非常长的句子没有任何停顿") > 22


class TestValidateAIFlavor:
    def _base(self, text):
        return _validate(text, words=len(text))

    def test_clean_colloquial_passes(self):
        text = "我试了一下。真的很离谱。你看这个数,三十多秒出图。对吧?"
        assert self._base(text) is None

    def test_formal_markers_rejected(self):
        text = "首先这样做。其次那样做。综上所述完成。就这样结束了。"
        assert "书面套话" in self._base(text)

    def test_too_many_soft_connectors_rejected(self):
        text = "然后跑一遍。然后再跑。然后再来。然后又试。然后再改。最后好了。"
        assert "机械" in self._base(text)

    def test_long_sentences_rejected(self):
        text = "今天我们来聊一个在没有联网的情况下也能用一条命令把视频从配音到字幕全部搞定的方法。"
        assert "句长" in self._base(text)

    def test_word_count_still_checked(self):
        assert "字数" in _validate("太短了。", words=500)


class TestPromptRequirements:
    def test_prompt_contains_deai_rules(self):
        # 需求1:去AI味硬性要求固化在 prompt 里
        for phrase in ("首先/其次", "排比", "平均句长", "第一人称"):
            assert phrase in PROMPT_TEMPLATE, f"prompt 缺少: {phrase}"
