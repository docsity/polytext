import unittest
from unittest.mock import Mock, patch

from polytext.exceptions import ConversionError, EmptyDocument, LoaderError
from polytext.loader.base import BaseLoader


class _FailingLoader:
    def __init__(self, error):
        self.error = error

    def load(self, input_path):
        raise self.error


class _FakeBaseLoader(BaseLoader):
    def __init__(self, error, **kwargs):
        super().__init__(**kwargs)
        self.error = error

    def initiate_storage(self, input):
        return {}

    def init_loader_class(self, input, storage_client, llm_api_key, is_document_fallback=False, **kwargs):
        return _FailingLoader(self.error)


class _FallbackFailingBaseLoader(BaseLoader):
    def __init__(self, initial_error, fallback_error, **kwargs):
        super().__init__(**kwargs)
        self.initial_error = initial_error
        self.fallback_error = fallback_error

    def initiate_storage(self, input):
        return {}

    def init_loader_class(self, input, storage_client, llm_api_key, is_document_fallback=False, **kwargs):
        if is_document_fallback:
            return _FailingLoader(self.fallback_error)
        return _FailingLoader(self.initial_error)


class _BeautifulTextLoader(BaseLoader):
    def __init__(self, raw_result=None, **kwargs):
        super().__init__(**kwargs)
        self.raw_result = raw_result or {
            "text": "raw text",
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "completion_model": "not provided",
            "completion_model_provider": "not provided",
            "text_chunks": "not provided",
            "type": "text",
            "input": "dummy input",
        }

    def extract_raw_text_for_beautiful_text(self, input_value: str, **kwargs) -> dict:
        return self.raw_result


class TestBaseLoaderErrorMapping(unittest.TestCase):
    def test_llm_output_empty_document_codes_are_raised_as_loader_errors(self):
        cases = [
            (993, "CONTENT_FILTER"),
            (994, "EMPTY_LLM_OUTPUT"),
            (995, "INVALID_ARGUMENT"),
            (996, "RECITATION"),
            (997, "REPETITIVE_OUTPUT"),
            (999, "MAX_TOKENS"),
        ]

        for empty_document_code, expected_loader_code in cases:
            with self.subTest(empty_document_code=empty_document_code):
                loader = _FakeBaseLoader(
                    EmptyDocument(
                        message=f"diagnostic failure {empty_document_code}",
                        code=empty_document_code,
                    )
                )

                sentry_sdk = Mock()
                with patch("polytext.loader.base.logger.info") as mock_info:
                    with patch("polytext.loader.base.logger.exception") as mock_exception:
                        with patch.dict("sys.modules", {"sentry_sdk": sentry_sdk}):
                            with self.assertRaises(LoaderError) as error_context:
                                loader.get_text(["dummy.txt"])

                error = error_context.exception
                self.assertEqual(error.status, 422)
                self.assertEqual(error.code, expected_loader_code)
                self.assertEqual(error.message, f"diagnostic failure {empty_document_code}")
                mock_info.assert_not_called()
                mock_exception.assert_not_called()
                sentry_sdk.capture_exception.assert_called_once()
                self.assertIs(sentry_sdk.capture_exception.call_args.args[0], error.__cause__)

    def test_empty_or_too_short_documents_are_raised_as_loader_errors(self):
        loader = _FakeBaseLoader(
            EmptyDocument(
                message="Document text with less than 400 characters",
                code=998,
            )
        )

        sentry_sdk = Mock()
        with patch("polytext.loader.base.logger.info") as mock_info:
            with patch("polytext.loader.base.logger.exception") as mock_exception:
                with patch.dict("sys.modules", {"sentry_sdk": sentry_sdk}):
                    with self.assertRaises(LoaderError) as error_context:
                        loader.get_text(["empty.txt"])

        error = error_context.exception
        self.assertEqual(error.status, 422)
        self.assertEqual(error.code, "NO_TEXT_DETECTED")
        self.assertEqual(error.message, "No text detected")
        mock_info.assert_not_called()
        mock_exception.assert_not_called()
        sentry_sdk.capture_exception.assert_not_called()

    def test_empty_document_after_fallback_ocr_is_raised_as_loader_error(self):
        loader = _FallbackFailingBaseLoader(
            initial_error=EmptyDocument(
                message="No text detected",
                code=998,
            ),
            fallback_error=EmptyDocument(
                message="No text extracted from OCR fallback",
            ),
            fallback_ocr=True,
        )

        sentry_sdk = Mock()
        with patch("polytext.loader.base.logger.info") as mock_info:
            with patch("polytext.loader.base.logger.exception") as mock_exception:
                with patch.dict("sys.modules", {"sentry_sdk": sentry_sdk}):
                    with self.assertRaises(LoaderError) as error_context:
                        loader.get_text(["empty.pdf"])

        error = error_context.exception
        self.assertEqual(error.status, 422)
        self.assertEqual(error.code, "NO_TEXT_DETECTED")
        self.assertEqual(error.message, "No text detected")
        mock_info.assert_not_called()
        mock_exception.assert_not_called()
        sentry_sdk.capture_exception.assert_not_called()

    def test_conversion_error_is_raised_as_loader_error(self):
        conversion_error = ConversionError("LibreOffice failed")
        loader = _FakeBaseLoader(conversion_error)

        sentry_sdk = Mock()
        with patch("polytext.loader.base.logger.info") as mock_info:
            with patch("polytext.loader.base.logger.exception") as mock_exception:
                with patch.dict("sys.modules", {"sentry_sdk": sentry_sdk}):
                    with self.assertRaises(LoaderError) as error_context:
                        loader.get_text(["document.docx"])

        error = error_context.exception
        self.assertEqual(error.status, 422)
        self.assertEqual(error.code, "CONVERSION_ERROR")
        self.assertEqual(error.message, "LibreOffice failed")
        mock_info.assert_not_called()
        mock_exception.assert_not_called()
        sentry_sdk.capture_exception.assert_called_once_with(conversion_error)

    def test_beautiful_text_without_detected_chapters_is_raised_as_loader_error(self):
        loader = _BeautifulTextLoader()
        cleanup_result = {
            "text": "Short text without headings.",
            "completion_tokens": 1,
            "prompt_tokens": 1,
            "completion_model": "gemini-3.1-flash-lite",
            "completion_model_provider": "google",
            "text_chunks": "not provided",
            "markdown_json": {"root": ["Short text without headings."]},
            "chapters": [],
        }

        fake_converter_class = Mock()
        fake_converter_class.return_value.convert.return_value = cleanup_result

        with patch("polytext.loader.base.BeautifulTextConverter", fake_converter_class):
            with self.assertRaises(LoaderError) as error_context:
                loader.get_beautiful_text(["dummy input"], active_chapters=True)

        error = error_context.exception
        self.assertEqual(error.status, 422)
        self.assertEqual(error.code, "NO_CHAPTERS_DETECTED")
        self.assertEqual(error.message, "No chapters detected")


if __name__ == "__main__":
    unittest.main()
