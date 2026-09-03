import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import APITimeoutError, AuthenticationError

from polytext.llm.multimodal import MultimodalLLM, normalize_provider


class TestMultimodalLLM(unittest.TestCase):
    def test_normalizes_supported_provider_aliases(self):
        self.assertEqual(normalize_provider("google"), "google")
        self.assertEqual(normalize_provider("gemini"), "google")
        self.assertEqual(normalize_provider("OPENAI"), "openai")

    def test_rejects_unknown_provider(self):
        with self.assertRaisesRegex(ValueError, "Unsupported LLM provider"):
            normalize_provider("unknown")

    @patch("polytext.llm.multimodal.genai.Client")
    def test_google_text_generation_preserves_prompt_as_content(self, genai_cls):
        genai_cls.return_value.models.generate_content.return_value = SimpleNamespace(
            text="formatted",
            usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=5),
        )

        result = MultimodalLLM("gemini-3.1-flash-lite", "google").generate_text(
            "Formatting prompt",
            "raw text",
        )

        request = genai_cls.return_value.models.generate_content.call_args.kwargs
        self.assertEqual(request["contents"], ["Formatting prompt", "raw text"])
        self.assertIsNone(request["config"].system_instruction)
        self.assertEqual(result.prompt_tokens, 12)
        self.assertEqual(result.completion_tokens, 5)

    @patch("polytext.llm.multimodal.OpenAI")
    def test_openai_text_generation_normalizes_response(self, openai_cls):
        openai_cls.return_value.responses.create.return_value = SimpleNamespace(
            output_text="clean text",
            usage=SimpleNamespace(input_tokens=17, output_tokens=9),
            status="completed",
            incomplete_details=None,
        )

        result = MultimodalLLM(
            model="gpt-5.6-luna",
            provider="openai",
            api_key="explicit-key",
        ).generate_text(
            instructions="Clean faithfully",
            input_text="raw text",
            max_output_tokens=8000,
        )

        self.assertEqual(result.text, "clean text")
        self.assertEqual(result.prompt_tokens, 17)
        self.assertEqual(result.completion_tokens, 9)
        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.model, "gpt-5.6-luna")
        self.assertEqual(result.finish_reason, "completed")
        openai_cls.assert_called_once_with(api_key="explicit-key")
        openai_cls.return_value.responses.create.assert_called_once_with(
            model="gpt-5.6-luna",
            instructions="Clean faithfully",
            input="raw text",
            max_output_tokens=8000,
            reasoning={"effort": "none"},
        )

    @patch("polytext.llm.multimodal.OpenAI")
    def test_openai_uses_environment_configuration_without_explicit_key(self, openai_cls):
        openai_cls.return_value.responses.create.return_value = SimpleNamespace(
            output_text="text",
            usage=SimpleNamespace(input_tokens=2, output_tokens=1),
            status="completed",
            incomplete_details=None,
        )

        MultimodalLLM("gpt-5.6-luna", "openai").generate_text("Do it", "input")

        openai_cls.assert_called_once_with()

    @patch("polytext.llm.multimodal.OpenAI")
    def test_openai_text_from_image_sends_only_the_image_as_user_content(self, openai_cls):
        openai_cls.return_value.responses.create.return_value = SimpleNamespace(
            output_text="visible words",
            usage=SimpleNamespace(input_tokens=31, output_tokens=4),
            status="completed",
            incomplete_details=None,
        )

        result = MultimodalLLM("gpt-5.6-luna", "openai").generate_text_from_image(
            instructions="Transcribe",
            image_data=b"image-bytes",
            mime_type="image/png",
            max_output_tokens=8192,
        )

        request = openai_cls.return_value.responses.create.call_args.kwargs
        self.assertEqual(request["model"], "gpt-5.6-luna")
        self.assertEqual(request["instructions"], "Transcribe")
        self.assertEqual(len(request["input"][0]["content"]), 1)
        image_part = request["input"][0]["content"][0]
        self.assertEqual(image_part["type"], "input_image")
        self.assertEqual(
            image_part["image_url"],
            "data:image/png;base64,aW1hZ2UtYnl0ZXM=",
        )
        self.assertEqual(result.text, "visible words")

    @patch("polytext.llm.multimodal.OpenAI")
    def test_openai_rejects_empty_output(self, openai_cls):
        openai_cls.return_value.responses.create.return_value = SimpleNamespace(
            output_text=None,
            usage=SimpleNamespace(input_tokens=3, output_tokens=0),
            status="completed",
            incomplete_details=None,
        )

        with self.assertRaisesRegex(Exception, "empty response"):
            MultimodalLLM("gpt-5.6-luna", "openai").generate_text("Do it", "input")

    @patch("polytext.llm.multimodal.OpenAI")
    def test_openai_rejects_incomplete_output(self, openai_cls):
        openai_cls.return_value.responses.create.return_value = SimpleNamespace(
            output_text="partial",
            usage=SimpleNamespace(input_tokens=3, output_tokens=1),
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        )

        with self.assertRaisesRegex(Exception, "incomplete response.*max_output_tokens"):
            MultimodalLLM("gpt-5.6-luna", "openai").generate_text("Do it", "input")

    @patch("polytext.llm.multimodal.OpenAI")
    def test_openai_retries_a_transient_timeout(self, openai_cls):
        completed = SimpleNamespace(
            output_text="recovered",
            usage=SimpleNamespace(input_tokens=3, output_tokens=1),
            status="completed",
            incomplete_details=None,
        )
        openai_cls.return_value.responses.create.side_effect = [
            APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses")),
            completed,
        ]

        result = MultimodalLLM("gpt-5.6-luna", "openai").generate_text("Do it", "input")

        self.assertEqual(result.text, "recovered")
        self.assertEqual(openai_cls.return_value.responses.create.call_count, 2)

    @patch("polytext.llm.multimodal.OpenAI")
    def test_openai_does_not_retry_authentication_failure(self, openai_cls):
        response = httpx.Response(
            401,
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        )
        openai_cls.return_value.responses.create.side_effect = AuthenticationError(
            "invalid key",
            response=response,
            body=None,
        )

        with self.assertRaises(AuthenticationError):
            MultimodalLLM("gpt-5.6-luna", "openai").generate_text("Do it", "input")

        self.assertEqual(openai_cls.return_value.responses.create.call_count, 1)


if __name__ == "__main__":
    unittest.main()
