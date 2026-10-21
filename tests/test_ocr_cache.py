import io
import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError

from polytext.loader.ocr_cache import S3OCRTranscriptCache


def _client_error(code: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": "test failure"}},
        "GetObject",
    )


class TestS3OCRTranscriptCache(unittest.TestCase):
    def test_read_returns_exact_nonempty_utf8_text_from_exact_uri(self):
        s3_client = Mock()
        s3_client.get_object.return_value = {
            "Body": io.BytesIO("  testo OCR è\n".encode("utf-8")),
        }
        cache = S3OCRTranscriptCache(
            s3_client=s3_client,
            uri="s3://cache-bucket/path/to/transcript.txt",
            markdown_output=False,
        )

        result = cache.read()

        self.assertEqual(result, "  testo OCR è\n")
        s3_client.get_object.assert_called_once_with(
            Bucket="cache-bucket",
            Key="path/to/transcript.txt",
        )

    def test_read_treats_whitespace_only_body_as_empty(self):
        s3_client = Mock()
        s3_client.get_object.return_value = {"Body": io.BytesIO(b" \n\t")}
        cache = S3OCRTranscriptCache(s3_client, "s3://bucket/cache.txt", False)

        self.assertIsNone(cache.read())

    def test_read_treats_missing_object_as_cache_miss_without_warning(self):
        for error_code in ("NoSuchKey", "404", "NotFound"):
            with self.subTest(error_code=error_code):
                s3_client = Mock()
                s3_client.get_object.side_effect = _client_error(error_code)
                cache = S3OCRTranscriptCache(
                    s3_client, "s3://bucket/cache.txt", False
                )

                with self.assertNoLogs("polytext.loader.ocr_cache", level="WARNING"):
                    self.assertIsNone(cache.read())

    def test_invalid_uri_logs_warning_and_is_a_safe_noop(self):
        for uri in ("https://bucket/cache.txt", "s3:///cache.txt", "s3://bucket"):
            with self.subTest(uri=uri):
                s3_client = Mock()
                with self.assertLogs(
                    "polytext.loader.ocr_cache", level="WARNING"
                ) as logs:
                    cache = S3OCRTranscriptCache(s3_client, uri, False)
                    self.assertIsNone(cache.read())
                    cache.write("secret transcript")

                s3_client.get_object.assert_not_called()
                s3_client.put_object.assert_not_called()
                self.assertNotIn("secret transcript", " ".join(logs.output))

    def test_invalid_utf8_logs_warning_and_returns_miss(self):
        s3_client = Mock()
        s3_client.get_object.return_value = {"Body": io.BytesIO(b"\xff")}
        cache = S3OCRTranscriptCache(s3_client, "s3://bucket/cache.txt", False)

        with self.assertLogs("polytext.loader.ocr_cache", level="WARNING"):
            self.assertIsNone(cache.read())

    def test_unexpected_read_failure_logs_warning_and_returns_miss(self):
        s3_client = Mock()
        s3_client.get_object.side_effect = RuntimeError("S3 unavailable")
        cache = S3OCRTranscriptCache(s3_client, "s3://bucket/cache.txt", False)

        with self.assertLogs("polytext.loader.ocr_cache", level="WARNING"):
            self.assertIsNone(cache.read())

    def test_write_plain_text_uses_exact_uri_bytes_and_content_type(self):
        s3_client = Mock()
        cache = S3OCRTranscriptCache(
            s3_client, "s3://other-bucket/exact/cache.txt", False
        )

        cache.write("testo è")

        s3_client.put_object.assert_called_once_with(
            Bucket="other-bucket",
            Key="exact/cache.txt",
            Body="testo è".encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )

    def test_write_markdown_uses_markdown_content_type(self):
        s3_client = Mock()
        cache = S3OCRTranscriptCache(s3_client, "s3://bucket/cache.md", True)

        cache.write("# Titolo")

        self.assertEqual(
            s3_client.put_object.call_args.kwargs["ContentType"],
            "text/markdown; charset=utf-8",
        )

    def test_write_failure_logs_warning_without_raising_or_leaking_text(self):
        s3_client = Mock()
        s3_client.put_object.side_effect = RuntimeError("S3 unavailable")
        cache = S3OCRTranscriptCache(s3_client, "s3://bucket/cache.txt", False)

        with self.assertLogs("polytext.loader.ocr_cache", level="WARNING") as logs:
            cache.write("secret transcript")

        self.assertNotIn("secret transcript", " ".join(logs.output))


if __name__ == "__main__":
    unittest.main()
