"""Shared state between the launcher patches and the hub API."""

import asyncio
import threading
from datetime import datetime
from typing import Any, Optional


class HubState:
    """References into the live conversation-app process."""

    def __init__(self) -> None:
        self.stream: Optional[Any] = None  # LocalStream, attached by launch_patched
        self.run_id: str = datetime.now().isoformat(timespec="seconds")
        self._lock = threading.Lock()

    def attach(self, stream: Any) -> None:
        with self._lock:
            self.stream = stream

    # ── robot / conversation accessors ──────────────────────────────────

    def robot(self) -> Optional[Any]:
        s = self.stream
        return getattr(s, "_robot", None) if s is not None else None

    def snapshot_jpeg(self) -> Optional[bytes]:
        robot = self.robot()
        if robot is None:
            return None
        media = getattr(robot, "media", None)
        if media is None:
            return None
        return media.get_frame_jpeg()

    def session_connected(self) -> bool:
        s = self.stream
        if s is None:
            return False
        try:
            return bool(s.handler._is_connected())
        except Exception:
            return False

    async def play_file(self, path: str) -> None:
        """Play a local audio file on the robot speaker (upload + daemon REST,
        via SDK ``media.play_sound``). Independent of the realtime session.
        Barges in on any assistant speech first.
        """
        robot = self.robot()
        if robot is None or getattr(robot, "media", None) is None:
            raise RuntimeError("robot media unavailable")
        stream = self.stream
        if stream is not None:
            try:
                stream.clear_audio_queue()
            except Exception:
                pass
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, robot.media.play_sound, str(path))

    async def say(self, text: str) -> None:
        """Barge in and voice ``text`` (injected turn, mirrors upstream's
        conversation.say RPC). Cross-loop safe: the hub server runs its own
        event loop, the handler lives on the app's main loop.
        """
        stream = self.stream
        if stream is None or not self.session_connected():
            raise RuntimeError("no active conversation session")
        stream.clear_audio_queue()
        loop = getattr(stream, "_asyncio_loop", None)
        if loop is not None and loop is not asyncio.get_running_loop():
            fut = asyncio.run_coroutine_threadsafe(stream.handler.say(text), loop)
            await asyncio.wait_for(asyncio.wrap_future(fut), timeout=15)
        else:
            await stream.handler.say(text)
