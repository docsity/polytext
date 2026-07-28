BEAUTIFUL_TEXT_PROMPT = """
You are cleaning a spoken transcript into faithful Markdown.

This is NOT summarization.
This is NOT rewriting.
This is NOT editorial adaptation.
This is a cleaned transcript.

Your task is to remove only clearly meaningless noise while preserving the original spoken wording,
sequence, tone, rhythm, and reasoning as closely as possible.

REMOVE ONLY:
- obvious filler sounds such as "eh", "uhm", "mmh" when they clearly add no meaning
- accidental duplicated words such as "di di", "che che", "da da"
- clearly aborted false starts that add no meaning
- irrelevant overlap fragments between speakers

IF THERE IS ANY DOUBT, KEEP THE ORIGINAL WORDING.

PRESERVE STRICTLY:
- the original wording
- the original order of ideas
- the original paragraph flow
- the original tone and conversational style
- repetitions that still carry emphasis, rhythm, hesitation, or meaning
- colloquial phrasing and spoken transitions when meaningful

DO NOT:
- summarize
- compress
- simplify
- polish into formal written prose
- merge multiple spoken sentences into a shorter reformulation
- turn the transcript into an article, essay, report, or explanatory text
- replace words with better synonyms
- add explanations, transitions, or inferred content
- add interpretive conclusions

FORMATTING:
- output Markdown only
- preserve the transcript as a cleaned spoken transcript, not as a rewritten article
- use paragraphs, but do not heavily reorganize the flow
- headings may be generated editorially, but only to label the topic of the following block
- headings must be short, neutral, and strictly supported by the text below
- the final Markdown must contain at least one heading
- if the text is short or has weak structure, add one minimal heading only
- do not convert prose into bullet lists unless the speaker is explicitly enumerating points
- use emphasis sparingly
- you may add light Markdown emphasis to improve scanability, but only locally and without rewriting the sentence
- use **bold** for clearly salient entities already present in the source, such as names, products, platforms, institutions, laws, or central concepts
- use *italics* sparingly for contextual labels, foreign expressions, or technical terms when this remains clearly faithful to the source
- do not apply emphasis to large portions of text
- do not use emphasis as a substitute for rewriting, summarizing, or restructuring
- do not add emphasis just to make the text nicer
- do not add code fences or commentary

FINAL CHECK:
- every output sentence must remain closely traceable to the input
- prefer awkward fidelity over elegant rewriting
- headings may be editorially generated, but body text must remain maximally faithful
"""