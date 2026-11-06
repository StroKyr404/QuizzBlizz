// Quiz Editor JavaScript
let currentQuiz = window.initialQuiz || {
    id: 'quiz-' + Math.random().toString(36).substring(2, 9),
    title: 'Neues Quiz',
    description: '',
    questions: [
        {
            id: 1,
            question: 'Erste Frage hier eingeben...',
            time_limit: 20,
            options: ['Antwort 1', 'Antwort 2', 'Antwort 3', 'Antwort 4'],
            correct_index: 0
        }
    ]
};

document.addEventListener('DOMContentLoaded', () => {
    renderQuiz();
});

function renderQuiz() {
    document.getElementById('quiz-title-input').value = currentQuiz.title || '';
    renderQuestions();
}

function renderQuestions() {
    const container = document.getElementById('questions-container');
    const countEl = document.getElementById('active-questions-count');
    
    const questions = currentQuiz.questions || [];
    countEl.innerText = questions.length;
    container.innerHTML = '';

    questions.forEach((q, qIdx) => {
        const qCard = document.createElement('div');
        qCard.className = 'bg-white/5 border border-white/10 rounded-2xl p-5 shadow-lg relative';
        
        qCard.innerHTML = `
            <div class="flex items-center justify-between mb-4 pb-3 border-b border-white/10">
                <div class="flex items-center space-x-3">
                    <span class="w-8 h-8 rounded-xl bg-purple-700 font-black text-sm text-white flex items-center justify-center">
                        ${qIdx + 1}
                    </span>
                    <span class="text-xs font-bold uppercase text-purple-300">Frage</span>
                </div>
                
                <div class="flex items-center space-x-3">
                    <!-- Timer Dropdown -->
                    <div class="flex items-center space-x-1.5 bg-black/30 px-3 py-1.5 rounded-xl border border-white/10 text-xs">
                        <span>⏱️</span>
                        <select onchange="updateQuestionTimer(${qIdx}, this.value)" class="bg-transparent text-white font-bold focus:outline-none cursor-pointer">
                            <option value="5" ${q.time_limit == 5 ? 'selected' : ''} class="bg-slate-900">5 Sek</option>
                            <option value="10" ${q.time_limit == 10 ? 'selected' : ''} class="bg-slate-900">10 Sek</option>
                            <option value="15" ${q.time_limit == 15 ? 'selected' : ''} class="bg-slate-900">15 Sek</option>
                            <option value="20" ${q.time_limit == 20 ? 'selected' : ''} class="bg-slate-900">20 Sek</option>
                            <option value="30" ${q.time_limit == 30 ? 'selected' : ''} class="bg-slate-900">30 Sek</option>
                            <option value="60" ${q.time_limit == 60 ? 'selected' : ''} class="bg-slate-900">60 Sek</option>
                            <option value="90" ${q.time_limit == 90 ? 'selected' : ''} class="bg-slate-900">90 Sek</option>
                        </select>
                    </div>

                    <!-- Delete button -->
                    <button onclick="deleteQuestion(${qIdx})" class="text-rose-400 hover:text-rose-300 p-1.5 rounded-lg hover:bg-rose-500/10 transition-colors" title="Frage löschen">
                        🗑️
                    </button>
                </div>
            </div>

            <!-- Question Textarea -->
            <div class="mb-4">
                <input type="text" value="${escapeHtml(q.question)}" onchange="updateQuestionText(${qIdx}, this.value)" placeholder="Frage hier eingeben..." class="w-full text-lg font-bold bg-black/30 text-white rounded-xl px-4 py-2.5 border border-white/15 focus:border-purple-400 focus:outline-none">
            </div>

            <!-- 4 Kahoot Options -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <!-- Red 0 -->
                <div class="flex items-center p-3 rounded-xl btn-kahoot-red">
                    <input type="radio" name="correct_${qIdx}" value="0" ${q.correct_index === 0 ? 'checked' : ''} onchange="updateCorrectIndex(${qIdx}, 0)" class="w-5 h-5 mr-3 accent-emerald-500 cursor-pointer" title="Als richtige Antwort markieren">
                    <div class="shape-triangle mr-3 shrink-0"></div>
                    <input type="text" value="${escapeHtml(q.options[0] || '')}" onchange="updateOptionText(${qIdx}, 0, this.value)" placeholder="Antwort 1 (Rot)" class="w-full bg-white/20 text-white font-bold rounded-lg px-3 py-1.5 text-sm focus:outline-none placeholder-white/60">
                </div>

                <!-- Blue 1 -->
                <div class="flex items-center p-3 rounded-xl btn-kahoot-blue">
                    <input type="radio" name="correct_${qIdx}" value="1" ${q.correct_index === 1 ? 'checked' : ''} onchange="updateCorrectIndex(${qIdx}, 1)" class="w-5 h-5 mr-3 accent-emerald-500 cursor-pointer" title="Als richtige Antwort markieren">
                    <div class="shape-diamond mr-3 shrink-0"></div>
                    <input type="text" value="${escapeHtml(q.options[1] || '')}" onchange="updateOptionText(${qIdx}, 1, this.value)" placeholder="Antwort 2 (Blau)" class="w-full bg-white/20 text-white font-bold rounded-lg px-3 py-1.5 text-sm focus:outline-none placeholder-white/60">
                </div>

                <!-- Yellow 2 -->
                <div class="flex items-center p-3 rounded-xl btn-kahoot-yellow">
                    <input type="radio" name="correct_${qIdx}" value="2" ${q.correct_index === 2 ? 'checked' : ''} onchange="updateCorrectIndex(${qIdx}, 2)" class="w-5 h-5 mr-3 accent-emerald-500 cursor-pointer" title="Als richtige Antwort markieren">
                    <div class="shape-circle mr-3 shrink-0"></div>
                    <input type="text" value="${escapeHtml(q.options[2] || '')}" onchange="updateOptionText(${qIdx}, 2, this.value)" placeholder="Antwort 3 (Gelb)" class="w-full bg-white/20 text-white font-bold rounded-lg px-3 py-1.5 text-sm focus:outline-none placeholder-white/60">
                </div>

                <!-- Green 3 -->
                <div class="flex items-center p-3 rounded-xl btn-kahoot-green">
                    <input type="radio" name="correct_${qIdx}" value="3" ${q.correct_index === 3 ? 'checked' : ''} onchange="updateCorrectIndex(${qIdx}, 3)" class="w-5 h-5 mr-3 accent-emerald-500 cursor-pointer" title="Als richtige Antwort markieren">
                    <div class="shape-square mr-3 shrink-0"></div>
                    <input type="text" value="${escapeHtml(q.options[3] || '')}" onchange="updateOptionText(${qIdx}, 3, this.value)" placeholder="Antwort 4 (Grün)" class="w-full bg-white/20 text-white font-bold rounded-lg px-3 py-1.5 text-sm focus:outline-none placeholder-white/60">
                </div>
            </div>
            <div class="mt-2 text-[11px] text-purple-300 font-semibold text-right">
                🔘 Kreis anklicken = Richtige Antwort festlegen
            </div>
        `;
        container.appendChild(qCard);
    });
}

function updateQuestionText(qIdx, text) {
    currentQuiz.questions[qIdx].question = text;
}

function updateQuestionTimer(qIdx, val) {
    currentQuiz.questions[qIdx].time_limit = parseInt(val, 10);
}

function updateOptionText(qIdx, optIdx, text) {
    currentQuiz.questions[qIdx].options[optIdx] = text;
}

function updateCorrectIndex(qIdx, correctIdx) {
    currentQuiz.questions[qIdx].correct_index = parseInt(correctIdx, 10);
}

function addEmptyQuestion() {
    currentQuiz.questions = currentQuiz.questions || [];
    currentQuiz.questions.push({
        id: currentQuiz.questions.length + 1,
        question: 'Neue Frage...',
        time_limit: 20,
        options: ['', '', '', ''],
        correct_index: 0
    });
    renderQuestions();
}

function deleteQuestion(qIdx) {
    if (currentQuiz.questions.length <= 1) {
        alert("Ein Quiz muss mindestens eine Frage enthalten.");
        return;
    }
    currentQuiz.questions.splice(qIdx, 1);
    renderQuestions();
}

function createNewQuiz() {
    currentQuiz = {
        id: 'quiz-' + Math.random().toString(36).substring(2, 9),
        title: 'Neues Quiz',
        description: '',
        questions: [
            {
                id: 1,
                question: 'Erste Frage hier...',
                time_limit: 20,
                options: ['', '', '', ''],
                correct_index: 0
            }
        ]
    };
    renderQuiz();
}

async function loadQuizForEdit(quizId) {
    try {
        const res = await fetch(`/api/quizzes/${quizId}`);
        if (res.ok) {
            currentQuiz = await res.json();
            renderQuiz();
        }
    } catch (err) {
        console.error("Fehler beim Laden:", err);
    }
}

async function saveCurrentQuiz() {
    const title = document.getElementById('quiz-title-input').value.trim();
    if (!title) {
        alert("Bitte gib einen Titel für das Quiz ein.");
        return;
    }
    currentQuiz.title = title;

    try {
        const res = await fetch('/api/quizzes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentQuiz)
        });
        const data = await res.json();
        if (data.status === 'ok') {
            alert("✅ Quiz erfolgreich gespeichert!");
            location.href = `/editor?id=${data.id}`;
        }
    } catch (err) {
        console.error("Fehler beim Speichern:", err);
        alert("Fehler beim Speichern des Quiz");
    }
}

async function deleteQuizById(quizId) {
    if (!confirm("Möchtest du dieses Quiz wirklich unwiderruflich löschen?")) {
        return;
    }
    try {
        const res = await fetch(`/api/quizzes/${quizId}`, { method: 'DELETE' });
        if (res.ok) {
            location.href = '/editor';
        }
    } catch (err) {
        console.error("Fehler beim Löschen:", err);
    }
}

async function uploadExcelFile(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];

    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name.replace(/\.[^/.]+$/, ""));

    try {
        const res = await fetch('/api/quizzes/import', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.status === 'ok') {
            alert(`🎉 Erfolgreich ${data.quiz.questions.length} Fragen aus Excel importiert!`);
            location.href = `/editor?id=${data.quiz.id}`;
        } else {
            alert(data.detail || "Fehler beim Importieren der Datei");
        }
    } catch (err) {
        console.error("Fehler beim Upload:", err);
        alert("Fehler beim Hochladen der Excel-Datei.");
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
