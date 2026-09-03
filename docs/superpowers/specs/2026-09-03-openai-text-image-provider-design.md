# OpenAI provider for text and image transcription

## Objective

Add direct OpenAI support to Polytext's text, single-image OCR, and multipage document OCR flows. The initial OpenAI model is `gpt-5.6-luna`, but callers may supply another compatible OpenAI model. Existing Google Gemini behavior remains the default, while the existing Azure OpenAI document backend remains separate and unchanged.

Audio, video, and YouTube processing are outside this change.

## Public configuration

`BaseLoader` continues to expose the existing public arguments:

- `provider`: selects `google`, `openai`, or an existing Azure alias where supported;
- `ocr_model`: selects the model used by OCR and, for compatibility with the current interface, the LLM model used by text-processing flows;
- `llm_api_key`: explicitly overrides the provider API key.

When `provider="openai"`, the default model is `gpt-5.6-luna`. If `llm_api_key` is absent, the official OpenAI client reads `OPENAI_API_KEY`. Missing credentials must produce a clear authentication/configuration error and credentials must never be logged or returned.

Existing callers that omit `provider` continue to use Google. Existing Google model defaults and behavior must not change as part of this feature.

Provider names are normalized at the boundary. `google` and `gemini` identify Google; `openai` identifies the direct OpenAI API; existing `azure`, `azure_openai`, and `azure_oai` aliases retain their current meaning.

## Architecture

Introduce a small provider adapter responsible only for the operations shared by the affected converters:

1. generate text from instructions and textual input;
2. generate text from instructions and one image;
3. normalize response text and token usage.

The adapter returns a provider-neutral result containing:

- generated text;
- input/prompt tokens;
- output/completion tokens;
- model;
- provider;
- provider-specific completion state when available.

Google calls continue to use `google.genai`. OpenAI calls use the official `OpenAI` client and the Responses API. Text prompts are represented as instructions plus user input. Images are sent as base64 data URLs with the detected MIME type. No OpenAI file is persisted after a request.

Provider-specific client construction, request syntax, response parsing, retryable exception classification, and token-field differences stay inside the adapter. Chunking, prompt selection, Markdown formatting, OCR image preprocessing, output dictionaries, and merge reconstruction remain in their existing components.

## Text flows

### `TextToMdConverter`

`text_to_md` and `TextToMdConverter` accept and propagate `model` and `model_provider`. Each chunk is generated through the provider adapter. When multiple chunks require an LLM merge, the same provider, model, and explicit key are passed to `TextMerger`.

### `BeautifulTextConverter`

`BeautifulTextConverter` uses the provider adapter for each cleanup chunk. `BaseLoader.get_beautiful_text` passes the configured provider and model instead of silently constructing the converter with Google defaults.

### `TextMerger`

`TextMerger` uses the provider adapter for boundary merges. Its default remains Google with the existing Gemini model so audio and every unchanged caller retain their current behavior. Text flows explicitly pass their selected provider and model, preventing mixed OpenAI/Gemini executions.

## Image OCR

`OCRLoader` preserves the configured provider and model instead of accepting only model names beginning with `gemini`. `OCRToTextConverter` keeps the existing image preprocessing and prompt construction, then calls the provider adapter with the processed image.

Gemini-specific fallback models, finish reasons, safety settings, recitation handling, and repetition retry chain apply only to Google requests. The initial OpenAI path uses bounded retries for transient OpenAI errors and reports incomplete or empty responses as OCR failures; it must not fall through to Gemini implicitly.

The result continues to expose the existing fields, with:

- `completion_model` equal to the model that actually produced the result;
- `completion_model_provider="openai"` for direct OpenAI calls;
- token counts normalized into the existing prompt/completion fields.

## Multipage document OCR

Add a direct OpenAI document OCR backend selected by `DocumentOCRLoader` for `ocr_provider="openai"`. It shares the existing document-to-PDF conversion, page selection, PDF page rendering, ordering, partial-failure policy, prompt construction, and final result schema.

Only the per-page inference implementation differs: each rendered page is sent through the same provider adapter used by single-image OCR. This avoids duplicating document orchestration and keeps Azure OpenAI isolated from direct OpenAI configuration.

If `allow_partial_ocr_failures` is enabled, failed OpenAI pages use the same inline failure representation and metadata policy as existing document OCR. Otherwise a page failure aborts the document operation.

## Error handling and retries

The adapter exposes provider-neutral transient and terminal failures while preserving the original exception as the cause.

- Google retains its current retry and fallback behavior.
- OpenAI retries rate limits, timeouts, connection failures, and server errors using a bounded policy consistent with the surrounding converter.
- Authentication, permission, invalid request, unsupported model/input, and malformed-image failures are not retried.
- Empty OpenAI output is treated as an extraction failure.
- OpenAI never silently falls back to Google, Azure, or another model.

`BaseLoader` maps provider exceptions into its existing public `LoaderError` contract where applicable without changing successful response schemas.

## Compatibility

The feature is opt-in through `provider="openai"`. Existing defaults, imports, output shapes, and Gemini/Azure behavior remain compatible. The OpenAI SDK is already a pinned project dependency, so no new runtime dependency is required.

The three locally modified manual test files are explicitly excluded from feature commits:

- `tests/test_get_audio_transcript_from_gcs.py`;
- `tests/test_get_document_ocr.py`;
- `tests/test_get_document_text.py`.

## Test strategy

Development follows test-first cycles. Unit tests use fake provider clients/responses and cover:

1. explicit `llm_api_key` precedence and environment-key fallback;
2. provider validation and alias normalization;
3. OpenAI Responses API payloads for text and image input;
4. normalized response text and token accounting;
5. provider/model propagation through `BaseLoader`, `TextToMdConverter`, `BeautifulTextConverter`, and `TextMerger`;
6. no mixed-provider merge when text is processed by OpenAI;
7. single-image OCR metadata and empty-output handling;
8. multipage OpenAI OCR page ordering and partial-failure behavior;
9. transient retry versus terminal OpenAI errors;
10. regression coverage proving unchanged Google defaults and Azure document routing.

After unit tests pass, targeted integration tests will exercise real text, image, and multipage document inputs with `gpt-5.6-luna` when `OPENAI_API_KEY` is available. Real API tests remain opt-in and are not required for the deterministic unit suite.

## Acceptance criteria

- A caller can process raw text, a supported image, or a scanned multipage document with `provider="openai"` and `ocr_model="gpt-5.6-luna"`.
- Every LLM call in an OpenAI text flow, including merges, uses OpenAI.
- Successful responses preserve Polytext's existing result shape and accurately identify model, provider, and token usage.
- Missing credentials and provider/API failures are visible and never cause an implicit cross-provider fallback.
- Existing Google and Azure tests continue to pass without callers changing configuration.
- Audio, video, and YouTube behavior is unchanged.
