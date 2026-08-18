"""Verbatim speech for the hub: edge-tts synthesis + voice-message conversion.

Both produce WAV files that ``HubState.play_file`` ships to the robot via the
SDK's ``media.play_sound`` (file upload + daemon REST) — independent of the
realtime session, so they work even while the model is idle.
"""

import os
import hashlib
import subprocess
import tempfile
from pathlib import Path

from . import db

DEFAULT_VOICE = "fr-FR-DeniseNeural"  # warm French female; override MEMOIRE_TTS_VOICE
MAX_VOICE_BYTES = 8 * 1024 * 1024
FFMPEG = os.getenv("MEMOIRE_FFMPEG", "ffmpeg")


def _data_dir(sub: str) -> Path:
    d = db.db_path().parent / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ffmpeg_to_wav(src: Path, dst: Path) -> None:
    """Convert any audio ffmpeg can read to mono 44.1k 16-bit WAV."""
    proc = subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-i", str(src),
         "-ac", "1", "-ar", "44100", "-sample_fmt", "s16", str(dst)],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0 or not dst.exists():
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[:300]}")


async def tts_to_wav(text: str) -> Path:
    """Synthesize ``text`` to a WAV file (cached by voice+text hash)."""
    import edge_tts

    voice = os.getenv("MEMOIRE_TTS_VOICE", DEFAULT_VOICE)
    key = hashlib.sha256(f"{voice}|{text}".encode()).hexdigest()[:24]
    wav = _data_dir("tts_cache") / f"{key}.wav"
    if wav.exists():
        return wav
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        mp3 = Path(tmp.name)
    try:
        await edge_tts.Communicate(text, voice).save(str(mp3))
        _ffmpeg_to_wav(mp3, wav)
    finally:
        mp3.unlink(missing_ok=True)
    return wav


def voice_message_to_wav(data: bytes, suffix: str, person: str) -> Path:
    """Store an uploaded voice message (webm/mp4/ogg/…) and convert to WAV."""
    if len(data) > MAX_VOICE_BYTES:
        raise ValueError("message vocal trop long")
    if not data:
        raise ValueError("message vocal vide")
    key = hashlib.sha256(data).hexdigest()[:24]
    vdir = _data_dir("voicemail")
    src = vdir / f"{person}-{key}{suffix}"
    wav = vdir / f"{person}-{key}.wav"
    if wav.exists():
        return wav
    src.write_bytes(data)
    try:
        _ffmpeg_to_wav(src, wav)
    finally:
        src.unlink(missing_ok=True)
    return wav
