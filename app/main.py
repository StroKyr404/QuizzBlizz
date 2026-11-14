import asyncio
import base64
from collections import deque
import io
import json
import os
import random
import secrets
import time
import uuid
from typing import Any, Dict, List, Optional

import qrcode
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator, model_validator

from .game_manager import game_manager
from .network import network_manager
from .security import (
    ADMIN_PASSWORD,
    AUTH_MODE_PASSWORD,
    GENERATED_ADMIN_PASSWORD,
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    create_csrf_form_token,
    create_session_token,
    get_rate_limit_key,
    is_loopback_client,
    is_teacher_authorized_http,
    is_teacher_authorized_ws,
    is_valid_host_header,
    rate_limiter,
    require_teacher_api,
    sanitize_player_name,
    verify_admin_password,
    verify_csrf_form_token,
    verify_same_origin,
)
from .storage import (
    delete_quiz,
    ensure_quizzes_dir,
    generate_excel_template,
    get_quiz,
    get_quiz_for_client,
    import_from_excel,
    list_quizzes,
    save_quiz,
    validate_quiz_id,
)

MAX_EXCEL_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_HOST_WS_BYTES = 8192
MAX_PLAYER_WS_BYTES = 2048

app = FastAPI(title="QuizBlizz - Das interaktive Schul-Quiz")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

ensure_quizzes_dir()

if GENERATED_ADMIN_PASSWORD:
    print("\n" + "!" * 65)
    print("🔐 HINWEIS (Cloud-Modus ohne QUIZBLIZZ_ADMIN_PASSWORD):")
    print(f"   Temporäres Lehrer-Passwort: {ADMIN_PASSWORD}")
    print("   Empfehlung: Setze QUIZBLIZZ_ADMIN_PASSWORD als Umgebungsvariable.")
    print("!" * 65 + "\n")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


# --- Pydantic Schemas ---

class QuestionPayload(BaseModel):
    id: Optional[int] = None
    question: str = Field(..., min_length=1, max_length=500)
    time_limit: int = Field(default=20, ge=5, le=120)
    points: int = Field(default=1000, ge=100, le=5000)
    options: List[str] = Field(..., min_length=2, max_length=4)
    correct_index: int = Field(default=0, ge=0, le=3)

    @field_validator("question")
    @classmethod
    def strip_question(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Fragetext darf nicht leer sein.")
        return cleaned

    @field_validator("options")
    @classmethod
    def clean_options(cls, v: List[str]) -> List[str]:
        cleaned = [str(opt).strip()[:200] for opt in v]
        if len([o for o in cleaned if o]) < 2:
            raise ValueError("Mindestens zwei nicht-leere Antwortoptionen erforderlich.")
        return cleaned

    @model_validator(mode="after")
    def validate_correct_index(self) -> "QuestionPayload":
        if self.correct_index >= len(self.options):
            raise ValueError("correct_index außerhalb der gültigen Optionen.")
        if not self.options[self.correct_index]:
            raise ValueError("Die markierte richtige Antwort darf nicht leer sein.")
        return self


class QuizPayload(BaseModel):
    id: Optional[str] = Field(default=None, max_length=64)
    title: str = Field(..., min_length=1, max_length=150)
    description: str = Field(default="", max_length=500)
    created_at: Optional[str] = Field(default=None, max_length=32)
    password_enabled: bool = False
    password: str = Field(default="", max_length=64)
    questions: List[QuestionPayload] = Field(..., min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Quiz-Titel darf nicht leer sein.")
        return cleaned


class CreateRoomPayload(BaseModel):
    quiz_id: str = Field(..., min_length=1, max_length=64)


# --- Helpers ---

def make_qr_code_data_url(text: str) -> str:
    qr = qrcode.QRCode(
        version=1,
        box_size=8,
        border=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#31105e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def _safe_next_url(next_url: Optional[str]) -> str:
    if not next_url:
        return "/host"
    candidate = next_url.strip()
    if candidate.startswith("/") and not candidate.startswith("//") and "\\" not in candidate:
        allowed_prefixes = ("/", "/host", "/editor")
        if any(candidate == p or candidate.startswith(f"{p}?") for p in allowed_prefixes):
            return candidate
    return "/host"


def _teacher_page_guard(request: Request, target_path: str) -> Optional[Response]:
    if is_teacher_authorized_http(request):
        return None
    if AUTH_MODE_PASSWORD:
        return RedirectResponse(url=f"/login?next={target_path}", status_code=303)
    return HTMLResponse(
        content=(
            "<!DOCTYPE html><html lang='de'><head><meta charset='UTF-8'><title>Zugriff verweigert</title></head>"
            "<body style='font-family:sans-serif;background:#1a0635;color:#fff;padding:3rem;text-align:center;'>"
            "<h1>🔒 Nur für die Lehrperson</h1>"
            "<p>Der Beamer- und Editor-Bereich ist im lokalen Schulnetz nur direkt auf dem Lehrer-Mac (localhost) freigeschaltet.</p>"
            "<p><a href='/play' style='color:#fbbf24;font-weight:bold;'>Zum Schüler-Beitritt &rarr;</a></p>"
            "</body></html>"
        ),
        status_code=403,
    )


# --- Page Routes ---

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    # Schüler im Schul-WLAN direkt auf den Buzzer weiterleiten, wenn lokaler Modus aktiv ist
    if not AUTH_MODE_PASSWORD and not is_loopback_client(request):
        return RedirectResponse(url="/play", status_code=303)

    join_url = network_manager.get_join_url() if is_teacher_authorized_http(request) else ""
    return templates.TemplateResponse(request=request, name="index.html", context={
        "join_url": join_url
    })


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: Optional[str] = "/host"):
    if not AUTH_MODE_PASSWORD and is_loopback_client(request):
        return RedirectResponse(url=_safe_next_url(next), status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={
        "csrf_token": create_csrf_form_token(),
        "next_url": _safe_next_url(next),
        "error": None
    })


@app.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    password: str = Form(""),
    csrf_token: str = Form(""),
    next: str = Form("/host")
):
    safe_next = _safe_next_url(next)
    if not verify_same_origin(request.headers) or not verify_csrf_form_token(csrf_token):
        return templates.TemplateResponse(request=request, name="login.html", context={
            "csrf_token": create_csrf_form_token(),
            "next_url": safe_next,
            "error": "Sitzung abgelaufen. Bitte erneut versuchen."
        }, status_code=403)

    client_key = get_rate_limit_key(request)
    if not rate_limiter.check("admin_login", client_key, limit=10, window_seconds=60):
        return templates.TemplateResponse(request=request, name="login.html", context={
            "csrf_token": create_csrf_form_token(),
            "next_url": safe_next,
            "error": "Zu viele Anmeldeversuche. Bitte 1 Minute warten."
        }, status_code=429)

    if not verify_admin_password(password):
        return templates.TemplateResponse(request=request, name="login.html", context={
            "csrf_token": create_csrf_form_token(),
            "next_url": safe_next,
            "error": "Falsches Passwort."
        }, status_code=401)

    token = create_session_token()
    resp = RedirectResponse(url=safe_next, status_code=303)
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=is_https,
    )
    return resp


@app.post("/logout")
async def logout_submit(request: Request):
    require_teacher_api(request, mutate=True)
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp


@app.get("/host", response_class=HTMLResponse)
async def host_page(request: Request, pin: Optional[str] = None):
    guard = _teacher_page_guard(request, "/host")
    if guard:
        return guard

    join_url = network_manager.get_join_url()
    quizzes = list_quizzes()
    return templates.TemplateResponse(request=request, name="host.html", context={
        "quizzes": quizzes,
        "pin": pin,
        "join_url": join_url
    })


@app.get("/play", response_class=HTMLResponse)
async def play_page(request: Request, pin: Optional[str] = ""):
    safe_pin = pin if (pin and pin.isdigit() and len(pin) == 6) else ""
    return templates.TemplateResponse(request=request, name="play.html", context={
        "prefilled_pin": safe_pin
    })


@app.get("/editor", response_class=HTMLResponse)
async def editor_page(request: Request, id: Optional[str] = None):
    guard = _teacher_page_guard(request, "/editor")
    if guard:
        return guard

    quizzes = list_quizzes()
    if id:
        active_quiz = get_quiz_for_client(id)
    else:
        active_quiz = get_quiz_for_client(quizzes[0]["id"]) if quizzes else None
    return templates.TemplateResponse(request=request, name="editor.html", context={
        "quizzes": quizzes,
        "active_quiz": active_quiz
    })


# --- API Endpoints ---

@app.get("/api/network/info")
async def network_info(request: Request):
    require_teacher_api(request, mutate=False)
    base_url = network_manager.get_join_url()
    return {
        "join_url": f"{base_url}/play",
        "base_url": base_url,
        "local_ip": network_manager.local_ip,
        "qr_code": make_qr_code_data_url(f"{base_url}/play")
    }


@app.post("/api/room/create")
async def create_room(request: Request, payload: CreateRoomPayload):
    require_teacher_api(request, mutate=True)

    quiz_id = validate_quiz_id(payload.quiz_id)
    if not quiz_id:
        raise HTTPException(status_code=400, detail="Ungültige Quiz-ID")

    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz nicht gefunden")

    room = game_manager.create_room(quiz)

    # Im Cloud-Betrieb die öffentliche Request-Domain nutzen (Host-Header validiert), lokal die Schul-WLAN-IP
    forwarded_host = request.headers.get("host", "")
    if AUTH_MODE_PASSWORD and is_valid_host_header(forwarded_host) and not is_loopback_client(request):
        scheme = "https" if (request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https") else "http"
        join_url = f"{scheme}://{forwarded_host}/play?pin={room.pin}"
    else:
        join_url = f"http://{network_manager.local_ip}:{network_manager.port}/play?pin={room.pin}"

    qr_data = make_qr_code_data_url(join_url)

    return {
        "pin": room.pin,
        "host_token": room.host_token,
        "quiz_title": quiz.get("title"),
        "questions_count": len(quiz.get("questions", [])),
        "join_url": join_url,
        "qr_code": qr_data,
        "password_required": room.password_required
    }


@app.get("/api/room/{pin}/info")
async def get_room_info(request: Request, pin: str):
    client_key = get_rate_limit_key(request)
    if not rate_limiter.check("room_info", client_key, limit=25, window_seconds=60):
        raise HTTPException(status_code=429, detail="Zu viele Anfragen. Bitte kurz warten.")

    if not pin.isdigit() or len(pin) != 6:
        raise HTTPException(status_code=404, detail="Raum nicht gefunden")

    room = game_manager.get_room(pin)
    if not room:
        raise HTTPException(status_code=404, detail="Raum nicht gefunden")

    return {
        "pin": room.pin,
        "state": room.state,
        "is_locked": room.is_locked,
        "password_required": room.password_required,
        "quiz_title": room.quiz.get("title", "")
    }


@app.get("/api/quizzes")
async def get_all_quizzes(request: Request):
    require_teacher_api(request, mutate=False)
    return list_quizzes()


@app.get("/api/quizzes/{quiz_id}")
async def get_single_quiz(request: Request, quiz_id: str):
    require_teacher_api(request, mutate=False)
    if not validate_quiz_id(quiz_id):
        raise HTTPException(status_code=400, detail="Ungültige Quiz-ID")
    q = get_quiz_for_client(quiz_id)
    if not q:
        raise HTTPException(status_code=404, detail="Quiz nicht gefunden")
    return q


@app.post("/api/quizzes")
async def create_or_update_quiz(request: Request, quiz_data: QuizPayload):
    require_teacher_api(request, mutate=True)
    saved_id = save_quiz(quiz_data.model_dump())
    return {"status": "ok", "id": saved_id}


@app.delete("/api/quizzes/{quiz_id}")
async def remove_quiz(request: Request, quiz_id: str):
    require_teacher_api(request, mutate=True)
    if not validate_quiz_id(quiz_id):
        raise HTTPException(status_code=400, detail="Ungültige Quiz-ID")
    success = delete_quiz(quiz_id)
    return {"success": success}


@app.get("/api/template/excel")
async def download_excel_template(request: Request):
    require_teacher_api(request, mutate=False)
    data = generate_excel_template()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=quiz_vorlage.xlsx"}
    )


@app.post("/api/quizzes/import")
async def upload_excel_quiz(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form("Importiertes Quiz")
):
    require_teacher_api(request, mutate=True)

    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Nur .xlsx-Excel-Dateien werden unterstützt.")

    chunks: List[bytes] = []
    total_bytes = 0
    while True:
        chunk = await file.read(65536)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > MAX_EXCEL_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Datei ist zu groß (maximal 2 MB erlaubt).")
        chunks.append(chunk)

    content = b"".join(chunks)
    if not content:
        raise HTTPException(status_code=400, detail="Die hochgeladene Datei ist leer.")

    try:
        quiz = import_from_excel(content, title=title)
        return {"status": "ok", "quiz": quiz}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültige oder beschädigte Excel-Datei.")


# --- WebSockets ---

class _WebSocketFrameTooLarge(Exception):
    pass


async def _receive_limited_json(
    websocket: WebSocket,
    max_bytes: int,
    timeout: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Liest ein WebSocket-Frame mit Größenlimit und parst es sicher als JSON-Objekt."""
    coro = websocket.receive()
    msg = await asyncio.wait_for(coro, timeout=timeout) if timeout is not None else await coro
    if msg.get("type") == "websocket.disconnect":
        raise WebSocketDisconnect(code=msg.get("code", 1000))
    raw_bytes = msg.get("bytes")
    if raw_bytes is not None:
        if len(raw_bytes) > max_bytes:
            raise _WebSocketFrameTooLarge()
        return None
    raw_text = msg.get("text")
    if not isinstance(raw_text, str):
        return None
    if len(raw_text) > max_bytes or len(raw_text.encode("utf-8", errors="ignore")) > max_bytes:
        raise _WebSocketFrameTooLarge()
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


@app.websocket("/ws/host/{pin}")
async def websocket_host(
    websocket: WebSocket,
    pin: str,
    token: Optional[str] = Query(default=None)
):
    if not verify_same_origin(websocket.headers) or not is_teacher_authorized_ws(websocket):
        await websocket.close(code=1008)
        return

    room = game_manager.get_room(pin)
    if not room or not token or not secrets.compare_digest(token, room.host_token):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    room.host_ws = websocket
    room.host_disconnected_at = None
    room.touch()
    print(f"🖥️ Host für Raum {pin} verbunden")

    try:
        await websocket.send_json({
            "type": "ROOM_STATUS",
            "pin": pin,
            "state": room.state,
            "is_locked": room.is_locked,
            "password_required": room.password_required,
            "players": [p.to_dict() for p in room.players.values()],
            "players_count": len(room.players),
            "quiz_title": room.quiz.get("title", ""),
            "total_questions": len(room.quiz.get("questions", []))
        })

        while True:
            data = await _receive_limited_json(websocket, MAX_HOST_WS_BYTES)
            if data is None:
                continue
            action = data.get("action")

            if action == "TOGGLE_LOCK":
                await room.toggle_lock()
            elif action == "START_GAME":
                await room.start_game()
            elif action == "NEXT_STEP":
                if room.state == "QUESTION":
                    await room.end_question_and_reveal()
                elif room.state == "REVEAL":
                    await room.show_leaderboard()
                elif room.state == "LEADERBOARD":
                    await room.next_question_or_podium()
                elif room.state == "PODIUM":
                    await room.finish_game()
            elif action == "KICK_PLAYER":
                p_id = data.get("player_id")
                if isinstance(p_id, str) and p_id:
                    await room.kick_player(p_id)

    except _WebSocketFrameTooLarge:
        await websocket.close(code=1009)
    except WebSocketDisconnect:
        print(f"Host für Raum {pin} getrennt")
    except Exception as e:
        print(f"Fehler im Host-WebSocket: {e}")
    finally:
        if room.host_ws is websocket:
            room.host_ws = None
            room.host_disconnected_at = time.monotonic()


@app.websocket("/ws/player/{pin}")
async def websocket_player(websocket: WebSocket, pin: str):
    client_key = get_rate_limit_key(websocket)
    if not verify_same_origin(websocket.headers):
        await websocket.close(code=1008)
        return

    if not rate_limiter.check("ws_player_join", client_key, limit=30, window_seconds=60):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    room = game_manager.get_room(pin) if (pin.isdigit() and len(pin) == 6) else None
    if not room:
        await websocket.send_json({"type": "ERROR", "message": "PIN ungültig oder Spiel nicht aktiv."})
        await websocket.close()
        return

    if room.state != "LOBBY":
        await websocket.send_json({"type": "ERROR", "message": "Das Spiel hat bereits begonnen."})
        await websocket.close()
        return

    player_id = str(uuid.uuid4())
    joined_name = ""

    try:
        first_msg = await _receive_limited_json(websocket, MAX_PLAYER_WS_BYTES, timeout=5.0)
        if not first_msg or first_msg.get("type") != "JOIN":
            await websocket.close(code=1008)
            return

        pwd_bucket_key = f"{pin}:{client_key}"
        if room.password_required and rate_limiter.is_limited("wrong_quiz_pwd", pwd_bucket_key, limit=5, window_seconds=60):
            await websocket.send_json({
                "type": "ERROR",
                "code": "RATE_LIMIT",
                "message": "Zu viele falsche Passwortversuche. Bitte 1 Minute warten."
            })
            await websocket.close(code=1008)
            return

        name = sanitize_player_name(first_msg.get("name", ""), max_len=20)
        if not name:
            name = f"Spieler-{random.randint(10, 99)}"

        password = str(first_msg.get("password", "")).strip()[:64]
        success, code, err_msg = await room.add_player(player_id, name, websocket, password)
        if not success:
            if code == "WRONG_PASSWORD":
                rate_limiter.check("wrong_quiz_pwd", pwd_bucket_key, limit=5, window_seconds=60)
            await websocket.send_json({"type": "ERROR", "code": code, "message": err_msg})
            await websocket.close()
            return

        joined_name = name
        print(f"📱 Schüler '{name}' Raum {pin} beigetreten.")

        await websocket.send_json({
            "type": "JOINED_SUCCESS",
            "player_id": player_id,
            "name": name,
            "quiz_title": room.quiz.get("title", "")
        })

        msg_timestamps: deque = deque()
        while True:
            data = await _receive_limited_json(websocket, MAX_PLAYER_WS_BYTES)
            now = time.monotonic()
            while msg_timestamps and now - msg_timestamps[0] > 5.0:
                msg_timestamps.popleft()
            if len(msg_timestamps) >= 12:
                await websocket.close(code=1008)
                break
            msg_timestamps.append(now)

            if data is None:
                continue
            msg_type = data.get("type")

            if msg_type == "ANSWER":
                ans_idx = data.get("answer_index")
                if ans_idx is not None and not isinstance(ans_idx, bool):
                    try:
                        parsed_idx = int(ans_idx)
                    except (ValueError, TypeError):
                        continue
                    await room.submit_answer(player_id, parsed_idx)

    except asyncio.TimeoutError:
        await websocket.close(code=1008)
    except _WebSocketFrameTooLarge:
        await websocket.close(code=1009)
    except WebSocketDisconnect:
        if joined_name:
            print(f"Schüler '{joined_name}' hat Verbindung getrennt")
    except Exception as e:
        print(f"Fehler im Player-WebSocket: {e}")
    finally:
        if joined_name:
            await room.remove_player(player_id)
