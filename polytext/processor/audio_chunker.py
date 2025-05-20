import os
import logging
import ffmpeg
from pydub import AudioSegment
from typing import List, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class AudioChunker:
    def __init__(
            self,
            audio_path: str,
            max_llm_tokens: int = 8000,
            overlap_duration: int = 5000,
            tokens_per_minute: int = 200,
            prompt_overhead: int = 500
    ) -> None:
        self.audio_path = audio_path
        self.max_llm_tokens = max_llm_tokens
        self.overlap_duration = overlap_duration
        self.tokens_per_minute = tokens_per_minute
        self.prompt_overhead = prompt_overhead

        self.audio = AudioSegment.from_file(audio_path)
        self.duration_ms = len(self.audio)

    def calculate_optimal_chunk_size(self) -> int:
        """Calculate optimal chunk size in milliseconds based on LLM token limit"""
        usable_tokens = self.max_llm_tokens - self.prompt_overhead
        # Convert tokens to milliseconds of audio
        chunk_duration_minutes = usable_tokens / self.tokens_per_minute
        chunk_duration_ms = int(chunk_duration_minutes * 60 * 1000)

        # Cap at 80% of max to be safe
        return int(chunk_duration_ms * 0.8)

    def find_chunk_boundaries(self) -> List[Tuple[int, int]]:
        """Find optimal chunk boundaries at natural silence points"""
        logger.info("Finding optimal chunk boundaries...")
        optimal_chunk_ms = self.calculate_optimal_chunk_size()
        logger.info(f"Optimal chunk size: {optimal_chunk_ms}")

        chunks = []
        start = 0

        while start < self.duration_ms:
            logger.info(f"\nProcessing chunk starting at {start}ms")
            # Calculate the ideal end point for this chunk
            ideal_end = start + optimal_chunk_ms
            logger.info(f"Ideal end point: {ideal_end}ms")

            # If we're near the end, just include everything remaining
            if ideal_end + self.overlap_duration >= self.duration_ms:
                logger.info(f"Near end of audio, including remaining duration: {self.duration_ms - start}ms")
                chunks.append((start, self.duration_ms))
                break

            chunks.append((start, ideal_end))
            # Start the next chunk before this one ends to create overlap
            start = ideal_end - self.overlap_duration
            logger.info(f"Next chunk will start at {start}ms (overlap: {self.overlap_duration}ms)")

        return chunks

    def _process_single_chunk(self, chunk_info: tuple) -> Dict[str, Any]:
        """Helper method to process a single audio chunk using ffmpeg"""
        i, (start_ms, end_ms) = chunk_info

        # Ensure temp directory exists
        os.makedirs("temp", exist_ok=True)

        # Create a temporary file for this chunk
        temp_filename = f"temp/temp_chunk_{i}.mp3"

        # Calculate duration in seconds
        duration = (end_ms - start_ms) / 1000
        start_seconds = start_ms / 1000

        # Build ffmpeg command
        stream = (
            ffmpeg
            .input(self.audio_path, ss=start_seconds, t=duration)
            .output(temp_filename,
                    acodec='libmp3lame',
                    ar=16000,
                    ac=1,
                    q=9)
            .overwrite_output()
        )

        # Run ffmpeg command
        ffmpeg.run(stream, quiet=True)
        logger.info(f"Exported chunk {i + 1} to {temp_filename}")

        return {
            "index": i,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": end_ms - start_ms,
            "file_path": temp_filename,
            "transcript": None
        }

    def extract_chunks(self) -> List[Dict[str, Any]]:
        """Extract audio chunks based on calculated boundaries"""
        logger.info("Extracting chunks...")
        boundaries = self.find_chunk_boundaries()
        logger.info(f"Found {len(boundaries)} chunks")

        if len(boundaries) == 1:
            logger.info("Only one chunk found, no need to split.")
            start_ms, end_ms = boundaries[0]
            return [{
                "index": 0,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": end_ms - start_ms,
                "file_path": self.audio_path,
                "transcript": None
            }]

        # Process chunks in parallel
        chunks = [None] * len(boundaries)
        with ThreadPoolExecutor() as executor:
            # Submit all chunks to thread pool
            future_to_chunk = {
                executor.submit(self._process_single_chunk, (i, boundary)): i
                for i, boundary in enumerate(boundaries)
            }

            # Collect results maintaining order
            for future in as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                chunks[chunk_index] = future.result()

        logger.info(f"Processed {len(chunks)} chunks in parallel")
        return chunks

    @staticmethod
    def cleanup_temp_files(chunks: List[Dict[str, Any]]) -> None:
        """Remove temporary audio chunk files"""
        for chunk in chunks:
            if os.path.exists(chunk["file_path"]):
                os.remove(chunk["file_path"])
