import unittest
from types import SimpleNamespace
from unittest.mock import patch

from polytext.processor.text_merger import TextMerger


class _FakeModels:
    def __init__(self):
        self.config = None

    def generate_content(self, model, contents, config):
        self.config = config
        return SimpleNamespace(
            text=None,
            candidates=[
                SimpleNamespace(
                    finish_reason="STOP",
                    safety_ratings=[SimpleNamespace(category="SAFE")],
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(text=None, thought=True)]
                    ),
                )
            ],
            prompt_feedback=SimpleNamespace(block_reason=None),
            usage_metadata=SimpleNamespace(
                candidates_token_count=None,
                prompt_token_count=251,
            ),
        )


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()


class TestTextMergerDiagnostics(unittest.TestCase):
    @patch("polytext.processor.text_merger.logger.warning")
    @patch("polytext.processor.text_merger.genai.Client", return_value=_FakeClient())
    def test_logs_structured_diagnostics_when_merge_response_has_no_text(
        self,
        _mock_client,
        mock_warning,
    ):
        merger = TextMerger()
        result = merger.merge_texts_with_llm(
            "Prima frase completa. Seconda frase completa.",
            "Seconda frase completa. Terza frase completa.",
        )

        mock_warning.assert_called_once()
        diagnostics = mock_warning.call_args.args[1]
        self.assertEqual(diagnostics["model"], "gemini-3.1-flash-lite")
        self.assertEqual(diagnostics["candidate_count"], 1)
        self.assertEqual(diagnostics["candidates"][0]["finish_reason"], "STOP")
        self.assertEqual(diagnostics["candidates"][0]["parts"][0]["thought"], True)
        self.assertFalse(diagnostics["candidates"][0]["parts"][0]["has_text"])
        self.assertEqual(diagnostics["usage_metadata"]["prompt_token_count"], 251)
        self.assertEqual(
            diagnostics["merge_inputs"],
            {
                "segment_1": {"char_count": 45, "word_count": 6, "is_empty": False},
                "segment_2": {"char_count": 45, "word_count": 6, "is_empty": False},
            },
        )
        self.assertEqual(
            diagnostics["source_transcripts"],
            {
                "transcript_1_char_count": 45,
                "transcript_1_tail": "Prima frase completa. Seconda frase completa.",
                "transcript_2_char_count": 45,
                "transcript_2_head": "Seconda frase completa. Terza frase completa.",
            },
        )
        self.assertEqual(
            result["merged_text"],
            merger.merge_texts(
                "Prima frase completa. Seconda frase completa.",
                "Seconda frase completa. Terza frase completa.",
            ),
        )
        config = _mock_client.return_value.models.config
        self.assertEqual(config.tools, [])
        self.assertTrue(config.automatic_function_calling.disable)


if __name__ == "__main__":
    unittest.main()
