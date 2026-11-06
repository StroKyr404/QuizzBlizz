# ⚡ QuizBlizz

> **Das blitzschnelle, interaktive Live-Quiz für Schule & Unterricht.**  
> Eine moderne, selbstgehostete Kahoot-Alternative – optimiert für iPads, Beamer und Schulnetzwerke ohne Admin-Rechte.

---

## 🎯 Warum QuizBlizz?

* 📱 **Für Schüler-iPads optimiert:** Schneller Einstieg über QR-Code, kein App-Download nötig (läuft direkt in Safari/Chrome), touch-optimierte 4-Farben-Buzzer und sofortiges Feedback mit Punkten und Serien (🔥 Streaks).
* 🖥️ **Große Beamer-Lobby:** Riesiger QR-Code (mit Klick-Vergrößerung für die hinterste Reihe), PIN, Live-Schülerliste mit Kick-Funktion und Zwischen-Rangliste.
* 🔒 **Sicher & Schultauglich:** 
  * **Lobby-Sperre (🔒 / 🔓):** Schließt den Raum, sobald alle Schüler anwesend sind.
  * **Passwortschutz:** Jedes Quiz kann optional mit einem geheimen Zusatz-Passwort geschützt werden.
  * **Schul-WLAN Bypass:** Umgeht automatisch die „Client-Isolation“ typischer Schul-Router (über Cloudflare Quick Tunnel) – ganz ohne Portfreigabe oder Adminrechte.
* 📊 **Excel-Import & Web-Editor:** Fragenkataloge direkt im Browser zusammenklicken oder als Excel-Vorlage (`.xlsx`) herunterladen, in Ruhe offline ausfüllen und per Drag & Drop hochladen.
* 🎵 **Integrierte Sound-Effekte:** Lobby-Melodie, spannende Countdown-Ticks und Sieger-Fanfaren über die Web Audio API – keine externen MP3s oder Lizenzprobleme.
* 🏆 **Siegerpodest mit Konfetti:** Animierte Siegerehrung (1., 2., 3. Platz) mit Konfetti-Kanone zum Abschluss des Spiels.

---

## 🚀 Schnellstart

### 1. Auf dem Mac (Lokal starten)

```bash
# Repository klonen
git clone git@github.com:StroKyr404/QuizzBlizz.git
cd QuizzBlizz

# Starten
./start.sh
```

*Das Skript richtet automatisch die lokale Python-Umgebung ein und öffnet das Hauptmenü im Browser (`http://localhost:8000`).*

### 2. Für Kolleginnen (Ohne Terminal & ohne Adminrechte)

* **Doppelklick-Start:** Kolleginnen können einfach doppelt auf **`QuizBlizz.app`** (oder **`QuizBlizz_Starten.command`**) klicken.
* Safari öffnet sich automatisch, sobald der Server bereit ist.
* *(Hinweis zum ersten Start auf macOS: Einmalig Rechtsklick $\rightarrow$ „Öffnen“ wählen, um den Gatekeeper zu bestätigen).*

---

## 🌐 Kostenloses Cloud-Hosting (Zero-Install für Kolleginnen)

Wenn Kolleginnen das Spiel nutzen möchten, ohne überhaupt etwas herunterzuladen oder zu entpacken, kann QuizBlizz in 2 Minuten kostenlos auf [Render.com](https://render.com) geschaltet werden:

1. Bei [render.com](https://render.com) mit dem GitHub-Account einloggen.
2. **„New +“** $\rightarrow$ **„Web Service“** wählen.
3. Dieses Repository (**`QuizzBlizz`**) auswählen.
4. Folgende Einstellungen hinterlegen:
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python run.py --no-tunnel --port $PORT`
5. Auf **„Deploy Web Service“** (Free Plan) klicken.

👉 **Ergebnis:** Eine feste Web-Adresse (z.&nbsp;B. `https://quizzblizz.onrender.com`), die Kolleginnen und Schüler einfach im Browser aufrufen können.

---

## 📖 Spielablauf im Unterricht

1. **Beamer vorbereiten:**
   * Starte QuizBlizz und klicke auf **„Spiel am Beamer starten“** (`/host`).
   * Wähle ein Quiz aus und klicke auf **„Lobby eröffnen“**.
   * Klicke oben rechts auf **„⛶ Vollbild“** für die Beamer-Projektion.
2. **Schüler verbinden:**
   * Die Schüler öffnen auf ihren iPads die **Kamera-App** und scannen den QR-Code auf der Leinwand.
   * Der Link öffnet sich in Safari mit bereits eingetragener PIN.
   * Schüler geben ihren Vornamen ein (und ggf. das mündlich genannte Quiz-Passwort) und tippen auf **„Los geht's“**.
   * Nach dem Login sehen Schüler den optischen **Wartebereich** (*„Erfolgreich eingeloggt!“*).
3. **Spiel leiten:**
   * Sobald alle Schüler da sind, kannst du die Lobby sperren (**🔒 Lobby gesperrt**) und auf **„Spiel starten ▶“** klicken.
   * Auf dem Beamer erscheinen Frage, Timer und Antwortmöglichkeiten.
   * Auf den iPads erscheinen die **4 großen Farbtasten** (🔴 Dreieck, 🔵 Raute, 🟡 Kreis, 🟩 Quadrat).
   * Nach Ablauf der Zeit zeigt der Beamer das Antwortdiagramm, die Rangliste und am Ende das Siegerpodest.

---

## 📊 Fragen mit Excel vorbereiten

1. Öffne den **Quiz-Editor** (`/editor`).
2. Klicke auf **„📥 Excel-Vorlage herunterladen“** (`quiz_vorlage.xlsx`).
3. Trage deine Fragen, die 4 Antwortoptionen, die Ziffer der richtigen Antwort (1 bis 4) und das Zeitlimit ein.
4. Klicke auf **„📤 Excel-Datei hochladen“** – dein Quiz wird sofort importiert und gespeichert.

---

## 🛠️ Technologie-Stack

* **Backend:** Python 3, FastAPI, Uvicorn (Asynchrone WebSockets für Latenzen < 30 ms)
* **Frontend:** HTML5, Modernes Tailwind CSS, Web Audio API Synthesizer, Canvas-Confetti
* **Netzwerk:** Automatischer Cloudflare Quick Tunnel (für strikte Schul-WLANs)
* **Dateiformate:** JSON-Speicherung, OpenPyXL (Excel-Import/Export), QR-Code Engine

---

## 📄 Lizenz

Dieses Projekt ist unter der [MIT-Lizenz](LICENSE) veröffentlicht – frei nutzbar, anpassbar und teilbar für Schulen und Lehrpersonen.
