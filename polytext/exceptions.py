class ConversionError(Exception):
    """Exception raised when document conversion fails."""
    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception

class EmptyDocument(Exception):
    """Exception raised when a document contains no text."""
    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        self.code = code

class ExceededMaxPages(Exception):
    """Exception raised when requested page range exceeds document length."""
    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        self.code = code