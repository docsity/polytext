# exceptions/base.py
class ConversionError(Exception):
    """
    Exception raised when document conversion to PDF fails.

    This exception is typically raised when LibreOffice fails to convert a document
    or when the conversion process encounters system-level issues.

    Attributes:
        message (str): Detailed error message describing the conversion failure
        original_exception: The underlying exception that caused the conversion failure
    """

    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception


class EmptyDocument(Exception):
    """
    Exception raised when a document contains no extractable text.

    This exception is raised when text extraction yields empty results or
    when the extracted text fails quality checks (e.g., too few characters,
    excessive repeated content).

    Attributes:
        message (str): Description of why the document is considered empty
        code (int): Error code for categorizing the type of emptiness (default: None)
    """
    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        self.code = code


class ExceededMaxPages(Exception):
    """
    Exception raised when requested page range exceeds document length.

    This exception occurs when attempting to extract text from pages beyond
    the document's actual page count or when invalid page ranges are specified.

    Attributes:
        message (str): Description of the page range error
        code (int): Error code for tracking purposes (default: None)
    """
    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        self.code = code
