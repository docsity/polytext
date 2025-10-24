from markitdown import MarkItDown
from urllib.parse import urlparse
import html2text
import requests
import io

def detect_type_from_url_or_headers(url: str) -> str:
    # 1. Try URL extension
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return "pdf"
    if path.endswith(".html") or path.endswith(".htm"):
        return "html"

    # 2. Fallback: make HEAD request to inspect headers
    try:
        head = requests.head(url, allow_redirects=True, timeout=10)
        ctype = head.headers.get("Content-Type", "").lower()
        if "pdf" in ctype:
            return "pdf"
        if "html" in ctype:
            return "html"
    except requests.RequestException:
        pass

    # Default fallback
    return "html"

def fetch_and_convert(url: str) -> str:
    filetype = detect_type_from_url_or_headers(url)
    md = MarkItDown()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/116.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }

    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    if filetype == "pdf":
        stream = io.BytesIO(response.content)
        return md.convert(stream, extension=".pdf").markdown
    else:
        stream = io.BytesIO(response.text.encode("utf-8"))
        return md.convert(stream, extension=".html").markdown

def html_to_md(path_or_url: str) -> dict:
    if (
            path_or_url.startswith("http://")
            or path_or_url.startswith("https://")
            or path_or_url.startswith("www.")
    ):
        md_text = fetch_and_convert(path_or_url)
    else:
        with open(path_or_url, "r", encoding="utf-8") as f:
            html_content = f.read()
            h = html2text.HTML2Text()
            h.ignore_links = False
            md_text = h.handle(html_content)

    return {
        "text": md_text,
        "completion_tokens": 0,
        "prompt_tokens": 0,
        "completion_model": 'not provided',
        "completion_model_provider": 'not provided',
        "text_chunks": 'not provided'
    }
