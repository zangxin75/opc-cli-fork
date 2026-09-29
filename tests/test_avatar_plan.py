"""avatar 切段测试:句子边界聚合、末段对齐语音全长。"""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from avatar.plan import plan_segments, segment_audio_times
from card.compose import SrtEntry


class PlanSegmentsTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(plan_segments([]), [])

    def test_single_short(self):
        es = [SrtEntry(1, 0.0, 3.0, "你好。")]
        self.assertEqual(plan_segments(es), [(0.0, 3.0)])

    def test_aggregates_across_sentences(self):
        es = [
            SrtEntry(1, 0.0, 5.0, "第一句。"),
            SrtEntry(2, 5.5, 9.0, "第二句。"),
            SrtEntry(3, 9.5, 14.0, "第三句。"),
        ]
        self.assertEqual(plan_segments(es), [(0.0, 14.0)])

    def test_split_at_sentence_boundary(self):
        es = [
            SrtEntry(1, 0.0, 8.0, "a"),
            SrtEntry(2, 8.0, 16.0, "b"),
            SrtEntry(3, 16.0, 20.0, "c"),
        ]
        self.assertEqual(plan_segments(es), [(0.0, 8.0), (8.0, 20.0)])

    def test_long_sentence_own_segment(self):
        es = [SrtEntry(1, 0.0, 20.0, "a")]
        self.assertEqual(plan_segments(es), [(0.0, 20.0)])


class SegmentAudioTimesTests(unittest.TestCase):
    def test_last_segment_extends_to_voice_duration(self):
        segs = [(0.0, 5.0), (5.0, 9.0), (14.0, 18.0)]
        times = segment_audio_times(segs, voice_duration=18.7)
        self.assertEqual(times, [(0.0, 5.0), (5.0, 9.0), (14.0, 18.7)])


if __name__ == "__main__":
    unittest.main()
