import re
from collections import Counter


def normalize_text_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [normalize_text_line(chunk) for chunk in chunks if normalize_text_line(chunk)]


def repetition_ratio(items: list[str], min_occurrences: int = 2) -> float:
    if not items:
        return 0.0

    counts = Counter(items)
    repeated_items = sum(count for count in counts.values() if count >= min_occurrences)
    return repeated_items / len(items)


def has_consecutive_repetition(items: list[str], min_run_length: int = 3) -> bool:
    previous = None
    run_length = 0

    for item in items:
        if item == previous:
            run_length += 1
        else:
            previous = item
            run_length = 1

        if run_length >= min_run_length:
            return True

    return False


def tail_has_excessive_repetition(
    text: str,
    tail_lines: int,
    threshold: float,
) -> bool:
    if not text:
        return False

    lines = [normalize_text_line(line) for line in text.splitlines() if normalize_text_line(line)]
    tail = lines[-tail_lines:] if len(lines) > tail_lines else lines
    if has_consecutive_repetition(tail):
        return True
    if len(tail) >= 4 and repetition_ratio(tail) >= threshold:
        return True

    sentences = split_sentences("\n".join(tail))
    if has_consecutive_repetition(sentences):
        return True
    if len(sentences) >= 4 and repetition_ratio(sentences) >= threshold:
        return True

    return False


def extract_finish_reason(response) -> str | None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None

    finish_reason = getattr(candidates[0], "finish_reason", None)
    if finish_reason is None:
        return None
    return str(finish_reason).upper()
