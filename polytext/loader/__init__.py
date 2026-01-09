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
from .youtube_llm import YoutubeTranscriptLoaderWithLlm
from .xml_xbrl import XmlXbrlLoader
from .base import BaseLoader

__all__ = ['DocumentLoader', 'VideoLoader', 'AudioLoader', 'HtmlLoader', 'YoutubeTranscriptLoader', 'OCRLoader', 'MarkdownLoader', 'DocumentOCRLoader', 'PlainTextLoader', 'YoutubeTranscriptLoaderWithLlm', 'XmlXbrlLoader', 'BaseLoader']
