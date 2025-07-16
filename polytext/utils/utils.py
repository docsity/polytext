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