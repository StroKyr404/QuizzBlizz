#!/bin/bash
# QuizBlizz Schnellstart für macOS

cd "$(dirname "$0")"

echo "⚡ Starte QuizBlizz Schul-Quiz..."

# Falls .venv fehlt, automatisch anlegen
if [ ! -d ".venv" ]; then
    echo "Erstelle Python-Umgebung..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

# Im Browser nach kurzer Wartezeit öffnen
(sleep 2 && open "http://localhost:8000/host") &

# Server starten
.venv/bin/python run.py "$@"
