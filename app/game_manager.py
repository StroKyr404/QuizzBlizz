import asyncio
import time
import random
from typing import Dict, Any, Optional, List
from fastapi import WebSocket

class Player:
    def __init__(self, player_id: str, name: str, ws: Optional[WebSocket] = None):
        self.id = player_id
        self.name = name
        self.ws = ws
        self.score = 0
        self.streak = 0
        self.last_answer = None  # { "index": int, "time_ms": float, "correct": bool, "points": int }

    def to_dict(self):
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
        self.host_ws = host_ws
        self.players: Dict[str, Player] = {}
        self.state = "LOBBY"  # LOBBY, GET_READY, QUESTION, REVEAL, LEADERBOARD, PODIUM
        self.current_q_index = -1
        self.q_start_time = 0.0
        self.timer_task: Optional[asyncio.Task] = None
        self.answers_for_current_q: Dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}

    @property
    def current_question(self) -> Optional[Dict[str, Any]]:
        questions = self.quiz.get("questions", [])
        if 0 <= self.current_q_index < len(questions):
            return questions[self.current_q_index]
        return None

    async def broadcast_to_players(self, data: Dict[str, Any]):
        disconnected = []
        for p_id, p in self.players.items():
            if p.ws:
                try:
                    await p.ws.send_json(data)
                except Exception:
                    disconnected.append(p_id)
        for p_id in disconnected:
            if p_id in self.players:
                del self.players[p_id]

    async def send_to_host(self, data: Dict[str, Any]):
        if self.host_ws:
            try:
                await self.host_ws.send_json(data)
            except Exception:
                pass

    async def broadcast_all(self, data: Dict[str, Any]):
        await self.send_to_host(data)
        await self.broadcast_to_players(data)

    async def add_player(self, player_id: str, name: str, ws: WebSocket) -> bool:
        # Check duplicate name
        for p in self.players.values():
            if p.name.lower() == name.lower():
                return False
        player = Player(player_id, name, ws)
        self.players[player_id] = player
        
        # Notify host
        await self.send_to_host({
            "type": "PLAYER_JOINED",
            "player": player.to_dict(),
            "players_count": len(self.players),
            "players": [p.to_dict() for p in self.players.values()]
        })
        return True

    async def remove_player(self, player_id: str):
        if player_id in self.players:
            p = self.players.pop(player_id)
            await self.send_to_host({
                "type": "PLAYER_LEFT",
                "player_id": player_id,
                "name": p.name,
                "players_count": len(self.players),
                "players": [pl.to_dict() for pl in self.players.values()]
            })

    async def kick_player(self, player_id: str):
        if player_id in self.players:
            p = self.players[player_id]
            if p.ws:
                try:
                    await p.ws.send_json({"type": "KICKED", "message": "Du wurdest von der Lehrperson entfernt."})
                    await p.ws.close()
                except Exception:
                    pass
            await self.remove_player(player_id)

    async def start_game(self):
        if self.state != "LOBBY":
            return
        self.current_q_index = 0
        await self.start_get_ready()

    async def start_get_ready(self):
        self.state = "GET_READY"
        q = self.current_question
        if not q:
            await self.finish_game()
            return

        # Reset player answers for this round
        self.answers_for_current_q = {0: 0, 1: 0, 2: 0, 3: 0}
        for p in self.players.values():
            p.last_answer = None

        total_q = len(self.quiz.get("questions", []))
        get_ready_msg = {
            "type": "GET_READY",
            "question_number": self.current_q_index + 1,
            "total_questions": total_q,
            "question_text": q["question"],
            "countdown": 3
        }
        await self.broadcast_all(get_ready_msg)

        # 3 seconds countdown
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
        self.state = "QUESTION"
        q = self.current_question
        if not q:
            await self.finish_game()
            return

        time_limit = q.get("time_limit", 20)
        self.q_start_time = time.time()

        # Send full question with options to Host
        await self.send_to_host({
            "type": "QUESTION_START",
            "question_number": self.current_q_index + 1,
            "total_questions": len(self.quiz.get("questions", [])),
            "question": q["question"],
            "options": q["options"],
            "time_limit": time_limit,
            "answered_count": 0,
            "total_players": len(self.players)
        })

        # Send options to Player (Kahoot style: color & shape pads)
        await self.broadcast_to_players({
            "type": "QUESTION_START",
            "question_number": self.current_q_index + 1,
            "options_count": len(q["options"]),
            "options": q["options"],
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
        if self.state != "QUESTION":
            return
        player = self.players.get(player_id)
        if not player or player.last_answer is not None:
            return

        elapsed = time.time() - self.q_start_time
        q = self.current_question
        if not q:
            return

        time_limit = q.get("time_limit", 20)
        is_correct = (answer_idx == q.get("correct_index", 0))

        # Calculate Kahoot points formula:
        # Base 1000 points. Points = round((1 - (elapsed / (time_limit * 2))) * 1000)
        # Streak adds bonus: 100 * (streak), capped at 500
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

        # Track counts for chart
        if 0 <= answer_idx <= 3:
            self.answers_for_current_q[answer_idx] = self.answers_for_current_q.get(answer_idx, 0) + 1

        # Acknowledge to player
        if player.ws:
            try:
                await player.ws.send_json({
                    "type": "ANSWER_RECEIVED",
                    "chosen_index": answer_idx
                })
            except Exception:
                pass

        # Update host with live answer counter
        answered_count = sum(1 for p in self.players.values() if p.last_answer is not None)
        await self.send_to_host({
            "type": "ANSWER_STATS_UPDATE",
            "answered_count": answered_count,
            "total_players": len(self.players)
        })

        # If everyone has answered, reveal immediately!
        if answered_count >= len(self.players) and len(self.players) > 0:
            if self.timer_task and not self.timer_task.done():
                self.timer_task.cancel()
            await self.end_question_and_reveal()

    async def end_question_and_reveal(self):
        self.state = "REVEAL"
        q = self.current_question
        if not q:
            return

        correct_idx = q.get("correct_index", 0)

        # Host reveal message with statistics
        await self.send_to_host({
            "type": "QUESTION_REVEAL",
            "correct_index": correct_idx,
            "stats": self.answers_for_current_q,
            "total_answers": sum(self.answers_for_current_q.values())
        })

        # Calculate ranks
        sorted_players = sorted(self.players.values(), key=lambda p: p.score, reverse=True)
        player_ranks = {p.id: idx + 1 for idx, p in enumerate(sorted_players)}

        # Individual feedback to each player
        for p_id, p in self.players.items():
            if p.ws:
                la = p.last_answer
                is_correct = la["correct"] if la else False
                points = la["points"] if la else 0
                chosen = la["index"] if la else None
                try:
                    await p.ws.send_json({
                        "type": "QUESTION_RESULT",
                        "is_correct": is_correct,
                        "chosen_index": chosen,
                        "correct_index": correct_idx,
                        "points_earned": points,
                        "total_score": p.score,
                        "streak": p.streak,
                        "rank": player_ranks.get(p_id, 1)
                    })
                except Exception:
                    pass

    async def show_leaderboard(self):
        self.state = "LEADERBOARD"
        # Sort top players
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
        if self.current_q_index >= len(self.quiz.get("questions", [])) - 1:
            await self.show_podium()
        else:
            self.current_q_index += 1
            await self.start_get_ready()

    async def show_podium(self):
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

        for idx, p in enumerate(sorted_players):
            if p.ws:
                try:
                    await p.ws.send_json({
                        "type": "PODIUM_PLAYER",
                        "rank": idx + 1,
                        "total_score": p.score,
                        "is_winner": (idx == 0)
                    })
                except Exception:
                    pass

    async def finish_game(self):
        self.state = "FINISHED"
        await self.broadcast_all({"type": "GAME_OVER"})

class GameManager:
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}

    def create_room(self, quiz: Dict[str, Any], host_ws: Optional[WebSocket] = None) -> GameRoom:
        # Generate clean 6-digit pin
        while True:
            pin = f"{random.randint(100000, 999999)}"
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
            if room.timer_task and not room.timer_task.done():
                room.timer_task.cancel()

game_manager = GameManager()
