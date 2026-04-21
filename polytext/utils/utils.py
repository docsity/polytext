import re


_EXTRA_SPACE_PATTERN = re.compile(r"[ \t]+")
_MARKDOWN_HEADING_PATTERN = re.compile(r"^#+\s+")
_SENTENCE_ENDING_PATTERN = re.compile(r'[.!?:;][)"\']*$')


def remove_markdown_strip(text: str) -> str:
    start_tag = "```markdown"
    end_tag = "```"

    # Remove start tag
    if text.startswith(start_tag):
        text = text[len(start_tag):].lstrip("\n")

    # Remove end tag
    if text.endswith(end_tag):
        text = text[:-len(end_tag)].rstrip("\n")

    return text


def clean_extracted_text_whitespace(text: str) -> str:
    if not text:
        return text

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines = []

    for raw_line in normalized_text.split("\n"):
        line = _EXTRA_SPACE_PATTERN.sub(" ", raw_line).strip()

        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        if not cleaned_lines or cleaned_lines[-1] == "":
            cleaned_lines.append(line)
            continue

        if _MARKDOWN_HEADING_PATTERN.match(line):
            cleaned_lines.append(line)
            continue

        previous_line = cleaned_lines[-1]
        if _MARKDOWN_HEADING_PATTERN.match(previous_line) or _SENTENCE_ENDING_PATTERN.search(previous_line):
            cleaned_lines.append(line)
            continue

        cleaned_lines[-1] = f"{previous_line} {line}"

    if cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()

    return "\n".join(cleaned_lines)
