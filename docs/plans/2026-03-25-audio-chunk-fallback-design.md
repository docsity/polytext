# Audio Chunk Fallback Design

## Goal

Apply the YouTube LLM anti-hallucination protections to audio transcription so recitation errors, max-token truncation, and repetitive-tail outputs are detected and retried with fallback models. In chunked audio flows, only the failing chunk should be retried.

## Context

`polytext/loader/audio.py` is only a thin loader around `polytext/converter/audio_to_text.py`. The actual Gemini transcription request, chunk processing, and merged output assembly all happen in the converter, so the converter is the correct boundary for chunk-local retries.

## Approach

Add the same guardrails introduced in commit `580e2dd` for YouTube transcription to `polytext/converter/audio_to_text.py`:

- detect `RECITATION` finish reasons and surface them as `EmptyDocument(code=996)`
- detect `MAX_TOKENS` finish reasons and surface them as `EmptyDocument(code=999)`
- detect repetitive tails in the generated transcript and surface them as `EmptyDocument(code=997)`
- retry those failures with fallback model settings
- preserve metadata about the winning attempt in the returned transcript payload

The retry logic will stay inside `AudioToTextConverter.transcribe_audio()`. Since each chunk is transcribed independently through `process_chunk()`, only the chunk that fails quality checks will be retried. Healthy chunks will not be re-run.

## Fallback Strategy

Use the same fallback sequence as the YouTube loader:

1. primary audio model
2. fallback model with adjusted temperature for affected outputs
3. final fallback model if the first fallback still hits the guarded failure modes

The fallback decision should be based on the current attempt, model, temperature, and `EmptyDocument.code`, matching the YouTube behavior as closely as possible without changing the audio-specific request shape.

## Metadata

Each chunk-level transcription result should expose enough metadata for downstream inspection:

- `completion_model`
- `completion_model_provider`
- `finish_reason`
- `max_output_tokens`
- `temperature`
- `fallback_from_model`
- `fallback_to_model`
- `fallback_reason`
- `fallback_temperature`

The full-audio result should continue exposing aggregate token counts and the final text. For chunked audio, metadata from chunk retries should be preserved in chunk payloads and surfaced in a lightweight aggregate form if practical without broad API breakage.

## Token Budgets

The converter should stop using one variable for two meanings.

- `max_llm_tokens` remains the chunk-sizing budget passed to `AudioChunker`
- `max_output_tokens` becomes the Gemini `GenerateContentConfig.max_output_tokens` value

To stay conservative for transcription quality, the defaults should remain linked:

- default `max_llm_tokens = 4250`
- default `max_output_tokens = max_llm_tokens` unless explicitly overridden

This keeps current runtime behavior safe while making the API semantics explicit and allowing future tuning without re-coupling chunk sizing and generation output caps.

## Error Handling

- keep retry-on-transient-server-error behavior
- keep existing “no human speech detected” behavior
- preserve chunk ordering and current merge behavior
- do not retry the entire audio when only one chunk fails a guardrail

## Testing

Add regression coverage in `tests/test_audio_transcription_model_migration.py` for:

- recitation-triggered fallback
- repetitive-tail-triggered fallback
- max-tokens-triggered fallback
- healthy transcript avoiding fallback
- chunk-local retry behavior where only the failing chunk is retried
- separate token-budget semantics so chunk sizing still uses `max_llm_tokens` while Gemini config uses `max_output_tokens`

The implementation should follow TDD: add one failing test, verify the failure, implement the minimum fix, then repeat.
