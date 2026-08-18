"""Hub FastAPI app: remote presence (say/snapshot) + caregiver dashboard."""

import json
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from . import auth, db, pages, speech
from .state import HubState

logger = logging.getLogger(__name__)

DEFAULT_PHRASES = [
    "Bonjour mon chéri, je pense à toi !",
    "As-tu bien mangé ce midi ?",
    "N'oublie pas tes médicaments ce soir.",
    "Je t'appelle ce soir, gros bisous.",
]


def phrases_path() -> Path:
    return db.db_path().parent / "phrases.json"


def load_phrases() -> list[str]:
    path = phrases_path()
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(DEFAULT_PHRASES, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            return DEFAULT_PHRASES
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [str(p) for p in data if str(p).strip()]
    except Exception:
        return DEFAULT_PHRASES


class SayBody(BaseModel):
    text: str
    mode: str = "tts"  # "tts" = verbatim robot-speaker playback, "ai" = injected turn


def build_app(state: HubState) -> FastAPI:
    app = FastAPI(title="Reachy Memoire Hub", docs_url=None, redoc_url=None)
    limiter = auth.RateLimiter()

    def _page_response(html: str, request: Request) -> HTMLResponse:
        """Serve a page; if auth came via ?t=, persist it as a cookie."""
        resp = HTMLResponse(html)
        token = request.query_params.get("t")
        if token:
            resp.set_cookie(
                auth.COOKIE_NAME, token, max_age=180 * 24 * 3600, httponly=True, samesite="lax"
            )
        return resp

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "session": state.session_connected()}

    @app.get("/")
    def index(person: str = Depends(auth.require_person)) -> RedirectResponse:
        return RedirectResponse("/care")

    @app.get("/famille")
    def famille(request: Request, person: str = Depends(auth.require_person)) -> HTMLResponse:
        return _page_response(pages.famille_page(person), request)

    @app.get("/care")
    def care(
        request: Request, day: str | None = None, person: str = Depends(auth.require_person)
    ) -> HTMLResponse:
        return _page_response(pages.care_page(day), request)

    # ── remote presence API ─────────────────────────────────────────────

    @app.post("/api/say")
    async def say(body: SayBody, person: str = Depends(auth.require_person)) -> dict:
        text = body.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="message vide")
        if len(text) > 400:
            raise HTTPException(status_code=422, detail="message trop long (400 max)")
        limiter.check("say", person, 5.0)
        try:
            if body.mode == "ai":
                await state.say(
                    f"{person.capitalize()} envoie ce message par téléphone. "
                    f"Dis-le à voix haute en le citant fidèlement : « {text} »"
                )
            else:
                intro = await speech.tts_to_wav(f"Message de {person}.")
                wav = await speech.tts_to_wav(text)
                await state.play_file(intro)
                await state.play_file(wav)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        db.log_transcript("remote", f"[{person}] {text}", state.run_id)
        return {"ok": True}

    @app.post("/api/voice")
    async def voice(file: UploadFile, person: str = Depends(auth.require_person)) -> dict:
        """Play an uploaded voice message (the person's real voice) on the robot."""
        limiter.check("voice", person, 5.0)
        data = await file.read()
        suffix = Path(file.filename or "msg.webm").suffix or ".webm"
        try:
            wav = speech.voice_message_to_wav(data, suffix, person)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except RuntimeError as e:
            raise HTTPException(status_code=422, detail=f"format audio non reconnu ({e})") from e
        try:
            intro = await speech.tts_to_wav(f"Message de {person}.")
            await state.play_file(intro)
            await state.play_file(wav)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        db.log_transcript("remote", f"[{person}] (message vocal)", state.run_id)
        return {"ok": True}

    @app.post("/api/view/start")
    async def view_start(person: str = Depends(auth.require_person)) -> dict:
        """Courtesy: announce that someone is watching (max once a minute)."""
        try:
            limiter.check("view-announce", person, 60.0)
        except HTTPException:
            return {"ok": True, "announced": False}
        try:
            wav = await speech.tts_to_wav(f"{person.capitalize()} nous regarde par mes yeux.")
            await state.play_file(wav)
        except RuntimeError:
            return {"ok": True, "announced": False}
        return {"ok": True, "announced": True}

    @app.get("/api/snapshot")
    def snapshot(person: str = Depends(auth.require_person)) -> Response:
        limiter.check("snapshot", person, 1.0)
        try:
            jpeg = state.snapshot_jpeg()
        except Exception as e:
            logger.warning("snapshot failed: %s", e)
            jpeg = None
        if not jpeg:
            raise HTTPException(status_code=503, detail="caméra indisponible")
        return Response(content=jpeg, media_type="image/jpeg")

    @app.get("/api/status")
    def status(person: str = Depends(auth.require_person)) -> dict:
        return {
            "session": state.session_connected(),
            "robot": state.robot() is not None,
            "run_id": state.run_id,
        }

    @app.get("/api/phrases")
    def phrases(person: str = Depends(auth.require_person)) -> JSONResponse:
        return JSONResponse(load_phrases())

    # ── dashboard data (JSON, for future clients) ───────────────────────

    @app.get("/api/care/summary")
    def care_summary(days: int = 14, person: str = Depends(auth.require_person)) -> dict:
        days = max(1, min(days, 90))
        return {
            "daily": db.daily_counts(days),
            "moods": db.mood_entries(days),
            "repeated": db.repeated_utterances(30),
            "last_events": db.last_events(8),
        }

    return app
