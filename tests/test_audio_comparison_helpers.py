import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, call

from tests.test_compare_audio_models import (
    compute_length_metrics,
    extract_eval_snippet,
    build_length_comparison,
    transcribe_with_model,
    parse_gcs_uri,
    resolve_input_to_audio,
    cleanup_temp_paths,
    save_raw_chunk_transcriptions,
)


class TestAudioComparisonHelpers(unittest.TestCase):
    def test_parse_gcs_uri(self):
        bucket, file_path = parse_gcs_uri("gcs://my-bucket/videos/sample.mp4")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(file_path, "videos/sample.mp4")

    def test_parse_gcs_uri_rejects_non_gcs(self):
        with self.assertRaises(ValueError):
            parse_gcs_uri("/tmp/local.mp4")

        with self.assertRaises(ValueError):
            parse_gcs_uri("gcs://bucket-only")

    def test_compute_length_metrics(self):
        text = "## Title\nHello world.\n### Subtitle\nAnother line."
        metrics = compute_length_metrics(text)

        self.assertEqual(metrics["char_count"], len(text))
        self.assertEqual(metrics["word_count"], 6)
        self.assertEqual(metrics["line_count"], 4)
        self.assertEqual(metrics["heading_count"], 2)
        self.assertEqual(metrics["repeated_long_sentence_groups"], 0)
        self.assertEqual(metrics["repeated_long_sentence_occurrences"], 0)
        self.assertEqual(metrics["max_long_sentence_repetitions"], 0)

    def test_compute_length_metrics_detects_repeated_long_sentences(self):
        long_a = (
            "Questa e una frase molto lunga costruita per verificare il rilevamento delle ripetizioni "
            "nei confronti tra trascrizioni e supera ampiamente la soglia minima di caratteri richiesta."
        )
        long_b = (
            "Anche questa seconda frase e volutamente lunga e serve a simulare un blocco ripetuto che "
            "potrebbe indicare una allucinazione o un loop nel testo prodotto dal modello."
        )
        text = " ".join([long_a, long_a, long_a, long_a, long_b, long_b, long_b])
        metrics = compute_length_metrics(text)

        self.assertEqual(metrics["repeated_long_sentence_groups"], 2)
        self.assertEqual(metrics["repeated_long_sentence_occurrences"], 7)
        self.assertEqual(metrics["max_long_sentence_repetitions"], 4)

    def test_extract_eval_snippet_marks_truncation(self):
        text = "abcdefghij"
        snippet, was_truncated = extract_eval_snippet(text, max_chars=4)

        self.assertEqual(snippet, "abcd")
        self.assertTrue(was_truncated)

    def test_extract_eval_snippet_without_truncation(self):
        text = "abc"
        snippet, was_truncated = extract_eval_snippet(text, max_chars=10)

        self.assertEqual(snippet, "abc")
        self.assertFalse(was_truncated)

    def test_build_length_comparison(self):
        model_a = {
            "char_count": 100,
            "word_count": 20,
            "line_count": 4,
            "heading_count": 1,
            "repeated_long_sentence_groups": 0,
            "repeated_long_sentence_occurrences": 0,
            "max_long_sentence_repetitions": 1,
            "generation_time_seconds": 10.0,
        }
        model_b = {
            "char_count": 80,
            "word_count": 16,
            "line_count": 5,
            "heading_count": 1,
            "repeated_long_sentence_groups": 3,
            "repeated_long_sentence_occurrences": 15,
            "max_long_sentence_repetitions": 6,
            "generation_time_seconds": 15.0,
        }
        comparison = build_length_comparison(model_a, model_b)

        self.assertEqual(comparison["char_count"]["delta_model_b_minus_model_a"], -20)
        self.assertEqual(comparison["word_count"]["delta_model_b_minus_model_a"], -4)
        self.assertEqual(comparison["line_count"]["delta_model_b_minus_model_a"], 1)
        self.assertEqual(comparison["heading_count"]["delta_model_b_minus_model_a"], 0)
        self.assertEqual(comparison["repeated_long_sentence_groups"]["delta_model_b_minus_model_a"], 3)
        self.assertEqual(comparison["repeated_long_sentence_occurrences"]["delta_model_b_minus_model_a"], 15)
        self.assertEqual(comparison["max_long_sentence_repetitions"]["delta_model_b_minus_model_a"], 5)
        self.assertEqual(comparison["generation_time_seconds"]["delta_model_b_minus_model_a"], 5.0)

    @patch("tests.test_compare_audio_models.AudioToTextConverter")
    def test_transcribe_with_model_enables_save_transcript_chunks_by_default(self, mock_converter_cls):
        mock_converter = mock_converter_cls.return_value
        mock_converter.transcribe_full_audio.return_value = {"text": "ok"}

        transcribe_with_model(
            audio_file="/tmp/dummy.mp3",
            transcription_model="gemini-2.0-flash",
            llm_api_key=None,
            timeout_minutes=None,
            markdown_output=True,
        )

        mock_converter_cls.assert_called_once_with(
            transcription_model="gemini-2.0-flash",
            markdown_output=True,
            llm_api_key=None,
            timeout_minutes=None,
        )
        mock_converter.transcribe_full_audio.assert_called_once_with(
            audio_path="/tmp/dummy.mp3",
            save_transcript_chunks=True,
        )

    @patch("tests.test_compare_audio_models.AudioToTextConverter")
    def test_transcribe_with_model_supports_plain_text_output(self, mock_converter_cls):
        mock_converter = mock_converter_cls.return_value
        mock_converter.transcribe_full_audio.return_value = {"text": "ok"}

        transcribe_with_model(
            audio_file="/tmp/dummy.mp3",
            transcription_model="gemini-3.1-flash-lite-preview",
            llm_api_key="k",
            timeout_minutes=2,
            markdown_output=False,
        )

        mock_converter_cls.assert_called_once_with(
            transcription_model="gemini-3.1-flash-lite-preview",
            markdown_output=False,
            llm_api_key="k",
            timeout_minutes=2,
        )

    def test_resolve_input_to_audio_local_audio(self):
        result = resolve_input_to_audio("/tmp/sample_audio.mp3")

        self.assertEqual(result["input_type"], "local_audio")
        self.assertEqual(result["audio_path"], "/tmp/sample_audio.mp3")
        self.assertEqual(result["cleanup_paths"], [])

    @patch("tests.test_compare_audio_models.os.close")
    @patch("tests.test_compare_audio_models.tempfile.mkstemp", return_value=(123, "/tmp/downloaded_video.mp4"))
    @patch("tests.test_compare_audio_models.convert_video_to_audio", return_value="/tmp/converted_audio.mp3")
    @patch("tests.test_compare_audio_models.Downloader")
    @patch("tests.test_compare_audio_models.storage.Client")
    def test_resolve_input_to_audio_gcs_video(
        self,
        mock_storage_client_cls,
        mock_downloader_cls,
        mock_convert_video_to_audio,
        mock_mkstemp,
        mock_close,
    ):
        mock_storage_client = mock_storage_client_cls.return_value
        mock_downloader = mock_downloader_cls.return_value

        result = resolve_input_to_audio("gcs://my-bucket/path/to/video.mp4", bitrate_quality=7)

        self.assertEqual(result["input_type"], "gcs_video")
        self.assertEqual(result["audio_path"], "/tmp/converted_audio.mp3")
        self.assertEqual(result["cleanup_paths"], ["/tmp/downloaded_video.mp4", "/tmp/converted_audio.mp3"])
        self.assertEqual(result["input_path"], "gcs://my-bucket/path/to/video.mp4")

        mock_downloader_cls.assert_called_once_with(
            gcs_client=mock_storage_client,
            document_gcs_bucket="my-bucket",
        )
        mock_downloader.download_file_from_gcs.assert_called_once_with(
            file_path="path/to/video.mp4",
            temp_file_path="/tmp/downloaded_video.mp4",
        )
        mock_convert_video_to_audio.assert_called_once_with(
            video_file="/tmp/downloaded_video.mp4",
            bitrate_quality=7,
        )

    @patch("tests.test_compare_audio_models.os.remove")
    @patch("tests.test_compare_audio_models.os.path.exists", side_effect=[True, False, True])
    def test_cleanup_temp_paths(self, mock_exists, mock_remove):
        cleanup_temp_paths(["/tmp/a.mp4", "/tmp/b.mp3", "/tmp/c.tmp"])

        mock_exists.assert_has_calls([call("/tmp/a.mp4"), call("/tmp/b.mp3"), call("/tmp/c.tmp")])
        mock_remove.assert_has_calls([call("/tmp/a.mp4"), call("/tmp/c.tmp")])

    def test_save_raw_chunk_transcriptions_writes_files_and_returns_paths(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir)
            paths = save_raw_chunk_transcriptions(
                run_dir=run_dir,
                input_path="gcs://bucket/path/to/video.mp4",
                model_name="gemini-3.1-flash-lite-preview",
                text_chunks=["chunk one", "chunk two"],
                markdown_output=False,
            )

            self.assertEqual(len(paths), 2)
            first = Path(paths[0])
            second = Path(paths[1])
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertEqual(first.suffix, ".txt")
            self.assertEqual(second.suffix, ".txt")
            self.assertEqual(first.read_text(encoding="utf-8"), "chunk one")
            self.assertEqual(second.read_text(encoding="utf-8"), "chunk two")


if __name__ == "__main__":
    unittest.main()
