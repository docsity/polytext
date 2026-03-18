import unittest
from unittest.mock import patch

from tests.test_compare_audio_models import (
    compute_length_metrics,
    extract_eval_snippet,
    build_length_comparison,
    transcribe_with_model,
)


class TestAudioComparisonHelpers(unittest.TestCase):
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
        }
        model_b = {
            "char_count": 80,
            "word_count": 16,
            "line_count": 5,
            "heading_count": 1,
            "repeated_long_sentence_groups": 3,
            "repeated_long_sentence_occurrences": 15,
            "max_long_sentence_repetitions": 6,
        }
        comparison = build_length_comparison(model_a, model_b)

        self.assertEqual(comparison["char_count"]["delta_model_b_minus_model_a"], -20)
        self.assertEqual(comparison["word_count"]["delta_model_b_minus_model_a"], -4)
        self.assertEqual(comparison["line_count"]["delta_model_b_minus_model_a"], 1)
        self.assertEqual(comparison["heading_count"]["delta_model_b_minus_model_a"], 0)
        self.assertEqual(comparison["repeated_long_sentence_groups"]["delta_model_b_minus_model_a"], 3)
        self.assertEqual(comparison["repeated_long_sentence_occurrences"]["delta_model_b_minus_model_a"], 15)
        self.assertEqual(comparison["max_long_sentence_repetitions"]["delta_model_b_minus_model_a"], 5)

    @patch("tests.test_compare_audio_models.AudioToTextConverter")
    def test_transcribe_with_model_enables_save_transcript_chunks_by_default(self, mock_converter_cls):
        mock_converter = mock_converter_cls.return_value
        mock_converter.transcribe_full_audio.return_value = {"text": "ok"}

        transcribe_with_model(
            audio_file="/tmp/dummy.mp3",
            transcription_model="gemini-2.0-flash",
            llm_api_key=None,
            timeout_minutes=None,
        )

        mock_converter.transcribe_full_audio.assert_called_once_with(
            audio_path="/tmp/dummy.mp3",
            save_transcript_chunks=True,
        )


if __name__ == "__main__":
    unittest.main()
