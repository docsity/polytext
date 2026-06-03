import unittest
from unittest.mock import Mock, patch

from polytext.exceptions import EmptyDocument, LoaderError
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


class TestBaseLoaderErrorMapping(unittest.TestCase):
    def test_llm_output_empty_document_codes_are_raised_as_loader_errors(self):
        cases = [
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

    def test_empty_or_too_short_documents_still_return_empty_response(self):
        loader = _FakeBaseLoader(
            EmptyDocument(
                message="Document text with less than 400 characters",
                code=998,
            )
        )

        with patch("polytext.loader.base.logger.exception") as mock_exception:
            response = loader.get_text(["empty.txt"])

        self.assertEqual(response["text"], "")
        self.assertEqual(response["completion_tokens"], 0)
        self.assertEqual(response["prompt_tokens"], 0)
        self.assertEqual(response["output_list"][0]["input"], "empty.txt")
        mock_exception.assert_not_called()


if __name__ == "__main__":
    unittest.main()
