# polytext/__init__.py
import os
import logging
import dotenv

from .exceptions.base import EmptyDocument, ExceededMaxPages, ConversionError, LoaderError

logger = logging.getLogger(__name__)

# Load environment variables
dotenv.load_dotenv()


def _filter_expected_loader_errors(event, hint):
    error = None
    if hint:
        exc_info = hint.get("exc_info")
        if exc_info:
            error = exc_info[1]
        else:
            error = hint.get("original_exception")

    if isinstance(error, LoaderError) and error.code == "NO_TEXT_DETECTED":
        return None

    exception_values = (event or {}).get("exception", {}).get("values", [])
    for exception_value in exception_values:
        exception_type = exception_value.get("type") or ""
        exception_message = exception_value.get("value")
        if exception_type.endswith("LoaderError") and exception_message == "No text detected":
            return None

    return event


# Initialize Sentry if DSN is configured
sentry_dsn = os.getenv('SENTRY_DSN_POLYTEXT')
if sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv('ENV', 'prod'),
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            before_send=_filter_expected_loader_errors,
        )
        logger.info("Sentry monitoring initialized")
    except ImportError:
        logger.warning("Sentry DSN is configured but sentry-sdk is not installed. "
                      "Install with: pip install polytext[sentry]")

from .converter.pdf import convert_to_pdf, DocumentConverter
from .loader.document import DocumentLoader
from .generator.pdf import get_customized_pdf_from_markdown, PDFGenerator

__all__ = [
    'convert_to_pdf',
    'DocumentConverter',
    'DocumentLoader',
    'EmptyDocument',
    'ExceededMaxPages',
    'ConversionError',
    'get_customized_pdf_from_markdown',
    'PDFGenerator'
]
