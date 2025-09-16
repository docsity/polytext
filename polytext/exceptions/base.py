# exceptions/base.py
import json

class ConversionError(Exception):
    """
    Exception raised when document conversion to PDF fails.

    This exception is typically raised when LibreOffice fails to convert a document
    or when the conversion process encounters system-level issues.

    Attributes:
        message (str): Detailed error message describing the conversion failure
        original_exception: The underlying exception that caused the conversion failure
    """

    def __init__(self, message: str, original_exception: Exception = None) -> None:
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
    def __init__(self, message: str, code: int = None, result_dict = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.result_dict = result_dict


class ExceededMaxPages(Exception):
    """
    Exception raised when requested page range exceeds document length.

    This exception occurs when attempting to extract text from pages beyond
    the document's actual page count or when invalid page ranges are specified.

    Attributes:
        message (str): Description of the page range error
        code (int): Error code for tracking purposes (default: None)
    """
    def __init__(self, message: str, code: int = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class LoaderError(Exception):
    """Domain error that carries a JSON payload for CLI/handlers."""
    def __init__(self, message: str = "timeout gemini",
                 status: int = 504, code: str = "TIMEOUT"):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.payload = {"status": status, "code": code, "message": message}

    def to_dict(self) -> dict:
        return dict(self.payload)

    def to_json(self) -> str:
        return json.dumps(self.payload)

    # Nice for `str(e)` or logging
    def __str__(self) -> str:
        return self.to_json()


class LoaderTimeoutError(Exception):
    """Domain error that carries a JSON payload for CLI/handlers."""
    def __init__(self, message: str = "timeout gemini",
                 status: int = 504, code: str = "TIMEOUT"):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.payload = {"status": status, "code": code, "message": message}

    def to_dict(self) -> dict:
        return dict(self.payload)

    def to_json(self) -> str:
        return json.dumps(self.payload)

    # Nice for `str(e)` or logging
    def __str__(self) -> str:
        return self.to_json()