TEXT_MERGE_PROMPT = """You are an expert at merging overlapping text segments from audio transcriptions while maintaining their original content and formatting.

TASK: Combine the following two markdown-formatted text segments into a single coherent document. These segments are transcriptions from consecutive audio chunks with some overlap between them.

INSTRUCTIONS:
1. Identify the overlapping content between TEXT SEGMENT 1 and TEXT SEGMENT 2.
2. Create a seamless merge at the overlap point, removing redundant content.
3. If needed, modify the markdown formatting in order to have a consistent formatting throughout the merged document based on semantic meaning. For example titles or headings can be removed or reorganized (as they are not part of the original audio) if they alter the natural and semantically coherent flow of the text, or if they do not mark the beginning of a new at least slightly different topic.
4. Make minimal alterations to the original text - only changes necessary for a natural flow.
5. If there are formatting inconsistencies between segments (e.g., different header levels for similar content), harmonize them based on their semantic meaning.
6. Return only the merged text in markdown format without explanations.

TEXT SEGMENT 1:
{chunk_1}

TEXT SEGMENT 2:
{chunk_2}"""