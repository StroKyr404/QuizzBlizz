import os
import io
import base64
import uuid
import asyncio
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import qrcode

from .storage import (
    list_quizzes, get_quiz, save_quiz, delete_quiz,
    generate_excel_template, import_from_excel, ensure_quizzes_dir
)
from .game_manager import game_manager
from .tunnel import tunnel_manager

app = FastAPI(title="QuizBlizz - Das interaktive Schul-Quiz")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

ensure_quizzes_dir()

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

# --- Page Routes ---

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    join_url = tunnel_manager.get_join_url()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "join_url": join_url
    })

@app.get("/host", response_class=HTMLResponse)
async def host_page(request: Request, pin: Optional[str] = None):
    join_url = tunnel_manager.get_join_url()
    quizzes = list_quizzes()
    return templates.TemplateResponse("host.html", {
        "request": request,
        "quizzes": quizzes,
        "pin": pin,
        "join_url": join_url
    })

@app.get("/play", response_class=HTMLResponse)
async def play_page(request: Request, pin: Optional[str] = ""):
    return templates.TemplateResponse("play.html", {
        "request": request,
        "prefilled_pin": pin
    })

@app.get("/editor", response_class=HTMLResponse)
async def editor_page(request: Request, id: Optional[str] = None):
    quizzes = list_quizzes()
    active_quiz = get_quiz(id) if id else (get_quiz(quizzes[0]["id"]) if quizzes else None)
    return templates.TemplateResponse("editor.html", {
        "request": request,
        "quizzes": quizzes,
        "active_quiz": active_quiz
    })

# --- API Endpoints ---

@app.get("/api/network/info")
async def network_info():
    base_url = tunnel_manager.get_join_url()
    return {
        "join_url": f"{base_url}/play",
        "base_url": base_url,
        "is_public_tunnel": bool(tunnel_manager.public_url),
        "local_ip": tunnel_manager.local_ip,
        "qr_code": make_qr_code_data_url(f"{base_url}/play")
    }

@app.post("/api/room/create")
async def create_room(payload: dict):
    quiz_id = payload.get("quiz_id")
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz nicht gefunden")

    room = game_manager.create_room(quiz)
    base_url = tunnel_manager.get_join_url()
    join_url = f"{base_url}/play?pin={room.pin}"
    qr_data = make_qr_code_data_url(join_url)

    return {
        "pin": room.pin,
        "quiz_title": quiz.get("title"),
        "questions_count": len(quiz.get("questions", [])),
        "join_url": join_url,
        "qr_code": qr_data
    }

@app.get("/api/quizzes")
async def get_all_quizzes():
    return list_quizzes()

@app.get("/api/quizzes/{quiz_id}")
async def get_single_quiz(quiz_id: str):
    q = get_quiz(quiz_id)
    if not q:
        raise HTTPException(status_code=404, detail="Quiz nicht gefunden")
    return q

@app.post("/api/quizzes")
async def create_or_update_quiz(quiz_data: dict):
    saved_id = save_quiz(quiz_data)
    return {"status": "ok", "id": saved_id}

@app.delete("/api/quizzes/{quiz_id}")
async def remove_quiz(quiz_id: str):
    success = delete_quiz(quiz_id)
    return {"success": success}

@app.get("/api/template/excel")
async def download_excel_template():
    data = generate_excel_template()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=quiz_vorlage.xlsx"}
    )

@app.post("/api/quizzes/import")
async def upload_excel_quiz(file: UploadFile = File(...), title: str = Form("Importiertes Quiz")):
    content = await file.read()
    try:
        quiz = import_from_excel(content, title=title)
        return {"status": "ok", "quiz": quiz}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Importieren: {str(e)}")

# --- WebSockets ---

@app.websocket("/ws/host/{pin}")
async def websocket_host(websocket: WebSocket, pin: str):
    await websocket.accept()
    room = game_manager.get_room(pin)
    if not room:
        await websocket.send_json({"type": "ERROR", "message": "Spielraum existiert nicht."})
        await websocket.close()
        return

    room.host_ws = websocket
    print(f"🖥️ Host für Raum {pin} verbunden")

    try:
        # Send current room state on connect
        await websocket.send_json({
            "type": "ROOM_STATUS",
            "pin": pin,
            "state": room.state,
            "players": [p.to_dict() for p in room.players.values()],
            "players_count": len(room.players),
            "quiz_title": room.quiz.get("title", ""),
            "total_questions": len(room.quiz.get("questions", []))
        })

        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "START_GAME":
                await room.start_game()
            elif action == "NEXT_STEP":
                if room.state == "QUESTION":
                    if room.timer_task and not room.timer_task.done():
                        room.timer_task.cancel()
                    await room.end_question_and_reveal()
                elif room.state == "REVEAL":
                    await room.show_leaderboard()
                elif room.state == "LEADERBOARD":
                    await room.next_question_or_podium()
                elif room.state == "PODIUM":
                    await room.finish_game()
            elif action == "KICK_PLAYER":
                p_id = data.get("player_id")
                if p_id:
                    await room.kick_player(p_id)

    except WebSocketDisconnect:
        print(f"Host für Raum {pin} getrennt")
    except Exception as e:
        print(f"Fehler im Host-WebSocket: {e}")

@app.websocket("/ws/player/{pin}")
async def websocket_player(websocket: WebSocket, pin: str):
    await websocket.accept()
    room = game_manager.get_room(pin)
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
        # First message must be JOIN
        first_msg = await websocket.receive_json()
        if first_msg.get("type") != "JOIN":
            await websocket.close()
            return

        name = str(first_msg.get("name", "")).strip()[:20]
        if not name:
            name = f"Spieler-{random.randint(10, 99)}"

        success = await room.add_player(player_id, name, websocket)
        if not success:
            await websocket.send_json({"type": "ERROR", "message": "Dieser Name ist bereits vergeben!"})
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

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ANSWER":
                ans_idx = data.get("answer_index")
                if ans_idx is not None:
                    await room.submit_answer(player_id, int(ans_idx))

    except WebSocketDisconnect:
        if joined_name:
            print(f"Schüler '{joined_name}' hat Verbindung getrennt")
            await room.remove_player(player_id)
    except Exception as e:
        print(f"Fehler im Player-WebSocket: {e}")
        if joined_name:
            await room.remove_player(player_id)
