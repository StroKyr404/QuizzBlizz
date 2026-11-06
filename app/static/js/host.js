// Host Logic for Klassenhut Beamer
let ws = null;
let currentPin = null;
let currentJoinUrl = null;
let isRoomLocked = false;
let questionTimerInterval = null;
let currentRemainingTime = 0;

// UI View Switcher
function showView(viewId) {
    const views = [
        'view-select-quiz',
        'view-lobby',
        'view-get-ready',
        'view-question',
        'view-leaderboard',
        'view-podium'
    ];
    views.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            if (id === viewId) {
                el.classList.remove('hidden');
            } else {
                el.classList.add('hidden');
            }
        }
    });

    const topStartBtn = document.getElementById('btn-top-start');
    if (topStartBtn) {
        if (viewId === 'view-lobby') {
            topStartBtn.classList.remove('hidden');
        } else {
            topStartBtn.classList.add('hidden');
        }
    }
}

function toggleSound() {
    const isMuted = !window.sounds.toggleMute();
    const icon = document.getElementById('sound-icon');
    if (icon) {
        icon.innerText = isMuted ? '🔇' : '🔊';
    }
}

function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        }
    }
}

// Fullscreen QR Modal
function openQrModal() {
    const modal = document.getElementById('modal-qr-zoom');
    if (modal) {
        modal.classList.remove('hidden');
    }
}

function closeQrModal() {
    const modal = document.getElementById('modal-qr-zoom');
    if (modal) {
        modal.classList.add('hidden');
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeQrModal();
    }
});

// 1-Click Copy URL to Clipboard
function copyJoinUrl() {
    if (!currentJoinUrl) return;
    navigator.clipboard.writeText(currentJoinUrl).then(() => {
        const btn = document.getElementById('btn-copy-url');
        const icon = document.getElementById('copy-icon');
        const label = document.getElementById('copy-label');
        if (label && icon) {
            label.innerText = '✓ Link kopiert!';
            icon.innerText = '✅';
            btn.classList.add('bg-emerald-600', 'text-white');
            setTimeout(() => {
                label.innerText = 'Link kopieren';
                icon.innerText = '📋';
                btn.classList.remove('bg-emerald-600', 'text-white');
            }, 2000);
        }
    }).catch(err => {
        console.error("Copy failed:", err);
        prompt("Link zum Kopieren:", currentJoinUrl);
    });
}

// Toggle Lobby Lock (prevent joining)
function toggleLobbyLock() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'TOGGLE_LOCK' }));
    }
}

function updateLockUi(locked) {
    isRoomLocked = locked;
    const btn = document.getElementById('btn-lock-lobby');
    const icon = document.getElementById('lock-icon');
    const text = document.getElementById('lock-text');

    if (btn && icon && text) {
        if (locked) {
            icon.innerText = '🔒';
            text.innerText = 'Lobby gesperrt (Kein Beitritt)';
            btn.className = 'px-3 py-1 bg-rose-500/25 hover:bg-rose-500/35 text-rose-300 border border-rose-500/50 rounded-full text-xs font-black flex items-center space-x-1.5 transition-all shadow-md';
        } else {
            icon.innerText = '🔓';
            text.innerText = 'Lobby offen';
            btn.className = 'px-3 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 rounded-full text-xs font-black flex items-center space-x-1.5 transition-all';
        }
    }
}

// 1. Create Room from Selected Quiz
async function createRoomFromSelected() {
    const radio = document.querySelector('input[name="selected_quiz"]:checked');
    if (!radio) {
        alert("Bitte wähle ein Quiz aus!");
        return;
    }
    const quizId = radio.value;

    try {
        const res = await fetch('/api/room/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ quiz_id: quizId })
        });
        const data = await res.json();
        if (data.pin) {
            setupLobby(data);
        } else {
            alert("Fehler beim Erstellen des Raums");
        }
    } catch (err) {
        console.error("Fehler:", err);
        alert("Verbindungsfehler beim Erstellen des Raums");
    }
}

// 2. Setup Lobby with PIN, QR & WebSocket
function setupLobby(roomData) {
    currentPin = roomData.pin;
    currentJoinUrl = roomData.join_url;
    
    document.getElementById('quiz-title-badge').innerText = roomData.quiz_title;
    document.getElementById('lobby-pin-display').innerText = roomData.pin.replace(/(\d{3})(\d{3})/, '$1 $2');
    document.getElementById('modal-pin-display').innerText = roomData.pin.replace(/(\d{3})(\d{3})/, '$1 $2');
    
    document.getElementById('lobby-join-url-text').innerText = roomData.join_url;
    document.getElementById('lobby-qr-img').src = roomData.qr_code;
    document.getElementById('modal-qr-img').src = roomData.qr_code;

    // Show password badge if protected
    const pwdBadge = document.getElementById('badge-pwd-protected');
    if (pwdBadge) {
        if (roomData.password_required) {
            pwdBadge.classList.remove('hidden');
        } else {
            pwdBadge.classList.add('hidden');
        }
    }

    showView('view-lobby');
    window.sounds.startLobbyMusic();

    connectHostWebSocket(roomData.pin);
}

function connectHostWebSocket(pin) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/host/${pin}`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("🖥️ Host WebSocket verbunden");
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleHostMessage(msg);
    };

    ws.onclose = () => {
        console.log("Host WebSocket getrennt");
    };

    ws.onerror = (err) => {
        console.error("Host WS Error:", err);
    };
}

// 3. Handle incoming WebSocket Messages
function handleHostMessage(msg) {
    switch (msg.type) {
        case 'ROOM_STATUS':
            if (typeof msg.is_locked !== 'undefined') {
                updateLockUi(msg.is_locked);
            }
            if (msg.password_required) {
                const pwdBadge = document.getElementById('badge-pwd-protected');
                if (pwdBadge) pwdBadge.classList.remove('hidden');
            }
            renderPlayers(msg.players || []);
            break;

        case 'ROOM_LOCK_STATUS':
            updateLockUi(msg.is_locked);
            break;

        case 'PLAYER_JOINED':
            window.sounds.playJoin();
            renderPlayers(msg.players || []);
            break;

        case 'PLAYER_LEFT':
            renderPlayers(msg.players || []);
            break;

        case 'GET_READY':
            window.sounds.stopLobbyMusic();
            showGetReady(msg);
            break;

        case 'QUESTION_START':
            showQuestion(msg);
            break;

        case 'ANSWER_STATS_UPDATE':
            updateAnswerCount(msg.answered_count, msg.total_players);
            break;

        case 'QUESTION_REVEAL':
            showQuestionReveal(msg);
            break;

        case 'LEADERBOARD':
            showLeaderboard(msg);
            break;

        case 'PODIUM':
            showPodium(msg);
            break;
    }
}

// Render student badges in Lobby
function renderPlayers(players) {
    const container = document.getElementById('player-tags-container');
    const countEl = document.getElementById('player-count');
    const waitingEl = document.getElementById('lobby-waiting-hint');

    countEl.innerText = players.length;

    if (players.length === 0) {
        if (!waitingEl) {
            container.innerHTML = `<div id="lobby-waiting-hint" class="w-full text-center py-12 text-purple-300 font-semibold text-lg animate-pulse">Warte auf Schüler... Scannt den QR-Code!</div>`;
        }
        return;
    }

    container.innerHTML = '';
    players.forEach(p => {
        const badge = document.createElement('div');
        badge.className = 'group flex items-center space-x-2 bg-white/15 hover:bg-red-500/80 px-4 py-2.5 rounded-2xl border border-white/20 text-white font-bold text-base transition-all transform hover:scale-105 cursor-pointer shadow-lg animate-bounce-in';
        badge.title = 'Klicken zum Entfernen';
        badge.innerHTML = `
            <span>${escapeHtml(p.name)}</span>
            <span class="text-xs text-red-200 group-hover:inline hidden font-black">✕</span>
        `;
        badge.onclick = () => kickPlayer(p.id, p.name);
        container.appendChild(badge);
    });
}

function kickPlayer(playerId, name) {
    if (confirm(`Schüler "${name}" wirklich aus dem Spiel entfernen?`)) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                action: 'KICK_PLAYER',
                player_id: playerId
            }));
        }
    }
}

// 4. Start Game
function startGame() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'START_GAME' }));
    }
}

// 5. Get Ready Screen
function showGetReady(msg) {
    showView('view-get-ready');
    document.getElementById('gr-q-num').innerText = msg.question_number;
    document.getElementById('gr-q-total').innerText = msg.total_questions;
    document.getElementById('gr-question-title').innerText = msg.question_text;

    let countdown = msg.countdown || 3;
    const counterEl = document.getElementById('gr-counter');
    counterEl.innerText = countdown;

    const interval = setInterval(() => {
        countdown--;
        if (countdown > 0) {
            counterEl.innerText = countdown;
            window.sounds.playTick(false);
        } else {
            clearInterval(interval);
        }
    }, 1000);
}

// 6. Question Active Screen
function showQuestion(msg) {
    showView('view-question');

    document.getElementById('q-cur-num').innerText = msg.question_number;
    document.getElementById('q-total-num').innerText = msg.total_questions;
    document.getElementById('q-text').innerText = msg.question;

    document.getElementById('q-answers-given').innerText = "0";
    document.getElementById('q-total-players').innerText = msg.total_players;

    // Reset Answer Cards
    const cards = [0, 1, 2, 3];
    cards.forEach(i => {
        const card = document.getElementById(`card-ans-${i}`);
        const textEl = document.getElementById(`ans-text-${i}`);
        const statEl = document.getElementById(`ans-stat-${i}`);

        if (card && textEl && statEl) {
            card.style.opacity = '1';
            card.style.filter = 'none';
            card.style.transform = 'none';
            card.style.boxShadow = '';
            statEl.classList.add('hidden');

            if (msg.options && msg.options[i]) {
                card.style.display = 'flex';
                textEl.innerText = msg.options[i];
            } else {
                card.style.display = 'none';
            }
        }
    });

    document.getElementById('reveal-control-bar').classList.add('hidden');

    // Start Timer Countdown
    currentRemainingTime = msg.time_limit;
    const timerNum = document.getElementById('q-timer-num');
    timerNum.innerText = currentRemainingTime;

    if (questionTimerInterval) clearInterval(questionTimerInterval);

    questionTimerInterval = setInterval(() => {
        currentRemainingTime--;
        timerNum.innerText = Math.max(0, currentRemainingTime);

        if (currentRemainingTime <= 5 && currentRemainingTime > 0) {
            window.sounds.playTick(true);
        }

        if (currentRemainingTime <= 0) {
            clearInterval(questionTimerInterval);
            window.sounds.playTimesUp();
        }
    }, 1000);
}

function updateAnswerCount(answered, total) {
    const el = document.getElementById('q-answers-given');
    if (el) el.innerText = answered;
    const totEl = document.getElementById('q-total-players');
    if (totEl) totEl.innerText = total;
}

function skipQuestion() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'NEXT_STEP' }));
    }
}

// 7. Question Reveal
function showQuestionReveal(msg) {
    if (questionTimerInterval) clearInterval(questionTimerInterval);

    const correctIdx = msg.correct_index;

    // Highlight correct card, dim wrong cards
    for (let i = 0; i < 4; i++) {
        const card = document.getElementById(`card-ans-${i}`);
        const statEl = document.getElementById(`ans-stat-${i}`);
        const count = msg.stats ? (msg.stats[i] || 0) : 0;

        if (card && statEl) {
            statEl.innerText = count;
            statEl.classList.remove('hidden');

            if (i === correctIdx) {
                card.style.opacity = '1';
                card.style.boxShadow = '0 0 35px #22c55e, 0 0 10px #ffffff';
                card.style.transform = 'scale(1.02)';
            } else {
                card.style.opacity = '0.35';
                card.style.filter = 'grayscale(60%)';
                card.style.boxShadow = '';
            }
        }
    }

    window.sounds.playCorrect();
    document.getElementById('reveal-control-bar').classList.remove('hidden');
}

function hostNextStep() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'NEXT_STEP' }));
    }
}

// 8. Leaderboard
function showLeaderboard(msg) {
    showView('view-leaderboard');

    const listEl = document.getElementById('leaderboard-list');
    listEl.innerHTML = '';

    const nextBtn = document.getElementById('btn-lb-next');
    if (msg.is_last_question) {
        nextBtn.innerText = '🏆 Zum Siegerpodest ➔';
        nextBtn.className = 'w-full py-5 bg-gradient-to-r from-amber-400 via-yellow-400 to-amber-500 text-slate-950 font-black text-2xl rounded-3xl shadow-2xl transform active:scale-95 transition-all';
    } else {
        nextBtn.innerText = 'Nächste Frage ➔';
        nextBtn.className = 'w-full py-4 bg-gradient-to-r from-amber-400 to-amber-500 text-slate-950 font-black text-xl rounded-2xl shadow-2xl transform active:scale-95 transition-all';
    }

    const leaderboard = msg.leaderboard || [];
    leaderboard.forEach((p, idx) => {
        const item = document.createElement('div');
        item.className = 'flex items-center justify-between p-4 bg-white/10 backdrop-blur-md rounded-2xl border border-white/15 shadow-xl animate-rise-up';
        item.style.animationDelay = `${idx * 0.1}s`;

        const streakBadge = p.streak > 1 ? `<span class="ml-2 text-xs bg-amber-500/30 text-amber-300 px-2 py-0.5 rounded-full font-bold">🔥 ${p.streak}er Serie</span>` : '';

        item.innerHTML = `
            <div class="flex items-center space-x-4">
                <span class="w-10 h-10 rounded-xl bg-purple-700 font-black text-xl text-white flex items-center justify-center shadow-md">
                    ${p.rank}
                </span>
                <span class="text-xl font-black text-white">${escapeHtml(p.name)}</span>
                ${streakBadge}
            </div>
            <div class="text-2xl font-black text-amber-300 font-mono">
                ${p.score.toLocaleString('de-DE')}
            </div>
        `;
        listEl.appendChild(item);
    });
}

// 9. Podium Screen
function showPodium(msg) {
    showView('view-podium');
    window.sounds.playPodiumFanfare();

    const p = msg.podium;

    // First place
    if (p.first) {
        document.getElementById('podium-name-1').innerText = p.first.name;
        document.getElementById('podium-score-1').innerText = `${p.first.score.toLocaleString('de-DE')} Punkte`;
    }
    // Second place
    if (p.second) {
        document.getElementById('podium-name-2').innerText = p.second.name;
        document.getElementById('podium-score-2').innerText = `${p.second.score.toLocaleString('de-DE')} Punkte`;
    } else {
        document.getElementById('podium-col-2').style.display = 'none';
    }
    // Third place
    if (p.third) {
        document.getElementById('podium-name-3').innerText = p.third.name;
        document.getElementById('podium-score-3').innerText = `${p.third.score.toLocaleString('de-DE')} Punkte`;
    } else {
        document.getElementById('podium-col-3').style.display = 'none';
    }

    // Sequential reveal animation
    setTimeout(() => {
        const col3 = document.getElementById('podium-col-3');
        if (col3) col3.classList.remove('opacity-0', 'translate-y-12');
    }, 400);

    setTimeout(() => {
        const col2 = document.getElementById('podium-col-2');
        if (col2) col2.classList.remove('opacity-0', 'translate-y-12');
    }, 1000);

    setTimeout(() => {
        const col1 = document.getElementById('podium-col-1');
        if (col1) col1.classList.remove('opacity-0', 'translate-y-12');
        triggerConfetti();
    }, 1800);
}

function triggerConfetti() {
    if (window.confetti) {
        confetti({
            particleCount: 120,
            spread: 90,
            origin: { y: 0.6 }
        });
        setTimeout(() => {
            confetti({
                particleCount: 80,
                angle: 60,
                spread: 60,
                origin: { x: 0 }
            });
            confetti({
                particleCount: 80,
                angle: 120,
                spread: 60,
                origin: { x: 1 }
            });
        }, 500);
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
