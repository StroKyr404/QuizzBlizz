import os
import json
import uuid
import io
import csv
from typing import List, Dict, Any, Optional
import openpyxl

QUIZZES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quizzes")

def ensure_quizzes_dir():
    os.makedirs(QUIZZES_DIR, exist_ok=True)
    files = [f for f in os.listdir(QUIZZES_DIR) if f.endswith(".json")]
    if not files:
        # Create directly without calling ensure_quizzes_dir in loop
        sample = {
            "id": "allgemeinwissen-starter",
            "title": "🎉 Schul-Quiz: Allgemeinwissen & Fun Facts",
            "description": "Ein spannendes Kennenlern-Quiz mit 5 Fragen für den Beamer-Einsatz.",
            "created_at": "2026-11-06",
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
    quizzes = []
    for filename in sorted(os.listdir(QUIZZES_DIR)):
        if filename.endswith(".json"):
            filepath = os.path.join(QUIZZES_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    quizzes.append({
                        "id": data.get("id", filename.replace(".json", "")),
                        "title": data.get("title", "Unbenanntes Quiz"),
                        "description": data.get("description", ""),
                        "question_count": len(data.get("questions", [])),
                        "created_at": data.get("created_at", "")
                    })
            except Exception as e:
                print(f"Fehler beim Laden von {filename}: {e}")
    return quizzes

def get_quiz(quiz_id: str) -> Optional[Dict[str, Any]]:
    ensure_quizzes_dir()
    filepath = os.path.join(QUIZZES_DIR, f"{quiz_id}.json")
    if not os.path.exists(filepath):
        # try search by id in file
        for filename in os.listdir(QUIZZES_DIR):
            if filename.endswith(".json"):
                fp = os.path.join(QUIZZES_DIR, filename)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("id") == quiz_id:
                            return data
                except Exception:
                    pass
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Fehler beim Lesen von {filepath}: {e}")
        return None

def save_quiz(quiz_data: Dict[str, Any]) -> str:
    os.makedirs(QUIZZES_DIR, exist_ok=True)
    quiz_id = quiz_data.get("id")
    if not quiz_id:
        quiz_id = str(uuid.uuid4())[:8]
        quiz_data["id"] = quiz_id
    
    # Sanitize id
    safe_id = "".join(c for c in quiz_id if c.isalnum() or c in ("-", "_")).strip()
    if not safe_id:
        safe_id = str(uuid.uuid4())[:8]
    quiz_data["id"] = safe_id

    filepath = os.path.join(QUIZZES_DIR, f"{safe_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(quiz_data, f, ensure_ascii=False, indent=2)
    return safe_id

def delete_quiz(quiz_id: str) -> bool:
    ensure_quizzes_dir()
    filepath = os.path.join(QUIZZES_DIR, f"{quiz_id}.json")
    if os.path.exists(filepath):
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

    # Style header row
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill(start_color="46178F", end_color="46178F", fill_type="solid") # Kahoot purple
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = 25

    ws.column_dimensions["A"].width = 45

    # Sample rows
    ws.append(["Hauptstadt von Frankreich?", "Berlin", "Paris", "Madrid", "Rom", 2, 20])
    ws.append(["Wie viel ist 7 mal 8?", "54", "58", "56", "64", 3, 15])
    ws.append(["Welches Element hat das Symbol 'O'?", "Gold", "Sauerstoff", "Osmium", "Eisen", 2, 20])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

def import_from_excel(file_bytes: bytes, title: str = "Importiertes Quiz") -> Dict[str, Any]:
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active

    questions = []
    q_id = 1
    # Skip header
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        q_text = str(row[0]).strip()
        ans1 = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        ans2 = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
        ans3 = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
        ans4 = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""

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
        # filter out empty trailing options if minimum 2 exist
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

    quiz_data = {
        "id": f"imported-{str(uuid.uuid4())[:8]}",
        "title": title or "Importiertes Quiz",
        "description": f"Erstellt via Excel-Import mit {len(questions)} Fragen",
        "created_at": "2026-11-06",
        "questions": questions
    }
    save_quiz(quiz_data)
    return quiz_data
