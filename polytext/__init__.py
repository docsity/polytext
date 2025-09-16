# polytext/__init__.py
import os
import logging
import dotenv

logger = logging.getLogger(__name__)

# Load environment variables
dotenv.load_dotenv()

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
        )
        logger.info("Sentry monitoring initialized")
    except ImportError:
        logger.warning("Sentry DSN is configured but sentry-sdk is not installed. "
                      "Install with: pip install polytext[sentry]")

from .converter.pdf import convert_to_pdf, DocumentConverter
from .loader.document import DocumentLoader
from .exceptions.base import EmptyDocument, ExceededMaxPages, ConversionError
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