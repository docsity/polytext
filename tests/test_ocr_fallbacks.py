import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from polytext.converter.document_ocr_to_text import DocumentOCRToTextConverter
from polytext.converter.document_ocr_to_text_azure_oai import (
    DocumentOCRToTextConverter as AzureDocumentOCRToTextConverter,
)
from polytext.converter.ocr_to_text import OCRToTextConverter
from polytext.exceptions import EmptyDocument


def _make_response(
    text="ocr text",
    finish_reason=None,
    completion_tokens=11,
    prompt_tokens=7,
):
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=finish_reason)],
        usage_metadata=SimpleNamespace(
            candidates_token_count=completion_tokens,
            prompt_token_count=prompt_tokens,
        ),
    )


class _FakeFiles:
    def upload(self, file):
        return SimpleNamespace(name="uploaded-image")

    def delete(self, name):
        return None


class _FakeModels:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.generate_content_models = []
        self.generate_content_temperatures = []
        self.generate_content_configs = []

    def generate_content(self, model, contents, config):
        self.generate_content_models.append(model)
        self.generate_content_temperatures.append(getattr(config, "temperature", None))
        self.generate_content_configs.append(config)
        if self.responses:
            return self.responses.pop(0)
        return _make_response()


class _FakeClient:
    def __init__(self, responses=None):
        self.files = _FakeFiles()
        self.models = _FakeModels(responses=responses)


class _ImmediateFuture:
    def __init__(self, result):
        self._result = result

    def result(self):
        return self._result


class _ImmediateExecutor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def submit(self, fn, *args, **kwargs):
        return _ImmediateFuture(fn(*args, **kwargs))


class _FakePixmap:
    def __init__(self, payload: bytes = b"fake-page-image"):
        self.payload = payload

    def save(self, path):
        with open(path, "wb") as handle:
            handle.write(self.payload)


class _FakePage:
    def __init__(self, payload: bytes = b"fake-page-image"):
        self.payload = payload

    def get_pixmap(self):
        return _FakePixmap(payload=self.payload)


class _FakePdf:
    def __init__(self, pages):
        self._pages = list(pages)

    def __len__(self):
        return len(self._pages)

    def __getitem__(self, item):
        return self._pages[item]

    def close(self):
        return None


def _immediate_as_completed(futures):
    return list(futures)


class TestOcrFallbacks(unittest.TestCase):
    def test_default_ocr_max_output_tokens_is_8192(self):
        converter = OCRToTextConverter()
        self.assertEqual(converter.max_output_tokens, 8192)

    def test_default_document_ocr_max_output_tokens_is_8192(self):
        converter = DocumentOCRToTextConverter()
        self.assertEqual(converter.max_output_tokens, 8192)

    @patch("polytext.converter.ocr_to_text.genai.Client")
    def test_custom_ocr_max_output_tokens_is_used_in_generate_config(self, mock_client_cls):
        fake_client = _FakeClient()
        mock_client_cls.return_value = fake_client

        converter = OCRToTextConverter(max_output_tokens=3000)
        with tempfile.NamedTemporaryFile(suffix=".png") as temp_image:
            temp_image.write(b"fake-image")
            temp_image.flush()
            result = converter.get_ocr(temp_image.name)

        self.assertEqual(result["text"], "ocr text")
        self.assertEqual(converter.max_output_tokens, 3000)
        self.assertEqual(fake_client.models.generate_content_configs[-1].max_output_tokens, 3000)

    @patch("polytext.converter.document_ocr_to_text.genai.Client")
    def test_custom_document_ocr_max_output_tokens_is_used_in_generate_config(self, mock_client_cls):
        fake_client = _FakeClient()
        mock_client_cls.return_value = fake_client

        converter = DocumentOCRToTextConverter(max_output_tokens=3000)
        with tempfile.NamedTemporaryFile(suffix=".png") as temp_image:
            temp_image.write(b"fake-image")
            temp_image.flush()
            result = converter.get_ocr(temp_image.name)

        self.assertEqual(result["text"], "ocr text")
        self.assertEqual(converter.max_output_tokens, 3000)
        self.assertEqual(fake_client.models.generate_content_configs[-1].max_output_tokens, 3000)

    @patch("polytext.converter.ocr_to_text.genai.Client")
    def test_ocr_recitation_retries_with_fallback_model(self, mock_client_cls):
        fake_client = _FakeClient(
            responses=[
                _make_response("first attempt", finish_reason="RECITATION"),
                _make_response("fallback text", finish_reason="STOP"),
            ]
        )
        mock_client_cls.return_value = fake_client

        converter = OCRToTextConverter(ocr_model="gemini-3.1-flash-lite-preview")
        with tempfile.NamedTemporaryFile(suffix=".png") as temp_image:
            temp_image.write(b"fake-image")
            temp_image.flush()
            result = converter.get_ocr(temp_image.name)

        self.assertEqual(result["text"], "fallback text")
        self.assertEqual(
            fake_client.models.generate_content_models,
            ["gemini-3.1-flash-lite-preview", "gemini-3-flash-preview"],
        )
        self.assertEqual(fake_client.models.generate_content_temperatures, [0.0, 1.0])
        self.assertEqual(result["completion_model"], "gemini-3-flash-preview")
        self.assertEqual(result["fallback_from_model"], "gemini-3.1-flash-lite-preview")
        self.assertEqual(result["fallback_to_model"], "gemini-3-flash-preview")
        self.assertIn("recitation", result["fallback_reason"].lower())

    @patch("polytext.converter.ocr_to_text.genai.Client")
    def test_ocr_repetitive_tail_retries_with_fallback_model(self, mock_client_cls):
        repetitive_text = "\n".join(["Repeated OCR tail."] * 6)
        fake_client = _FakeClient(
            responses=[
                _make_response(repetitive_text, finish_reason="STOP"),
                _make_response("clean fallback text", finish_reason="STOP"),
            ]
        )
        mock_client_cls.return_value = fake_client

        converter = OCRToTextConverter(ocr_model="gemini-3.1-flash-lite-preview")
        with tempfile.NamedTemporaryFile(suffix=".png") as temp_image:
            temp_image.write(b"fake-image")
            temp_image.flush()
            result = converter.get_ocr(temp_image.name)

        self.assertEqual(result["text"], "clean fallback text")
        self.assertEqual(
            fake_client.models.generate_content_models,
            ["gemini-3.1-flash-lite-preview", "gemini-3-flash-preview"],
        )
        self.assertIn("repetitive tail", result["fallback_reason"].lower())

    @patch("polytext.converter.ocr_to_text.genai.Client")
    def test_ocr_uses_final_fallback_after_fallback_model_still_fails(self, mock_client_cls):
        fake_client = _FakeClient(
            responses=[
                _make_response("first attempt", finish_reason="MAX_TOKENS"),
                _make_response("second attempt", finish_reason="RECITATION"),
                _make_response("final fallback text", finish_reason="STOP"),
            ]
        )
        mock_client_cls.return_value = fake_client

        with patch("polytext.converter.ocr_to_text.OCR_FINAL_FALLBACK_MODEL", "gemini-2.0-flash"):
            converter = OCRToTextConverter(ocr_model="gemini-3.1-flash-lite-preview")
            with tempfile.NamedTemporaryFile(suffix=".png") as temp_image:
                temp_image.write(b"fake-image")
                temp_image.flush()
                result = converter.get_ocr(temp_image.name)

        self.assertEqual(result["text"], "final fallback text")
        self.assertEqual(
            fake_client.models.generate_content_models,
            [
                "gemini-3.1-flash-lite-preview",
                "gemini-3-flash-preview",
                "gemini-2.0-flash",
            ],
        )
        self.assertEqual(fake_client.models.generate_content_temperatures, [0.0, 1.0, 0.0])
        self.assertEqual(result["completion_model"], "gemini-2.0-flash")
        self.assertEqual(result["fallback_from_model"], "gemini-3-flash-preview")
        self.assertEqual(result["fallback_to_model"], "gemini-2.0-flash")

    @patch("polytext.converter.document_ocr_to_text.genai.Client")
    @patch("concurrent.futures.as_completed", side_effect=_immediate_as_completed)
    @patch("concurrent.futures.ThreadPoolExecutor", _ImmediateExecutor)
    @patch("fitz.open")
    def test_document_ocr_only_retries_the_problem_page(
        self,
        mock_fitz_open,
        _mock_as_completed,
        mock_client_cls,
    ):
        fake_client = _FakeClient(
            responses=[
                _make_response("page one text", finish_reason="STOP"),
                _make_response("page two first attempt", finish_reason="MAX_TOKENS"),
                _make_response("page two fallback text", finish_reason="STOP"),
            ]
        )
        mock_client_cls.return_value = fake_client
        mock_fitz_open.return_value = _FakePdf([_FakePage(), _FakePage()])

        converter = DocumentOCRToTextConverter(ocr_model="gemini-3.1-flash-lite-preview")
        result = converter.get_document_ocr("dummy.pdf")

        self.assertIn("page one text", result["text"])
        self.assertIn("page two fallback text", result["text"])
        self.assertEqual(
            fake_client.models.generate_content_models,
            [
                "gemini-3.1-flash-lite-preview",
                "gemini-3.1-flash-lite-preview",
                "gemini-3-flash-preview",
            ],
        )
        self.assertEqual(fake_client.models.generate_content_temperatures, [0.0, 0.0, 1.0])

    @patch("fitz.open")
    def test_azure_document_ocr_no_pages_is_empty_or_too_short(self, mock_fitz_open):
        mock_fitz_open.return_value = _FakePdf([])

        converter = AzureDocumentOCRToTextConverter(
            azure_endpoint="https://example.openai.azure.com",
            azure_api_version="2024-10-21",
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
            temp_pdf.write(b"%PDF-1.4\n")
            temp_pdf.flush()
            with self.assertRaises(EmptyDocument) as error_context:
                converter.get_document_ocr(temp_pdf.name)

        self.assertEqual(error_context.exception.code, 998)
        self.assertEqual(error_context.exception.message, "The document has no pages.")


if __name__ == "__main__":
    unittest.main()
