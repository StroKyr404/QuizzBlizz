import datetime
import io
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

import openpyxl

from .security import hash_quiz_password

QUIZZES_DIR = os.path.realpath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quizzes")
)
_QUIZ_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_IMPORT_QUESTIONS = 200


def validate_quiz_id(quiz_id: Optional[str]) -> Optional[str]:
    if not isinstance(quiz_id, str):
        return None
    cleaned = quiz_id.strip()
    if not _QUIZ_ID_RE.match(cleaned):
        return None
    return cleaned


def _safe_quiz_filepath(quiz_id: Optional[str]) -> Optional[str]:
    valid_id = validate_quiz_id(quiz_id)
    if not valid_id:
        return None
    target = os.path.realpath(os.path.join(QUIZZES_DIR, f"{valid_id}.json"))
    if not target.startswith(QUIZZES_DIR + os.sep):
        return None
    return target


def _has_stored_password(data: Dict[str, Any]) -> bool:
    return bool(
        data.get("password_enabled", False)
        and (str(data.get("password_hash", "")).strip() or str(data.get("password", "")).strip())
    )


def sanitize_quiz_for_client(data: Dict[str, Any]) -> Dict[str, Any]:
    """Entfernt Passwort-Daten aus dem Quiz-Objekt bevor es an den Browser gesendet wird."""
    clean = dict(data)
    has_pwd = _has_stored_password(clean)
    clean.pop("password", None)
    clean.pop("password_hash", None)
    clean["password_enabled"] = has_pwd
    clean["has_password"] = has_pwd
    return clean


def ensure_quizzes_dir():
    os.makedirs(QUIZZES_DIR, exist_ok=True)
    files = [f for f in os.listdir(QUIZZES_DIR) if f.endswith(".json")]
    if not files:
        sample = {
            "id": "allgemeinwissen-starter",
            "title": "🎉 Schul-Quiz: Allgemeinwissen & Fun Facts",
            "description": "Ein spannendes Kennenlern-Quiz mit 5 Fragen für den Beamer-Einsatz.",
            "created_at": "2026-11-06",
            "password_enabled": False,
            "password_hash": "",
            "questions": [
                {
                    "id": 1,
                    "question": "Welcher Planet ist der Sonne am nächsten?",
                    "time_limit": 20,
                    "points": 1000,
                    "options": ["Venus", "Merkur", "Mars", "Jupiter"],
                    "correct_index": 1
                },
                {
                    "id": 2,
                    "question": "Wie viele Zähne hat ein erwachsener Mensch normalerweise (inkl. Weisheitszähne)?",
                    "time_limit": 20,
                    "points": 1000,
                    "options": ["28", "30", "32", "36"],
                    "correct_index": 2
                },
                {
                    "id": 3,
                    "question": "Welches Tier kann bekanntlich nicht rückwärts gehen?",
                    "time_limit": 20,
                    "points": 1000,
                    "options": ["Känguru", "Elefant", "Pinguin", "Frosch"],
                    "correct_index": 0
                },
                {
                    "id": 4,
                    "question": "Was ist die chemische Formel für gewöhnliches Kochsalz?",
                    "time_limit": 15,
                    "points": 1000,
                    "options": ["H2O", "CO2", "NaCl", "CH4"],
                    "correct_index": 2
                },
                {
                    "id": 5,
                    "question": "In welcher Stadt steht der berühmte schiefe Turm?",
                    "time_limit": 15,
                    "points": 1000,
                    "options": ["Rom", "Florenz", "Venedig", "Pisa"],
                    "correct_index": 3
                }
            ]
        }
        filepath = os.path.join(QUIZZES_DIR, "allgemeinwissen-starter.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False, indent=2)


def list_quizzes() -> List[Dict[str, Any]]:
    ensure_quizzes_dir()
    real_quizzes_dir = os.path.realpath(QUIZZES_DIR)
    quizzes = []
    for filename in sorted(os.listdir(real_quizzes_dir)):
        if filename.endswith(".json"):
            filepath = os.path.realpath(os.path.join(real_quizzes_dir, filename))
            if not filepath.startswith(real_quizzes_dir + os.sep) or not os.path.isfile(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_id = str(data.get("id", filename.replace(".json", "")))
                    safe_id = validate_quiz_id(raw_id) or validate_quiz_id(filename.replace(".json", ""))
                    if not safe_id:
                        continue
                    has_pwd = _has_stored_password(data)
                    quizzes.append({
                        "id": safe_id,
                        "title": str(data.get("title", "Unbenanntes Quiz")),
                        "description": str(data.get("description", "")),
                        "question_count": len(data.get("questions", [])),
                        "created_at": str(data.get("created_at", "")),
                        "password_enabled": has_pwd,
                        "has_password": has_pwd
                    })
            except Exception as e:
                print(f"Fehler beim Laden von {filename}: {e}")
    return quizzes


def get_quiz(quiz_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Lädt ein Quiz inkl. interner Hash-Daten (nur für den Server)."""
    ensure_quizzes_dir()
    filepath = _safe_quiz_filepath(quiz_id)
    if not filepath:
        return None
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Fehler beim Lesen von {filepath}: {e}")
            return None

    # Fallback: Suche nach interner ID in gültigen JSON-Dateien im QUIZZES_DIR
    for filename in os.listdir(QUIZZES_DIR):
        if filename.endswith(".json"):
            fp = os.path.realpath(os.path.join(QUIZZES_DIR, filename))
            if not fp.startswith(QUIZZES_DIR + os.sep):
                continue
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("id") == quiz_id:
                        return data
            except Exception:
                pass
    return None


def get_quiz_for_client(quiz_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Lädt ein Quiz bereinigt ohne Passwort/Hash für das Editor-Frontend."""
    data = get_quiz(quiz_id)
    if not data:
        return None
    return sanitize_quiz_for_client(data)


def save_quiz(quiz_data: Dict[str, Any]) -> str:
    os.makedirs(QUIZZES_DIR, exist_ok=True)
    raw_id = str(quiz_data.get("id") or "").strip()
    safe_id = "".join(c for c in raw_id if c.isascii() and (c.isalnum() or c in ("-", "_")))[:64].strip()
    if not safe_id:
        safe_id = str(uuid.uuid4())[:8]

    filepath = _safe_quiz_filepath(safe_id)
    if not filepath:
        safe_id = str(uuid.uuid4())[:8]
        filepath = os.path.join(QUIZZES_DIR, f"{safe_id}.json")

    to_store = dict(quiz_data)
    to_store["id"] = safe_id

    # Bestehendes Passwort ermitteln, falls ein vorhandenes Quiz aktualisiert wird
    existing = get_quiz(safe_id) if os.path.exists(filepath) else None
    password_enabled = bool(to_store.get("password_enabled", False))
    new_plain_password = str(to_store.pop("password", "") or "").strip()

    if password_enabled:
        if new_plain_password:
            to_store["password_hash"] = hash_quiz_password(new_plain_password)
        elif existing and str(existing.get("password_hash", "")).strip():
            to_store["password_hash"] = str(existing["password_hash"]).strip()
        elif existing and str(existing.get("password", "")).strip():
            to_store["password_hash"] = hash_quiz_password(str(existing["password"]).strip())
        else:
            to_store["password_enabled"] = False
            to_store["password_hash"] = ""
    else:
        to_store["password_enabled"] = False
        to_store["password_hash"] = ""

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(to_store, f, ensure_ascii=False, indent=2)
    return safe_id


def delete_quiz(quiz_id: Optional[str]) -> bool:
    ensure_quizzes_dir()
    filepath = _safe_quiz_filepath(quiz_id)
    if filepath and os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False


def generate_excel_template() -> bytes:
    """Erzeugt eine saubere Excel-Vorlage mit Beispielen für Lehrer."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Quiz-Fragen"

    headers = [
        "Frage",
        "Antwort 1 (Rot / Dreieck)",
        "Antwort 2 (Blau / Raute)",
        "Antwort 3 (Gelb / Kreis)",
        "Antwort 4 (Grün / Quadrat)",
        "Richtige Antwort (1-4)",
        "Zeitlimit (Sekunden)"
    ]
    ws.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill(start_color="46178F", end_color="46178F", fill_type="solid")
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = 25

    ws.column_dimensions["A"].width = 45

    ws.append(["Hauptstadt von Frankreich?", "Berlin", "Paris", "Madrid", "Rom", 2, 20])
    ws.append(["Wie viel ist 7 mal 8?", "54", "58", "56", "64", 3, 15])
    ws.append(["Welches Element hat das Symbol 'O'?", "Gold", "Sauerstoff", "Osmium", "Eisen", 2, 20])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def import_from_excel(file_bytes: bytes, title: str = "Importiertes Quiz") -> Dict[str, Any]:
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    questions = []
    try:
        ws = wb.active
        q_id = 1
        for row in ws.iter_rows(min_row=2, values_only=True):
            if len(questions) >= MAX_IMPORT_QUESTIONS:
                break
            if not row or not row[0]:
                continue
            q_text = str(row[0]).strip()[:500]
            if not q_text:
                continue
            ans1 = str(row[1]).strip()[:200] if len(row) > 1 and row[1] is not None else ""
            ans2 = str(row[2]).strip()[:200] if len(row) > 2 and row[2] is not None else ""
            ans3 = str(row[3]).strip()[:200] if len(row) > 3 and row[3] is not None else ""
            ans4 = str(row[4]).strip()[:200] if len(row) > 4 and row[4] is not None else ""

            try:
                correct_num = int(row[5]) if len(row) > 5 and row[5] is not None else 1
                correct_index = max(0, min(3, correct_num - 1))
            except (ValueError, TypeError):
                correct_index = 0

            try:
                time_limit = int(row[6]) if len(row) > 6 and row[6] is not None else 20
                time_limit = max(5, min(120, time_limit))
            except (ValueError, TypeError):
                time_limit = 20

            options = [ans1, ans2, ans3, ans4]
            if len([o for o in options if o]) < 2:
                continue

            questions.append({
                "id": q_id,
                "question": q_text,
                "time_limit": time_limit,
                "points": 1000,
                "options": options,
                "correct_index": correct_index
            })
            q_id += 1
    finally:
        wb.close()

    if not questions:
        raise ValueError("Keine gültigen Fragen in der Excel-Datei gefunden.")

    safe_title = (str(title or "").strip() or "Importiertes Quiz")[:150]
    quiz_data = {
        "id": f"imported-{str(uuid.uuid4())[:8]}",
        "title": safe_title,
        "description": f"Erstellt via Excel-Import mit {len(questions)} Fragen",
        "created_at": datetime.date.today().isoformat(),
        "password_enabled": False,
        "password_hash": "",
        "questions": questions
    }
    save_quiz(quiz_data)
    return sanitize_quiz_for_client(quiz_data)
