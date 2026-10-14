"""
VIDYA-X AI — Video Processor
Extracts audio from MP4 videos via FFmpeg and performs speech-to-text transcription
using faster-whisper. Preserves high-precision timestamps for source grounding.
"""

import os
import shutil
import subprocess
import tempfile
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Whisper Model Configuration
# ---------------------------------------------------------------------------
# Options:
#  - "tiny":  Fastest, lowest memory (~1 GB VRAM / minimal CPU), lower accuracy
#  - "base":  Recommended for hackathon demos; fast and decent accuracy (~1 GB VRAM / CPU friendly)
#  - "small": Higher accuracy, better for technical terms (~2 GB VRAM / more CPU intensive)
#  - "medium" / "large-v3": Production-grade accuracy, requires GPU / high RAM
#
# Override via environment variable WHISPER_MODEL, e.g. WHISPER_MODEL=tiny
DEFAULT_WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")


def format_timestamp(seconds: float) -> str:
    """Format floating point seconds into human-readable HH:MM:SS string."""
    total_seconds = max(0.0, float(seconds))
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    secs = int(total_seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def check_ffmpeg_available() -> bool:
    """Check if the FFmpeg binary is accessible in the current system PATH."""
    return shutil.which("ffmpeg") is not None


def extract_audio_from_video(video_path: str, output_audio_path: str) -> None:
    """
    Extract 16kHz mono audio from video file using FFmpeg (optimal format for Whisper).

    Args:
        video_path: Path to source MP4 video.
        output_audio_path: Destination path for extracted WAV audio.

    Raises:
        RuntimeError: If FFmpeg is missing or fails to extract audio.
    """
    if not check_ffmpeg_available():
        raise RuntimeError(
            "FFmpeg is not installed or not found in system PATH. "
            "FFmpeg is required for video processing and audio extraction. "
            "Please install FFmpeg and ensure 'ffmpeg' is accessible in your PATH."
        )

    # ffmpeg -i <video> -vn -acodec pcm_s16le -ar 16000 -ac 1 -y <output.wav>
    command = [
        "ffmpeg",
        "-y",               # Overwrite without asking
        "-i", video_path,   # Input video
        "-vn",              # Disable video recording
        "-acodec", "pcm_s16le",  # Uncompressed 16-bit PCM
        "-ar", "16000",     # 16kHz sampling rate required by Whisper
        "-ac", "1",         # Mono audio
        output_audio_path,
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr.strip()[:300]}")
    except Exception as exc:
        raise RuntimeError(f"Failed to execute FFmpeg for '{os.path.basename(video_path)}': {str(exc)}")


def process_video(
    file_path: str,
    file_id: str,
    file_name: str,
    model_size: str = DEFAULT_WHISPER_MODEL,
) -> List[Dict[str, Any]]:
    """
    Process an MP4 video by extracting its audio and transcribing it into timestamped units.

    Args:
        file_path: Absolute path to the saved MP4 file.
        file_id: Unique identifier for this uploaded file.
        file_name: Original file name.
        model_size: Whisper model size ("tiny", "base", "small", etc.).

    Returns:
        List of structured content units containing segment transcripts and timestamps.

    Raises:
        RuntimeError: If FFmpeg is missing or audio extraction fails.
        ValueError: If transcription fails or file is corrupted.
    """
    # Create temporary WAV audio file
    temp_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_audio_path = temp_audio_file.name
    temp_audio_file.close()

    try:
        # Step 1: Extract audio with FFmpeg
        extract_audio_from_video(file_path, temp_audio_path)

        # Step 2: Lazy import and load faster-whisper
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "faster-whisper is not installed. Please install it using: pip install faster-whisper"
            )

        # Use CPU with int8 quantization for lightweight fast local inference
        # or CUDA if available
        try:
            whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
            segments, info = whisper_model.transcribe(
                temp_audio_path,
                beam_size=5,
                word_timestamps=False,
            )
        except Exception as exc:
            raise ValueError(f"Whisper transcription failed for '{file_name}': {str(exc)}")

        # Step 3: Build structured content units
        units: List[Dict[str, Any]] = []
        unit_index = 1

        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue

            unit_id = f"unit_{unit_index:03d}"
            ts_start = format_timestamp(segment.start)
            ts_end = format_timestamp(segment.end)

            unit: Dict[str, Any] = {
                "unit_id": unit_id,
                "content": text,
                "source_type": "video",
                "file_id": file_id,
                "file_name": file_name,
                "page": None,
                "slide": None,
                "timestamp_start": ts_start,
                "timestamp_end": ts_end,
                "metadata": {
                    "start_seconds": round(segment.start, 2),
                    "end_seconds": round(segment.end, 2),
                    "detected_language": getattr(info, "language", "unknown"),
                    # Structured for future multimodal/vision expansion in Steps 4 & 5
                    "visual_content": None,
                },
            }
            units.append(unit)
            unit_index += 1

        return units

    finally:
        # Step 4: Always clean up temporary audio file
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except OSError:
                pass
