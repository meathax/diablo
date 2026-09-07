"""Capture comparisons must not accept missing or incomplete reference evidence."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('compare_frames', Path(__file__).parents[1] / 'scripts/compare_frames.py')
frames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames)


class FrameComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.left, self.right = (Path(self.temp.name) / name for name in ('a', 'b'))
        self.left.mkdir()
        self.right.mkdir()
        self.raw = struct.pack('<8sIIQQ', b'D8RGB001', 640, 480, 128, 6400) + bytes(768 + 640 * 480)

    def seed(self):
        for directory in (self.left, self.right):
            (directory / 'frame-128.d8f').write_bytes(self.raw)

    def test_empty_series_are_not_equality_evidence(self):
        self.assertFalse(frames.compare_series(self.left, self.right)['equal'])

    def test_equal_complete_series(self):
        self.seed()
        self.assertEqual(frames.compare_series(self.left, self.right)['frames_compared'], 1)

    def test_missing_frame_is_rejected(self):
        self.seed()
        (self.left / 'frame-256.d8f').write_bytes(self.raw)
        self.assertEqual(frames.compare_series(self.left, self.right)['difference'], 'frame set')

    def test_partial_capture_is_rejected(self):
        self.seed()
        (self.right / 'frame-256.d8f.partial').touch()
        self.assertFalse(frames.compare_series(self.left, self.right)['equal'])

    def test_unused_palette_entry_is_compared(self):
        self.seed()
        altered = bytearray(self.raw)
        altered[32 + 767] = 1
        (self.right / 'frame-128.d8f').write_bytes(altered)
        result = frames.compare_series(self.left, self.right)
        self.assertEqual((result['difference'], result['entry'], result['channel']), ('palette', 255, 'B'))

    def test_wrong_time_and_truncation_are_rejected(self):
        self.seed()
        altered = bytearray(self.raw)
        altered[24] ^= 1
        target = self.right / 'frame-128.d8f'
        target.write_bytes(altered)
        self.assertEqual(frames.compare_series(self.left, self.right)['difference'], 'logic_ms')
        target.write_bytes(altered[:-1])
        with self.assertRaises(ValueError):
            frames.compare_series(self.left, self.right)
