# polytext/loader/__init__.py
from .text import get_document_text, extract_text_from_file, TextLoader
from .video import VideoLoader
from .audio import AudioLoader
from .youtube import YoutubeTranscriptLoader
from .html import HtmlLoader
from .ocr import OCRLoader

__all__ = ['get_document_text', 'extract_text_from_file', 'TextLoader', 'VideoLoader', 'AudioLoader', 'HtmlLoader', 'YoutubeTranscriptLoader', 'OCRLoader']