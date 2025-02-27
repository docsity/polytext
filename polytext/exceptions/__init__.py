# polytext/exceptions/__init__.py
from .base import EmptyDocument, ExceededMaxPages, ConversionError

__all__ = ['EmptyDocument', 'ExceededMaxPages', 'ConversionError']