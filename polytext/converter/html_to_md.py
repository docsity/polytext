from markitdown import MarkItDown
import html2text
import requests
import io

def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/116.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text

def html_to_md(path_or_url: str) -> dict:
    if (
            path_or_url.startswith("http://")
            or path_or_url.startswith("https://")
            or path_or_url.startswith("www.")
    ):
        md = MarkItDown()
        html_content = fetch_html(path_or_url)
        stream = io.BytesIO(html_content.encode("utf-8"))
        md_text = md.convert(stream).markdown
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
