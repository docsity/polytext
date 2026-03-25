# Audio Chunk Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Mirror the YouTube anti-hallucination fallback logic in audio transcription while ensuring only failing chunks are retried.

**Architecture:** Keep `polytext/loader/audio.py` thin and move the new behavior into `polytext/converter/audio_to_text.py`, where single-file and chunked audio transcription already converge. Add shared guard helpers, chunk-local fallback orchestration, and regression tests covering each guarded failure mode.

**Tech Stack:** Python 3.12+, Google GenAI SDK, `retry`, `pytest`, `unittest.mock`

---

### Task 1: Add failing tests for guarded fallback triggers

**Files:**
- Modify: `tests/test_audio_transcription_model_migration.py`
- Modify: `polytext/converter/audio_to_text.py`

**Step 1: Write the failing test**

Add focused tests for:

- `RECITATION` finish reason triggers fallback to the configured fallback model
- `MAX_TOKENS` finish reason triggers fallback
- repetitive tail detection triggers fallback even when finish reason is otherwise acceptable
- a healthy transcript does not use fallback

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audio_transcription_model_migration.py -q`
Expected: FAIL because the audio converter does not yet inspect finish reasons or repetitive tails.

**Step 3: Write minimal implementation**

Add helper plumbing in `polytext/converter/audio_to_text.py` for:

- finish reason extraction
- repetitive-tail detection
- fallback-model decision helpers
- transcript result metadata

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_audio_transcription_model_migration.py -q`
Expected: PASS for the new fallback-trigger tests.

**Step 5: Commit**

```bash
git add tests/test_audio_transcription_model_migration.py polytext/converter/audio_to_text.py
git commit -m "feat: add guarded fallback for audio transcription"
```

### Task 2: Add failing test for chunk-local retry

**Files:**
- Modify: `tests/test_audio_transcription_model_migration.py`
- Modify: `polytext/converter/audio_to_text.py`

**Step 1: Write the failing test**

Add a test that simulates multiple chunks where only one chunk produces a guarded failure and confirm only that chunk is retried with fallback.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audio_transcription_model_migration.py -q`
Expected: FAIL because the converter does not yet expose chunk-local fallback behavior clearly enough.

**Step 3: Write minimal implementation**

Keep `process_chunk()` calling `transcribe_audio()` once per chunk and ensure fallback remains inside `transcribe_audio()` so retry scope stays local to the chunk.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_audio_transcription_model_migration.py -q`
Expected: PASS with only the bad chunk retried.

**Step 5: Commit**

```bash
git add tests/test_audio_transcription_model_migration.py polytext/converter/audio_to_text.py
git commit -m "test: cover chunk-local audio fallback"
```

### Task 3: Wire metadata through full-audio results

**Files:**
- Modify: `polytext/converter/audio_to_text.py`
- Modify: `polytext/loader/audio.py`
- Test: `tests/test_audio_transcription_model_migration.py`

**Step 1: Write the failing test**

Add or extend a test asserting the returned result includes the fallback and finish metadata needed for observability.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audio_transcription_model_migration.py -q`
Expected: FAIL because the metadata is not yet fully surfaced.

**Step 3: Write minimal implementation**

Return the metadata from chunk or single-file transcription and pass it through the loader without changing its high-level role.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_audio_transcription_model_migration.py -q`
Expected: PASS with the new metadata fields present.

**Step 5: Commit**

```bash
git add tests/test_audio_transcription_model_migration.py polytext/converter/audio_to_text.py polytext/loader/audio.py
git commit -m "feat: surface audio fallback metadata"
```

### Task 4: Run focused verification

**Files:**
- Modify: `tests/test_audio_transcription_model_migration.py`
- Modify: `polytext/converter/audio_to_text.py`
- Modify: `polytext/loader/audio.py`

**Step 1: Run the focused test suite**

Run: `python3 -m pytest tests/test_audio_transcription_model_migration.py -q`
Expected: PASS.

**Step 2: Run any additional directly affected tests**

Run: `python3 -m pytest tests/test_audio_chunker.py -q`
Expected: PASS.

**Step 3: Review the diff**

Run: `git diff -- polytext/converter/audio_to_text.py polytext/loader/audio.py tests/test_audio_transcription_model_migration.py`
Expected: only the intended fallback and metadata changes.

**Step 4: Commit**

```bash
git add polytext/converter/audio_to_text.py polytext/loader/audio.py tests/test_audio_transcription_model_migration.py docs/plans/2026-03-25-audio-chunk-fallback-design.md docs/plans/2026-03-25-audio-chunk-fallback.md
git commit -m "feat: add chunk-local audio fallback safeguards"
```
