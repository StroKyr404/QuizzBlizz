// Student / iPad Client Logic
let playerWs = null;
let myPin = null;
let myName = null;
let myPlayerId = null;
let hasAnsweredCurrentQuestion = false;

document.addEventListener('DOMContentLoaded', () => {
    const pinInput = document.getElementById('input-pin');
    if (pinInput) {
        if (pinInput.value && pinInput.value.length === 6) {
            checkPinStatus(pinInput.value.trim());
        }
        pinInput.addEventListener('input', (e) => {
            const val = e.target.value.trim();
            if (val.length === 6) {
                checkPinStatus(val);
            }
        });
    }
});

async function checkPinStatus(pin) {
    try {
        const res = await fetch(`/api/room/${pin}/info`);
        if (res.ok) {
            const info = await res.json();
            const pwdWrapper = document.getElementById('field-pwd-wrapper');
            if (pwdWrapper) {
                if (info.password_required) {
                    pwdWrapper.classList.remove('hidden');
                } else {
                    pwdWrapper.classList.add('hidden');
                }
            }
            if (info.is_locked) {
                showError("⚠️ Diese Spiel-Lobby ist derzeit gesperrt.");
            } else {
                hideError();
            }
        }
    } catch (err) {
        // Ignored during typing
    }
}

function hideError() {
    const errBox = document.getElementById('join-error-msg');
    if (errBox) errBox.classList.add('hidden');
}

function handleJoinSubmit(e) {
    e.preventDefault();
    const pin = document.getElementById('input-pin').value.trim();
    const name = document.getElementById('input-nickname').value.trim();
    const passwordInput = document.getElementById('input-password');
    const password = passwordInput ? passwordInput.value.trim() : '';

    if (!pin || pin.length !== 6) {
        showError("Bitte eine gültige 6-stellige PIN eingeben.");
        return;
    }
    if (!name) {
        showError("Bitte einen Namen eingeben.");
        return;
    }

    myPin = pin;
    myName = name;
    connectPlayerWebSocket(pin, name, password);
}

function showError(msg) {
    const errBox = document.getElementById('join-error-msg');
    if (errBox) {
        errBox.innerText = msg;
        errBox.classList.remove('hidden');
    }
}

function connectPlayerWebSocket(pin, name, password) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/player/${pin}`;

    playerWs = new WebSocket(wsUrl);

    playerWs.onopen = () => {
        console.log("📱 Player WebSocket geöffnet. Sende JOIN...");
        playerWs.send(JSON.stringify({
            type: 'JOIN',
            name: name,
            password: password || ''
        }));
    };

    playerWs.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handlePlayerMessage(msg);
    };

    playerWs.onclose = () => {
        console.log("Player WS geschlossen");
    };

    playerWs.onerror = (err) => {
        console.error("Player WS Error:", err);
        showError("Verbindung zum Spielserver fehlgeschlagen.");
    };
}

function handlePlayerMessage(msg) {
    switch (msg.type) {
        case 'JOINED_SUCCESS':
            myPlayerId = msg.player_id;
            document.getElementById('player-header').classList.remove('hidden');
            document.getElementById('player-nickname-badge').innerText = msg.name;
            setPhase('phase-lobby');
            break;

        case 'ERROR':
            showError(msg.message);
            if (msg.code === 'WRONG_PASSWORD') {
                const pwdWrapper = document.getElementById('field-pwd-wrapper');
                if (pwdWrapper) {
                    pwdWrapper.classList.remove('hidden');
                    const pwdInp = document.getElementById('input-password');
                    if (pwdInp) pwdInp.focus();
                }
            }
            if (playerWs) playerWs.close();
            break;

        case 'KICKED':
            alert(msg.message || "Du wurdest aus dem Spiel entfernt.");
            location.reload();
            break;

        case 'GET_READY':
            hasAnsweredCurrentQuestion = false;
            document.getElementById('pl-gr-num').innerText = msg.question_number;
            setPhase('phase-get-ready');
            break;

        case 'QUESTION_START':
            hasAnsweredCurrentQuestion = false;
            showPlayerQuestion(msg);
            break;

        case 'ANSWER_RECEIVED':
            setPhase('phase-submitted');
            break;

        case 'QUESTION_RESULT':
            showPlayerResult(msg);
            break;

        case 'LEADERBOARD_PHASE':
            // Keep current feedback or show wait
            break;

        case 'PODIUM_PLAYER':
            showPlayerPodium(msg);
            break;
    }
}

// 1. Show Question (Display 2 or 4 buttons)
function showPlayerQuestion(msg) {
    setPhase('phase-question');
    const optionsCount = msg.options_count || 4;

    for (let i = 0; i < 4; i++) {
        const pad = document.getElementById(`pl-pad-${i}`);
        const padText = document.getElementById(`pl-pad-text-${i}`);
        
        if (i < optionsCount) {
            pad.style.display = 'flex';
            pad.disabled = false;
            if (msg.options && msg.options[i]) {
                padText.innerText = msg.options[i];
            } else {
                padText.innerText = '';
            }
        } else {
            pad.style.display = 'none';
        }
    }
}

// 2. Submit Answer
function chooseAnswer(index) {
    if (hasAnsweredCurrentQuestion) return;
    hasAnsweredCurrentQuestion = true;

    // Vibrate device if supported
    if (navigator.vibrate) {
        navigator.vibrate(50);
    }

    if (playerWs && playerWs.readyState === WebSocket.OPEN) {
        playerWs.send(JSON.stringify({
            type: 'ANSWER',
            answer_index: index
        }));
    }

    // Instant local transition to submitted
    setPhase('phase-submitted');
}

// 3. Show Result (Feedback Screen)
function showPlayerResult(msg) {
    setPhase('phase-feedback');

    const feedbackEl = document.getElementById('phase-feedback');
    const iconEl = document.getElementById('feedback-icon');
    const titleEl = document.getElementById('feedback-title');
    const pointsEl = document.getElementById('feedback-points');
    const streakEl = document.getElementById('feedback-streak');
    const rankEl = document.getElementById('feedback-rank');
    const scoreBadge = document.getElementById('player-score-badge');

    if (scoreBadge) {
        scoreBadge.innerText = msg.total_score.toLocaleString('de-DE');
    }

    rankEl.innerText = msg.rank;

    if (msg.is_correct) {
        window.sounds.playCorrect();
        feedbackEl.className = 'flex-1 flex flex-col items-center justify-center p-6 text-center bg-emerald-600 text-white';
        iconEl.innerText = '✓';
        titleEl.innerText = 'Richtig!';
        pointsEl.innerText = `+${msg.points_earned.toLocaleString('de-DE')} Punkte`;
        pointsEl.className = 'text-2xl font-black text-amber-200 font-mono mb-4';

        if (msg.streak > 1) {
            streakEl.innerText = `🔥 ${msg.streak}er Serie!`;
            streakEl.classList.remove('hidden');
        } else {
            streakEl.classList.add('hidden');
        }
    } else {
        window.sounds.playWrong();
        feedbackEl.className = 'flex-1 flex flex-col items-center justify-center p-6 text-center bg-rose-700 text-white';
        iconEl.innerText = '✕';
        titleEl.innerText = 'Leider falsch!';
        pointsEl.innerText = '+0 Punkte';
        pointsEl.className = 'text-2xl font-black text-white/80 font-mono mb-4';
        streakEl.classList.add('hidden');
    }
}

// 4. Show Podium
function showPlayerPodium(msg) {
    setPhase('phase-podium');
    document.getElementById('pl-final-rank').innerText = msg.rank;
    document.getElementById('pl-final-score').innerText = msg.total_score.toLocaleString('de-DE');

    const icon = document.getElementById('pl-podium-icon');
    if (msg.rank === 1) {
        icon.innerText = '👑';
    } else if (msg.rank === 2) {
        icon.innerText = '🥈';
    } else if (msg.rank === 3) {
        icon.innerText = '🥉';
    } else {
        icon.innerText = '👏';
    }
}
