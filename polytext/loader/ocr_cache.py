import logging
from urllib.parse import urlparse

from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)

_MISSING_OBJECT_CODES = {"NoSuchKey", "404", "NotFound"}


class S3OCRTranscriptCache:
    """Best-effort storage for a plain UTF-8 OCR transcript in S3."""

    def __init__(self, s3_client, uri: str, markdown_output: bool):
        self.s3_client = s3_client
        self.markdown_output = markdown_output
        self.bucket = None
        self.key = None

        parsed = urlparse(uri)
        if parsed.scheme == "s3" and parsed.netloc and parsed.path.startswith("/"):
            key = parsed.path[1:]
            if key:
                self.bucket = parsed.netloc
                self.key = key
                return

        logger.warning("Invalid OCR cache S3 URI; cache is disabled")

    @property
    def is_configured(self) -> bool:
        return self.bucket is not None and self.key is not None

    def read(self) -> str | None:
        if not self.is_configured:
            return None

        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=self.key)
            text = response["Body"].read().decode("utf-8")
        except ClientError as error:
            error_code = str(error.response.get("Error", {}).get("Code", ""))
            if error_code in _MISSING_OBJECT_CODES:
                return None
            logger.warning("Unable to read OCR transcript cache from S3", exc_info=True)
            return None
        except Exception:
            logger.warning("Unable to read OCR transcript cache from S3", exc_info=True)
            return None

        return text if text.strip() else None

    def write(self, text: str) -> None:
        if not self.is_configured:
            return

        content_type = (
            "text/markdown; charset=utf-8"
            if self.markdown_output
            else "text/plain; charset=utf-8"
        )
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=self.key,
                Body=text.encode("utf-8"),
                ContentType=content_type,
            )
        except Exception:
            logger.warning("Unable to write OCR transcript cache to S3", exc_info=True)
