def merge_texts(text1, text2, k=5, min_matches=3):
    """
    Merge two texts by finding where they overlap and combining them.

    Args:
        text1 (str): The first text (beginning part)
        text2 (str): The second text (ending part)
        k (int): Number of words from text2 to search for in text1
        min_matches (int): Minimum number of matching words required to merge

    Returns:
        str: The merged text, or original texts concatenated if no good merge point found
    """
    # Clean and split the texts into words
    import re

    def clean_and_split(text):
        # Convert to lowercase and split by whitespace
        return re.findall(r'\b\w+\b', text.lower())

    words1 = clean_and_split(text1)
    words2 = clean_and_split(text2)

    if len(words2) < k or len(words1) < k:
        return text1 + " " + text2  # Texts too short for meaningful merge

    # Get the first k words of text2
    search_words = words2[:k]

    # Maximum number of words to check in text1 (last k+20 words)
    check_length = min(len(words1), k + 20)

    best_match_count = 0
    best_match_position = -1

    # Check each possible position in the last part of text1
    for i in range(max(0, len(words1) - check_length), len(words1) - k + 1):
        matches = 0
        for j in range(k):
            if i + j < len(words1) and words1[i + j] == search_words[j]:
                matches += 1

        if matches > best_match_count:
            best_match_count = matches
            best_match_position = i

    # If we found enough matching words, perform the merge
    if best_match_count >= min_matches and best_match_position != -1:
        # Find the position in the original text1 that corresponds to best_match_position
        # We need to map from word index to character index
        char_position = 0
        word_count = 0

        for m in re.finditer(r'\b\w+\b', text1.lower()):
            if word_count == best_match_position:
                char_position = m.start()
                break
            word_count += 1

        # Get all of text1 up to the match point
        merged_text = text1[:char_position]

        # Add text2 content from after the matching section
        # We're being cautious here, keeping k words and then adding the rest
        merged_text += " " + text2

        return merged_text

    # If no good merge found, just concatenate the texts
    return text1 + " " + text2

def merge_chunks(chunks, k=5, min_matches=3):
    """
    Merge an ordered list of text chunks into a single document.

    Parameters
    ----------
    chunks : list[str]
        [chunk_1, chunk_2, …] in their natural order.
    k : int, optional
        Passed straight through to `merge_texts`.
    min_matches : int, optional
        Passed straight through to `merge_texts`.

    Returns
    -------
    str
        One continuous piece of text produced by repeatedly calling
        `merge_texts` on successive pairs:
        result = merge_texts(chunk_1, chunk_2)
        result = merge_texts(result,  chunk_3)
        …
    """
    if not chunks:                     # Handle an empty list gracefully
        return ""

    merged = chunks[0]
    for nxt in chunks[1:]:
        merged = merge_texts(merged, nxt, k=k, min_matches=min_matches)
    return merged
