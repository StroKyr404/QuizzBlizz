#!/bin/bash
# QuizBlizz Start-Skript für macOS

cd "$(dirname "$0")"

echo "⚡ Starte QuizBlizz Schul-Quiz..."

# Falls .venv fehlt (z.B. auf Mac der Kollegin), automatisch im Benutzerbereich anlegen
if [ ! -d ".venv" ]; then
    echo "📦 Ersteinrichtung: Installiere QuizBlizz (keine Adminrechte nötig)..."
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
fi

# Warte aktiv, bis der Webserver wirklich antwortet, und öffne erst DANN den Browser!
(
    until curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ | grep -q "200"; do
        sleep 0.3
    done
    open "http://localhost:8000/host"
) &

# Server starten
exec .venv/bin/python run.py "$@"
