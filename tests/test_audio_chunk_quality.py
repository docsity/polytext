import tempfile
import unittest
from unittest.mock import MagicMock, patch

from polytext.converter import audio_to_text
from polytext.loader import BaseLoader


class AudioChunkQualityTests(unittest.TestCase):
    def test_counts_empty_and_low_text_chunks_separately(self):
        chunks = [
            {"duration_ms": 120_000},
            {"duration_ms": 120_000},
            {"duration_ms": 120_000},
            {"duration_ms": 20_000},
            {"duration_ms": 1_200_000},
        ]
        transcripts = ["parola " * 40, "  \n", "parola " * 12, "ciao", "parola " * 100]

        quality = audio_to_text.summarize_audio_chunk_quality(chunks, transcripts)

        self.assertEqual(quality, {
            "total_chunks": 5,
            "empty_chunks": 1,
            "low_text_chunks": 2,
            "empty_chunk_indices": [2],
            "low_text_chunk_indices": [3, 5],
            "low_text_threshold_words_per_minute": 20,
            "low_text_min_duration_ms": 60_000,
        })

    @patch("polytext.converter.audio_to_text.TextMerger")
    @patch("polytext.converter.audio_to_text.AudioChunker")
    @patch.object(audio_to_text.AudioToTextConverter, "process_chunk")
    def test_quality_is_returned_without_saving_chunk_transcripts(
        self, mock_process_chunk, mock_chunker_cls, mock_merger_cls
    ):
        chunker = mock_chunker_cls.return_value
        chunker.duration_ms = 240_000
        chunker.extract_chunks.return_value = [
            {"file_path": "/tmp/chunk1.mp3", "duration_ms": 120_000},
            {"file_path": "/tmp/chunk2.mp3", "duration_ms": 120_000},
        ]
        mock_process_chunk.side_effect = lambda chunk, index: (
            index,
            {"transcript": "parola " * 40 if index == 0 else "", "completion_tokens": 4, "prompt_tokens": 5},
        )
        mock_merger_cls.return_value.merge_chunks_with_llm_sequential.return_value = {
            "full_text_merged": "testo finale", "completion_tokens": 0, "prompt_tokens": 0
        }

        with tempfile.NamedTemporaryFile(suffix=".mp3") as source_audio:
            converter = audio_to_text.AudioToTextConverter()
            result = converter.transcribe_full_audio(source_audio.name)

        self.assertEqual(result["text"], "testo finale")
        self.assertEqual(result["audio_chunk_quality"]["total_chunks"], 2)
        self.assertEqual(result["audio_chunk_quality"]["empty_chunks"], 1)
        self.assertNotIn("text_chunks", result)

    def test_quality_reaches_top_level_loader_response(self):
        quality = {"total_chunks": 2, "empty_chunks": 1, "low_text_chunks": 0}
        file_loader = MagicMock()
        file_loader.load.return_value = {
            "text": "trascrizione", "completion_tokens": 3, "prompt_tokens": 4,
            "audio_chunk_quality": quality,
        }

        response = BaseLoader().run_loader_class(file_loader, ["audio.mp3"])

        self.assertEqual(response["audio_chunk_quality"], quality)
        self.assertEqual(response["output_list"][0]["audio_chunk_quality"], quality)


if __name__ == "__main__":
    unittest.main()
