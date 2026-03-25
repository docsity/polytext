import unittest
import os
from unittest.mock import MagicMock, patch

from polytext.processor.audio_chunker import AudioChunker


class TestAudioChunker(unittest.TestCase):
    @patch("polytext.processor.audio_chunker.AudioSegment.from_file")
    def test_optimal_chunk_size_is_about_15_minutes_with_4250_max_tokens(self, mock_from_file):
        fake_audio = MagicMock()
        fake_audio.__len__.return_value = 3_600_000
        mock_from_file.return_value = fake_audio

        chunker = AudioChunker(audio_path="/tmp/dummy.mp3", max_llm_tokens=4250)

        self.assertEqual(chunker.calculate_optimal_chunk_size(), 900_000)

    @patch("polytext.processor.audio_chunker.ffmpeg.run")
    @patch("polytext.processor.audio_chunker.ffmpeg.input")
    @patch("polytext.processor.audio_chunker.AudioSegment.from_file")
    def test_process_single_chunk_uses_unique_temp_file_across_instances(
        self,
        mock_from_file,
        mock_ffmpeg_input,
        _mock_ffmpeg_run,
    ):
        fake_audio = MagicMock()
        fake_audio.__len__.return_value = 10_000
        mock_from_file.return_value = fake_audio

        fake_stream = MagicMock()
        mock_ffmpeg_input.return_value.output.return_value.overwrite_output.return_value = fake_stream

        chunker_a = AudioChunker(audio_path="/tmp/dummy.mp3")
        chunker_b = AudioChunker(audio_path="/tmp/dummy.mp3")

        chunk_a = chunker_a._process_single_chunk((0, (0, 1_000)))
        chunk_b = chunker_b._process_single_chunk((0, (0, 1_000)))

        try:
            self.assertNotEqual(chunk_a["file_path"], chunk_b["file_path"])
        finally:
            for file_path in (chunk_a["file_path"], chunk_b["file_path"]):
                if os.path.exists(file_path):
                    os.remove(file_path)


if __name__ == "__main__":
    unittest.main()
