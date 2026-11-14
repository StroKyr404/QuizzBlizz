import asyncio
import random
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from .security import verify_quiz_password

MAX_PLAYERS_PER_ROOM = 300
MAX_ACTIVE_ROOMS = 50
ROOM_IDLE_TTL_SECONDS = 4 * 3600
FINISHED_ROOM_TTL_SECONDS = 10 * 60
ORPHANED_HOST_TTL_SECONDS = 15 * 60


class Player:
    def __init__(self, player_id: str, name: str, ws: Optional[WebSocket] = None):
        self.id = player_id
        self.name = name
        self.ws = ws
        self.score = 0
        self.streak = 0
        self.last_answer = None  # { "index": int, "time_ms": float, "correct": bool, "points": int }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "score": self.score,
            "streak": self.streak,
            "has_answered": self.last_answer is not None
        }


class GameRoom:
    def __init__(self, pin: str, quiz: Dict[str, Any], host_ws: Optional[WebSocket] = None):
        self.pin = pin
        self.quiz = quiz
        self.host_token = secrets.token_urlsafe(24)
        self.host_ws = host_ws
        self.players: Dict[str, Player] = {}
        self.state = "LOBBY"  # LOBBY, GET_READY, QUESTION, REVEAL, LEADERBOARD, PODIUM, FINISHED
        self.current_q_index = -1
        self.q_start_time = 0.0
        self.timer_task: Optional[asyncio.Task] = None
        self.answers_for_current_q: Dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
        self.is_locked = False

        self.password_enabled = bool(self.quiz.get("password_enabled"))
        self.password_hash = str(self.quiz.get("password_hash", "") or "").strip()
        self.legacy_password = str(self.quiz.get("password", "") or "").strip()
        self.password_required = bool(self.password_enabled and (self.password_hash or self.legacy_password))

        now = time.monotonic()
        self.created_at = now
        self.last_activity = now
        self.finished_at: Optional[float] = None
        self.host_disconnected_at: Optional[float] = None
        self._lock = asyncio.Lock()

    def touch(self) -> None:
        self.last_activity = time.monotonic()

    @property
    def current_question(self) -> Optional[Dict[str, Any]]:
        questions = self.quiz.get("questions", [])
        if 0 <= self.current_q_index < len(questions):
            return questions[self.current_q_index]
        return None

    async def toggle_lock(self) -> bool:
        async with self._lock:
            self.touch()
            self.is_locked = not self.is_locked
            await self.send_to_host({
                "type": "ROOM_LOCK_STATUS",
                "is_locked": self.is_locked
            })
            return self.is_locked

    async def _send_player_list_to_host(self, event_type: str, extra: Optional[Dict[str, Any]] = None) -> None:
        payload: Dict[str, Any] = {
            "type": event_type,
            "players_count": len(self.players),
            "players": [p.to_dict() for p in self.players.values()]
        }
        if extra:
            payload.update(extra)
        await self.send_to_host(payload)

    async def _safe_send_json(
        self,
        ws: Optional[WebSocket],
        data: Dict[str, Any],
        timeout: float = 2.0,
    ) -> bool:
        if ws is None:
            return False
        try:
            await asyncio.wait_for(ws.send_json(data), timeout=timeout)
            return True
        except Exception:
            return False

    async def broadcast_to_players(self, data: Dict[str, Any]):
        targets = [
            (p_id, p.name, p.ws)
            for p_id, p in list(self.players.items())
            if p.ws is not None
        ]
        if not targets:
            return

        results = await asyncio.gather(
            *(self._safe_send_json(ws, data) for _, _, ws in targets)
        )
        disconnected = [
            (p_id, p_name)
            for (p_id, p_name, _), ok in zip(targets, results)
            if not ok
        ]
        for p_id, p_name in disconnected:
            if p_id in self.players:
                del self.players[p_id]
                await self._send_player_list_to_host("PLAYER_LEFT", {
                    "player_id": p_id,
                    "name": p_name
                })

    async def send_to_host(self, data: Dict[str, Any]):
        await self._safe_send_json(self.host_ws, data)

    async def broadcast_all(self, data: Dict[str, Any]):
        await self.send_to_host(data)
        await self.broadcast_to_players(data)

    async def add_player(
        self,
        player_id: str,
        name: str,
        ws: WebSocket,
        provided_password: Optional[str] = None
    ) -> tuple:
        async with self._lock:
            self.touch()
            if self.state != "LOBBY":
                return False, "GAME_STARTED", "Das Spiel hat bereits begonnen."

            if self.is_locked:
                return False, "LOCKED", "Die Lobby wurde von der Lehrperson gesperrt. Kein Beitritt möglich."

            if len(self.players) >= MAX_PLAYERS_PER_ROOM:
                return False, "ROOM_FULL", "Die maximale Teilnehmerzahl wurde erreicht."

            if self.password_required:
                if not verify_quiz_password(provided_password, self.password_hash, self.legacy_password):
                    return False, "WRONG_PASSWORD", "Falsches Quiz-Passwort! Bitte frage deine Lehrperson."

            for p in self.players.values():
                if p.name.lower() == name.lower():
                    return False, "DUPLICATE_NAME", "Dieser Name ist bereits vergeben!"

            player = Player(player_id, name, ws)
            self.players[player_id] = player

            await self._send_player_list_to_host("PLAYER_JOINED", {
                "player": player.to_dict()
            })
            return True, "OK", ""

    async def remove_player(self, player_id: str):
        async with self._lock:
            if player_id in self.players:
                p = self.players.pop(player_id)
                self.touch()
                await self._send_player_list_to_host("PLAYER_LEFT", {
                    "player_id": player_id,
                    "name": p.name
                })

    async def kick_player(self, player_id: str):
        ws_to_close = None
        async with self._lock:
            if player_id in self.players:
                p = self.players.pop(player_id)
                self.touch()
                ws_to_close = p.ws
                await self._send_player_list_to_host("PLAYER_LEFT", {
                    "player_id": player_id,
                    "name": p.name
                })
        if ws_to_close:
            await self._safe_send_json(ws_to_close, {
                "type": "KICKED",
                "message": "Du wurdest von der Lehrperson entfernt."
            })
            try:
                await asyncio.wait_for(ws_to_close.close(), timeout=2.0)
            except Exception:
                pass

    async def start_game(self):
        async with self._lock:
            if self.state != "LOBBY":
                return
            self.touch()
            self.current_q_index = 0
            await self._start_get_ready_locked()

    async def _start_get_ready_locked(self):
        self.state = "GET_READY"
        q = self.current_question
        if not q:
            await self._finish_game_locked()
            return

        self.answers_for_current_q = {0: 0, 1: 0, 2: 0, 3: 0}
        for p in self.players.values():
            p.last_answer = None

        total_q = len(self.quiz.get("questions", []))
        get_ready_msg = {
            "type": "GET_READY",
            "question_number": self.current_q_index + 1,
            "total_questions": total_q,
            "question_text": q.get("question", ""),
            "countdown": 3
        }
        await self.broadcast_all(get_ready_msg)

        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()

        async def get_ready_timer():
            try:
                await asyncio.sleep(3)
                await self.start_question()
            except asyncio.CancelledError:
                pass

        self.timer_task = asyncio.create_task(get_ready_timer())

    async def start_question(self):
        async with self._lock:
            if self.state != "GET_READY":
                return
            self.touch()
            self.state = "QUESTION"
            q = self.current_question
            if not q:
                await self._finish_game_locked()
                return

            time_limit = q.get("time_limit", 20)
            self.q_start_time = time.monotonic()

            options = q.get("options", [])
            await self.send_to_host({
                "type": "QUESTION_START",
                "question_number": self.current_q_index + 1,
                "total_questions": len(self.quiz.get("questions", [])),
                "question": q.get("question", ""),
                "options": options,
                "time_limit": time_limit,
                "answered_count": 0,
                "total_players": len(self.players)
            })

            await self.broadcast_to_players({
                "type": "QUESTION_START",
                "question_number": self.current_q_index + 1,
                "options_count": len(options),
                "options": options,
                "time_limit": time_limit
            })

            if self.timer_task and not self.timer_task.done():
                self.timer_task.cancel()

            async def countdown():
                try:
                    await asyncio.sleep(time_limit)
                    await self.end_question_and_reveal()
                except asyncio.CancelledError:
                    pass

            self.timer_task = asyncio.create_task(countdown())

    async def submit_answer(self, player_id: str, answer_idx: int):
        async with self._lock:
            if self.state != "QUESTION":
                return
            player = self.players.get(player_id)
            if not player or player.last_answer is not None:
                return

            q = self.current_question
            if not q:
                return

            options = q.get("options", [])
            if not isinstance(answer_idx, int) or isinstance(answer_idx, bool):
                return
            if answer_idx < 0 or answer_idx >= len(options):
                return

            self.touch()
            elapsed = max(0.0, time.monotonic() - self.q_start_time)
            time_limit = max(1, q.get("time_limit", 20))
            is_correct = (answer_idx == q.get("correct_index", 0))

            points_earned = 0
            if is_correct:
                player.streak += 1
                ratio = max(0.0, min(1.0, elapsed / time_limit))
                speed_score = int(round((1.0 - (ratio / 2.0)) * 1000))
                streak_bonus = min(500, (player.streak - 1) * 100) if player.streak > 1 else 0
                points_earned = speed_score + streak_bonus
                player.score += points_earned
            else:
                player.streak = 0

            player.last_answer = {
                "index": answer_idx,
                "time_ms": round(elapsed * 1000),
                "correct": is_correct,
                "points": points_earned
            }

            if 0 <= answer_idx <= 3:
                self.answers_for_current_q[answer_idx] = self.answers_for_current_q.get(answer_idx, 0) + 1

            await self._safe_send_json(player.ws, {
                "type": "ANSWER_RECEIVED",
                "chosen_index": answer_idx
            })

            answered_count = sum(1 for p in self.players.values() if p.last_answer is not None)
            await self.send_to_host({
                "type": "ANSWER_STATS_UPDATE",
                "answered_count": answered_count,
                "total_players": len(self.players)
            })

            if answered_count >= len(self.players) and len(self.players) > 0:
                if self.timer_task and not self.timer_task.done():
                    self.timer_task.cancel()
                await self._end_question_and_reveal_locked()

    async def end_question_and_reveal(self):
        async with self._lock:
            if self.timer_task and not self.timer_task.done():
                current_task = asyncio.current_task()
                if self.timer_task is not current_task:
                    self.timer_task.cancel()
            await self._end_question_and_reveal_locked()

    async def _end_question_and_reveal_locked(self):
        if self.state != "QUESTION":
            return
        self.state = "REVEAL"
        self.touch()
        q = self.current_question
        if not q:
            return

        correct_idx = q.get("correct_index", 0)

        await self.send_to_host({
            "type": "QUESTION_REVEAL",
            "correct_index": correct_idx,
            "stats": self.answers_for_current_q,
            "total_answers": sum(self.answers_for_current_q.values())
        })

        sorted_players = sorted(self.players.values(), key=lambda p: p.score, reverse=True)
        player_ranks = {p.id: idx + 1 for idx, p in enumerate(sorted_players)}

        result_tasks = []
        for p_id, p in list(self.players.items()):
            if p.ws:
                la = p.last_answer
                is_correct = la["correct"] if la else False
                points = la["points"] if la else 0
                chosen = la["index"] if la else None
                result_tasks.append(self._safe_send_json(p.ws, {
                    "type": "QUESTION_RESULT",
                    "is_correct": is_correct,
                    "chosen_index": chosen,
                    "correct_index": correct_idx,
                    "points_earned": points,
                    "total_score": p.score,
                    "streak": p.streak,
                    "rank": player_ranks.get(p_id, 1)
                }))
        if result_tasks:
            await asyncio.gather(*result_tasks)

    async def show_leaderboard(self):
        async with self._lock:
            if self.state != "REVEAL":
                return
            self.state = "LEADERBOARD"
            self.touch()
            sorted_players = sorted(self.players.values(), key=lambda p: p.score, reverse=True)
            top_list = [
                {
                    "rank": idx + 1,
                    "name": p.name,
                    "score": p.score,
                    "streak": p.streak,
                    "last_points": p.last_answer["points"] if p.last_answer else 0
                }
                for idx, p in enumerate(sorted_players[:5])
            ]

            is_last_question = (self.current_q_index >= len(self.quiz.get("questions", [])) - 1)

            await self.send_to_host({
                "type": "LEADERBOARD",
                "leaderboard": top_list,
                "is_last_question": is_last_question
            })

            await self.broadcast_to_players({
                "type": "LEADERBOARD_PHASE",
                "is_last_question": is_last_question
            })

    async def next_question_or_podium(self):
        async with self._lock:
            if self.state != "LEADERBOARD":
                return
            self.touch()
            if self.current_q_index >= len(self.quiz.get("questions", [])) - 1:
                await self._show_podium_locked()
            else:
                self.current_q_index += 1
                await self._start_get_ready_locked()

    async def _show_podium_locked(self):
        self.state = "PODIUM"
        sorted_players = sorted(self.players.values(), key=lambda p: p.score, reverse=True)

        podium = {
            "first": sorted_players[0].to_dict() if len(sorted_players) > 0 else None,
            "second": sorted_players[1].to_dict() if len(sorted_players) > 1 else None,
            "third": sorted_players[2].to_dict() if len(sorted_players) > 2 else None,
            "all": [p.to_dict() for p in sorted_players]
        }

        await self.send_to_host({
            "type": "PODIUM",
            "podium": podium
        })

        podium_tasks = [
            self._safe_send_json(p.ws, {
                "type": "PODIUM_PLAYER",
                "rank": idx + 1,
                "total_score": p.score,
                "is_winner": (idx == 0)
            })
            for idx, p in enumerate(sorted_players)
            if p.ws is not None
        ]
        if podium_tasks:
            await asyncio.gather(*podium_tasks)

    async def finish_game(self):
        async with self._lock:
            await self._finish_game_locked()

    async def _finish_game_locked(self):
        self.state = "FINISHED"
        self.finished_at = time.monotonic()
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        await self.broadcast_all({"type": "GAME_OVER"})

    def cancel_timers(self) -> None:
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()


class GameManager:
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}

    def cleanup_stale_rooms(self) -> int:
        now = time.monotonic()
        to_remove: List[str] = []
        for pin, room in list(self.rooms.items()):
            if room.state == "FINISHED" and room.finished_at and (now - room.finished_at) > FINISHED_ROOM_TTL_SECONDS:
                to_remove.append(pin)
            elif room.host_disconnected_at and (now - room.host_disconnected_at) > ORPHANED_HOST_TTL_SECONDS:
                to_remove.append(pin)
            elif (now - room.last_activity) > ROOM_IDLE_TTL_SECONDS:
                to_remove.append(pin)

        for pin in to_remove:
            self.remove_room(pin)

        # Fallback: falls Limit immer noch überschritten, älteste Räume entfernen
        while len(self.rooms) >= MAX_ACTIVE_ROOMS:
            oldest_pin = min(self.rooms.keys(), key=lambda p: self.rooms[p].last_activity)
            self.remove_room(oldest_pin)

        return len(to_remove)

    def create_room(self, quiz: Dict[str, Any], host_ws: Optional[WebSocket] = None) -> GameRoom:
        self.cleanup_stale_rooms()
        while True:
            pin = f"{secrets.randbelow(900000) + 100000}"
            if pin not in self.rooms:
                break
        room = GameRoom(pin, quiz, host_ws)
        self.rooms[pin] = room
        return room

    def get_room(self, pin: str) -> Optional[GameRoom]:
        return self.rooms.get(str(pin).strip())

    def remove_room(self, pin: str):
        if pin in self.rooms:
            room = self.rooms.pop(pin)
            room.cancel_timers()


game_manager = GameManager()
