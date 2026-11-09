#!/bin/bash
# Erstellt eine saubere ZIP-Datei für Kolleginnen und GitHub Releases

cd "$(dirname "$0")"

OUTPUT="QuizBlizz-macOS.zip"
echo "📦 Erstelle portables Paket: $OUTPUT..."

rm -f "$OUTPUT"

zip -r "$OUTPUT" \
    QuizBlizz.app \
    QuizBlizz_Starten.command \
    start.sh \
    run.py \
    requirements.txt \
    README.md \
    app \
    quizzes \
    -x "*.pyc" -x "*__pycache__*" -x "*.DS_Store*"

echo "✅ Fertig! Die Datei '$OUTPUT' kann jetzt direkt auf GitHub hochgeladen oder per AirDrop/USB an Kolleginnen weitergegeben werden."
