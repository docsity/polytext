import unittest
from unittest.mock import MagicMock, patch

from polytext.processor.audio_chunker import AudioChunker


class TestAudioChunker(unittest.TestCase):
    @patch("polytext.processor.audio_chunker.AudioSegment.from_file")
    def test_optimal_chunk_size_is_about_20_minutes_with_5500_max_tokens(self, mock_from_file):
        fake_audio = MagicMock()
        fake_audio.__len__.return_value = 3_600_000
        mock_from_file.return_value = fake_audio

        chunker = AudioChunker(audio_path="/tmp/dummy.mp3", max_llm_tokens=5500)

        self.assertEqual(chunker.calculate_optimal_chunk_size(), 1_200_000)


if __name__ == "__main__":
    unittest.main()
