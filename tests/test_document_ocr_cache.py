import io
import tempfile
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from polytext.exceptions import EmptyDocument, LoaderError
from polytext.loader.base import BaseLoader
from polytext.loader.document_ocr import DocumentOCRLoader


def _missing_object_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
        "GetObject",
    )


class _ResultLoader:
    def __init__(self, result=None, error=None, events=None):
        self.result = result
        self.error = error
        self.events = events

    def load(self, input_path):
        if self.events is not None:
            self.events.append("standard")
        if self.error is not None:
            raise self.error
        return dict(self.result)


class _FallbackIntegrationBaseLoader(BaseLoader):
    def __init__(self, storage_client=None, events=None, **kwargs):
        super().__init__(**kwargs)
        self.test_storage_client = storage_client or {}
        self.events = events
        self.fallback_loader = None

    def initiate_storage(self, input):
        return self.test_storage_client

    def init_loader_class(
        self,
        input,
        storage_client,
        llm_api_key,
        is_document_fallback=False,
        **kwargs,
    ):
        if not is_document_fallback:
            return _ResultLoader(
                error=EmptyDocument(message="No text detected", code=998),
                events=self.events,
            )
        loader = super().init_loader_class(
            input=input,
            storage_client=storage_client,
            llm_api_key=llm_api_key,
            is_document_fallback=True,
            **kwargs,
        )
        loader._select_document_ocr_fn = Mock(
            return_value=Mock(return_value=dict(TestDocumentOCRCache.OCR_RESULT))
        )
        self.fallback_loader = loader
        return loader


class TestDocumentOCRCache(unittest.TestCase):
    OCR_RESULT = {
        "text": "fresh OCR transcript",
        "completion_tokens": 17,
        "prompt_tokens": 23,
        "completion_model": "ocr-model",
        "completion_model_provider": "provider",
        "text_chunks": ["chunk"],
        "ocr_failed_pages": [4],
        "ocr_failed_pages_detail": [{"page": 4, "reason": "timeout"}],
    }

    def setUp(self):
        tempfile.tempdir = None

    def tearDown(self):
        tempfile.tempdir = None

    def _run_local_ocr(self, *, provider="google", cache_client=None, cache_uri=None):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        loader = DocumentOCRLoader(
            source="local",
            temp_dir=temp_dir.name,
            ocr_provider=provider,
            is_fallback_ocr=True,
            ocr_cache_uri=cache_uri,
            ocr_cache_s3_client=cache_client,
        )
        ocr_fn = Mock(return_value=dict(self.OCR_RESULT))
        with patch.object(loader, "_select_document_ocr_fn", return_value=ocr_fn):
            result = loader.load("source/document.pdf")
        return result, ocr_fn

    def test_cache_hit_skips_ocr(self):
        cache_client = Mock()
        cache_client.get_object.return_value = {
            "Body": io.BytesIO(b"cached transcript"),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = DocumentOCRLoader(
                source="cloud",
                temp_dir=temp_dir,
                ocr_provider="google",
                is_fallback_ocr=True,
                ocr_cache_uri="s3://cache-bucket/transcripts/document.txt",
                ocr_cache_s3_client=cache_client,
            )

            with patch.object(loader, "download_document") as download_document:
                with patch.object(loader, "convert_doc_to_pdf") as convert_doc_to_pdf:
                    with patch.object(loader, "_select_document_ocr_fn") as select_ocr:
                        result = loader.load("source/document.pdf")

        self.assertEqual(
            result,
            {
                "text": "cached transcript",
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "completion_model": "not provided",
                "completion_model_provider": "not provided",
                "text_chunks": "not provided",
                "type": "document_ocr",
                "input": "source/document.pdf",
                "ocr_provider": "google",
                "ocr_cache_hit": True,
            },
        )
        download_document.assert_not_called()
        convert_doc_to_pdf.assert_not_called()
        select_ocr.assert_not_called()

    def test_cache_miss_runs_ocr_preserves_metadata_and_writes_exact_text(self):
        cache_client = Mock()
        cache_client.get_object.side_effect = _missing_object_error()

        result, ocr_fn = self._run_local_ocr(
            cache_client=cache_client,
            cache_uri="s3://cache-bucket/exact/transcript.txt",
        )

        expected = {
            **self.OCR_RESULT,
            "type": "document_ocr",
            "input": "source/document.pdf",
            "ocr_provider": "google",
            "ocr_cache_hit": False,
        }
        self.assertEqual(result, expected)
        pre_change_result = {key: value for key, value in expected.items() if key != "ocr_cache_hit"}
        for key, value in pre_change_result.items():
            self.assertIs(type(result[key]), type(value), key)
        ocr_fn.assert_called_once()
        cache_client.put_object.assert_called_once_with(
            Bucket="cache-bucket",
            Key="exact/transcript.txt",
            Body=b"fresh OCR transcript",
            ContentType="text/markdown; charset=utf-8",
        )

    def test_empty_or_invalid_cache_runs_ocr_and_rewrites_cache(self):
        cache_bodies = (b" \n\t", b"\xff")
        for cache_body in cache_bodies:
            with self.subTest(cache_body=cache_body):
                cache_client = Mock()
                cache_client.get_object.return_value = {
                    "Body": io.BytesIO(cache_body),
                }

                result, ocr_fn = self._run_local_ocr(
                    cache_client=cache_client,
                    cache_uri="s3://bucket/cache.md",
                )

                self.assertFalse(result["ocr_cache_hit"])
                ocr_fn.assert_called_once()
                self.assertEqual(
                    cache_client.put_object.call_args.kwargs["Body"],
                    b"fresh OCR transcript",
                )

    def test_fallback_without_cache_uri_runs_ocr_and_marks_miss(self):
        cache_client = Mock()

        result, ocr_fn = self._run_local_ocr(cache_client=cache_client)

        self.assertFalse(result["ocr_cache_hit"])
        ocr_fn.assert_called_once()
        cache_client.get_object.assert_not_called()
        cache_client.put_object.assert_not_called()

    def test_cache_write_failure_does_not_change_ocr_result(self):
        cache_client = Mock()
        cache_client.get_object.side_effect = _missing_object_error()
        cache_client.put_object.side_effect = RuntimeError("write unavailable")

        with self.assertLogs("polytext.loader.ocr_cache", level="WARNING"):
            result, _ = self._run_local_ocr(
                cache_client=cache_client,
                cache_uri="s3://bucket/cache.md",
            )

        self.assertEqual(result["text"], "fresh OCR transcript")
        self.assertEqual(result["completion_tokens"], 17)
        self.assertFalse(result["ocr_cache_hit"])

    def test_ocr_failure_is_raised_without_writing_cache(self):
        cache_client = Mock()
        cache_client.get_object.side_effect = _missing_object_error()
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        loader = DocumentOCRLoader(
            source="local",
            temp_dir=temp_dir.name,
            is_fallback_ocr=True,
            ocr_cache_uri="s3://bucket/cache.txt",
            ocr_cache_s3_client=cache_client,
        )
        ocr_error = RuntimeError("OCR failed")
        with patch.object(
            loader,
            "_select_document_ocr_fn",
            return_value=Mock(side_effect=ocr_error),
        ):
            with self.assertRaises(RuntimeError) as error_context:
                loader.load("document.pdf")

        self.assertIs(error_context.exception, ocr_error)
        cache_client.put_object.assert_not_called()

    def test_cache_miss_preserves_google_and_azure_provider_routing(self):
        for provider in ("google", "azure"):
            with self.subTest(provider=provider):
                cache_client = Mock()
                cache_client.get_object.side_effect = _missing_object_error()

                result, ocr_fn = self._run_local_ocr(
                    provider=provider,
                    cache_client=cache_client,
                    cache_uri="s3://bucket/cache.md",
                )

                ocr_fn.assert_called_once()
                self.assertEqual(result["ocr_provider"], provider)
                self.assertFalse(result["ocr_cache_hit"])

    def test_standard_success_does_not_resolve_or_read_cache(self):
        old_item = {
            "text": "standard extraction",
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "completion_model": "not provided",
            "completion_model_provider": "not provided",
            "text_chunks": "not provided",
            "type": "document",
            "input": "document.pdf",
        }

        class SuccessfulBaseLoader(BaseLoader):
            def initiate_storage(self, input):
                return {}

            def init_loader_class(self, *args, **kwargs):
                return _ResultLoader(result=old_item)

        loader = SuccessfulBaseLoader(
            source="local",
            fallback_ocr=True,
            ocr_cache_uri="s3://bucket/cache.txt",
        )
        with patch("polytext.loader.base.create_s3_client") as create_client:
            result = loader.get_text(["document.pdf"])

        self.assertEqual(
            result,
            {
                "text": "standard extraction",
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "output_list": [old_item],
            },
        )
        create_client.assert_not_called()
        self.assertNotIn("ocr_cache_hit", result)

    def test_fallback_cache_hit_is_propagated_and_reuses_input_s3_client(self):
        input_s3_client = Mock()
        input_s3_client.get_object.return_value = {
            "Body": io.BytesIO(b"cached from another bucket"),
        }
        loader = _FallbackIntegrationBaseLoader(
            storage_client={
                "s3_client": input_s3_client,
                "document_aws_bucket": "source-bucket",
                "file_path": "source/document.pdf",
            },
            source="cloud",
            fallback_ocr=True,
            ocr_cache_uri="s3://cache-bucket/exact/transcript.txt",
        )

        with patch("polytext.loader.base.create_s3_client") as create_client:
            result = loader.get_text(["s3://source-bucket/source/document.pdf"])

        self.assertEqual(result["text"], "cached from another bucket")
        self.assertEqual(result["completion_tokens"], 0)
        self.assertEqual(result["prompt_tokens"], 0)
        self.assertTrue(result["ocr_cache_hit"])
        self.assertTrue(result["output_list"][0]["ocr_cache_hit"])
        input_s3_client.get_object.assert_called_once_with(
            Bucket="cache-bucket",
            Key="exact/transcript.txt",
        )
        create_client.assert_not_called()

    def test_local_fallback_creates_cache_client_only_after_standard_failure(self):
        events = []
        cache_client = Mock()
        cache_client.get_object.return_value = {"Body": io.BytesIO(b"cached")}
        loader = _FallbackIntegrationBaseLoader(
            events=events,
            source="local",
            fallback_ocr=True,
            ocr_cache_uri="s3://bucket/cache.txt",
        )

        def create_client(**kwargs):
            events.append("factory")
            return cache_client

        with patch("polytext.loader.base.create_s3_client", side_effect=create_client):
            result = loader.get_text(["document.pdf"])

        self.assertEqual(events, ["standard", "factory"])
        self.assertTrue(result["ocr_cache_hit"])

    def test_gcs_fallback_lazily_creates_s3_cache_client(self):
        events = []
        cache_client = Mock()
        cache_client.get_object.return_value = {"Body": io.BytesIO(b"cached")}
        loader = _FallbackIntegrationBaseLoader(
            storage_client={
                "gcs_client": Mock(),
                "document_gcs_bucket": "source-bucket",
                "file_path": "source/document.pdf",
            },
            events=events,
            source="cloud",
            fallback_ocr=True,
            ocr_cache_uri="s3://cache-bucket/cache.txt",
        )

        def create_client(**kwargs):
            events.append("factory")
            return cache_client

        with patch("polytext.loader.base.create_s3_client", side_effect=create_client):
            result = loader.get_text(["gcs://source-bucket/source/document.pdf"])

        self.assertEqual(events, ["standard", "factory"])
        self.assertTrue(result["ocr_cache_hit"])
        cache_client.get_object.assert_called_once_with(
            Bucket="cache-bucket",
            Key="cache.txt",
        )

    def test_cache_client_creation_failure_falls_back_to_ocr(self):
        loader = _FallbackIntegrationBaseLoader(
            source="local",
            fallback_ocr=True,
            ocr_cache_uri="s3://bucket/cache.txt",
        )

        with patch(
            "polytext.loader.base.create_s3_client",
            side_effect=RuntimeError("credentials unavailable"),
        ):
            with self.assertLogs("polytext.loader.base", level="WARNING"):
                result = loader.get_text(["document.pdf"])

        self.assertEqual(result["text"], "fresh OCR transcript")
        self.assertFalse(result["ocr_cache_hit"])
        self.assertFalse(result["output_list"][0]["ocr_cache_hit"])

    def test_fallback_without_uri_marks_ocr_as_cache_miss_at_both_levels(self):
        loader = _FallbackIntegrationBaseLoader(
            source="local",
            fallback_ocr=True,
        )

        with patch("polytext.loader.base.create_s3_client") as create_client:
            result = loader.get_text(["document.pdf"])

        self.assertFalse(result["ocr_cache_hit"])
        self.assertFalse(result["output_list"][0]["ocr_cache_hit"])
        create_client.assert_not_called()

    def test_force_ocr_ignores_cache_configuration_and_payload_has_no_flag(self):
        loader = BaseLoader(
            source="local",
            force_ocr=True,
            ocr_cache_uri="s3://bucket/cache.txt",
        )
        document_loader = loader.init_loader_class(
            input="document.pdf",
            storage_client={},
            llm_api_key=None,
            source="local",
        )
        document_loader._select_document_ocr_fn = Mock(
            return_value=Mock(return_value=dict(self.OCR_RESULT))
        )

        result = loader.run_loader_class(document_loader, ["document.pdf"])

        self.assertFalse(document_loader.is_fallback_ocr)
        self.assertIsNone(document_loader.ocr_cache_uri)
        self.assertNotIn("ocr_cache_hit", result)
        self.assertNotIn("ocr_cache_hit", result["output_list"][0])
        self.assertEqual(
            result["output_list"][0],
            {
                **self.OCR_RESULT,
                "type": "document_ocr",
                "input": "document.pdf",
                "ocr_provider": "google",
            },
        )


if __name__ == "__main__":
    unittest.main()
