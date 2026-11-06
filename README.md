# ⚡ QuizBlizz - Das blitzschnelle Schul-Quiz

Ein selbstgehosteter, eleganter **Kahoot-Nachbau**, optimiert für den Einsatz im Klassenzimmer mit **Beamer** und **Schüler-iPads**.

Entwickelt für den sofortigen Einsatz **ohne Admin-Rechte** und **ohne komplizierte Schulnetzwerk-Konfiguration**.

---

## ✨ Features

- 🖥️ **Beamer-Ansicht für die Lehrkraft**:
  - **Riesiger QR-Code**: Standardmäßig groß dargestellt + Klick vergrößert ihn auf den gesamten Bildschirm (ideal für große Klassenzimmer).
  - **1-Klick Link-Kopierer**: Die Web-Adresse ist dezent dargestellt und wird mit einem einzigen Klick („📋 Link kopieren“) in die Zwischenablage kopiert.
  - **Lobby-Sperre (🔒 / 🔓)**: Mit einem Klick kann das Beitreten in der offenen Lobby gesperrt werden, sobald alle Schüler im Raum sind.
  - **Quiz-Passwortschutz**: Optionale Passwortabfrage – Schüler können nur mit dem von dir genannten Passwort beitreten.
  - Live-Anzeige aller Schüler mit **Kick-Funktion** (Klick auf unpassende Nicknames).
  - Countdown-Timer, spannende Ton- und Tick-Effekte (über Web Audio, keine externen MP3s nötig).
  - Automatische Auswertung mit Antwortverteilungs-Diagramm.
  - Zwischen-Rangliste mit Punkte- und Serienanzeige (🔥 Streak).
  - Animierte **Siegerehrung auf dem Treppchen** (1., 2., 3. Platz) mit Konfetti-Kanone!

- 📱 **Schüler-Ansicht für iPads**:
  - Schneller Einstieg: QR-Code mit der iPad-Kamera scannen $\rightarrow$ PIN ist sofort eingetragen $\rightarrow$ Name eingeben $\rightarrow$ los!
  - Bei passwortgeschützten Quizzen erscheint automatisch das Eingabefeld für das Passwort.
  - 4 große, farbige Buzzer-Tasten (🔴 Dreieck, 🔵 Raute, 🟡 Kreis, 🟩 Quadrat).
  - Berührungsoptimiert für iPads (kein störendes Zoomen bei Doppeltippen).
  - Sofortiges Feedback (Richtig/Falsch mit Punkten, Streak und aktuellem Rang).

- 📊 **Quiz-Editor & Excel-Import**:
  - Interaktiver Fragen-Editor direkt im Browser.
  - Option zum Aktivieren/Deaktivieren des Passwortschutzes und Festlegen des Passworts.
  - **Excel-Vorlage herunterladen**, Fragen in Ruhe am Computer ausfüllen und per Drag & Drop hochladen.
  - Zeitlimits pro Frage flexibel einstellbar (5s bis 90s).

---

## 🖱️ Doppelklick-Start für Kolleginnen (Ohne Terminal & ohne Admin-Rechte)

Für Kolleginnen, die kein Terminal nutzen möchten:

1. **Option A: Über die App**
   - Einfach doppelt auf **`QuizBlizz.app`** klicken.
   - Der Server startet im Hintergrund und Safari öffnet sich automatisch, sobald alles startklar ist!

2. **Option B: Über den Finder-Starter**
   - Doppelklick auf **`QuizBlizz_Starten.command`** im Finder.

3. **Für Kolleginnen packen (ZIP erstellen)**:
   - Führe einmal `./package_release.sh` aus.
   - Es entsteht eine Datei **`QuizBlizz-macOS.zip`**, die du per USB-Stick, AirDrop oder als GitHub Release teilen kannst. Kolleginnen entpacken sie und klicken einfach auf `QuizBlizz.app`!

- 🌐 **Sicheres Schul-WLAN Bypass (Cloudflare Tunnel)**:
  - Verhindert das Problem der "Client-Isolation" in Schul-WLANs, bei dem iPads den Mac oft nicht direkt im lokalen Netz erreichen können.
  - Erzeugt bei Bedarf automatisch eine sichere HTTPS-Adresse, die von allen iPads sofort geöffnet werden kann.

---

## 🚀 Schnellstart

### Auf dem Mac starten:

1. Öffne das Terminal und wechsle in diesen Ordner.
2. Starte das Spiel mit:
   ```bash
   ./start.sh
   ```
   *Alternativ ohne Skript:*
   ```bash
   .venv/bin/python run.py
   ```
3. Dein Standard-Browser öffnet sich automatisch auf der Beamer-Ansicht (`http://localhost:8000/host`).

---

## 📖 Spielablauf im Unterricht

1. **Beamer vorbereiten**:
   - Öffne `http://localhost:8000/host`.
   - Wähle ein Quiz aus und klicke auf **„Lobby eröffnen“**.
   - Klicke oben rechts auf **„⛶ Vollbild“**, um die Ansicht optimal auf den Beamer zu legen.
2. **Schüler einloggen**:
   - Die Schüler öffnen auf ihren iPads die **Kamera-App** und scannen den QR-Code auf der Leinwand.
   - Sie geben ihren Vornamen ein und tippen auf **„Los geht's“**.
3. **Spiel leiten**:
   - Sobald alle Schüler in der Lobby zu sehen sind, klickt die Lehrkraft auf **„Spiel starten“**.
   - Auf dem Beamer wird die Frage angezeigt, auf den iPads erscheinen die 4 Antwortflächen.
   - Nach Ablauf der Zeit (oder wenn alle geantwortet haben) folgt die Auflösung mit Diagramm, Rangliste und am Ende das Siegerpodest.

---

## 📥 Excel-Fragenkatalog importieren

1. Klicke im Menü auf **„Quiz-Editor“** (`/editor`).
2. Klicke auf **„Excel-Vorlage herunterladen“** (`quiz_vorlage.xlsx`).
3. Trage deine Fragen, die 4 Antwortmöglichkeiten und die Ziffer der richtigen Antwort (1 bis 4) in Excel ein.
4. Klicke auf **„Excel-Datei hochladen“** – das Quiz ist sofort spielbereit!
