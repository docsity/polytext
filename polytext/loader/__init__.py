# polytext/loader/__init__.py
from .document import DocumentLoader
from .video import VideoLoader
from .audio import AudioLoader
from .youtube import YoutubeTranscriptLoader
from .html import HtmlLoader
from .ocr import OCRLoader
from .markdown import MarkdownLoader
from .document_ocr import DocumentOCRLoader
from .plain_text import PlainTextLoader

__all__ = ['DocumentLoader', 'VideoLoader', 'AudioLoader', 'HtmlLoader', 'YoutubeTranscriptLoader', 'OCRLoader', 'MarkdownLoader', 'DocumentOCRLoader', 'PlainTextLoader']
