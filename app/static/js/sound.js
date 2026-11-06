// Web Audio Sound Synthesizer for Klassenhut
// Generates cheerful Kahoot-like sound effects without requiring audio files

class SoundEngine {
    constructor() {
        this.ctx = null;
        this.enabled = true;
        this.lobbyLoopId = null;
        this.isLooping = false;
    }

    init() {
        if (!this.ctx) {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AudioCtx();
        }
        if (this.ctx && this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
    }

    toggleMute() {
        this.enabled = !this.enabled;
        if (!this.enabled) {
            this.stopLobbyMusic();
        }
        return this.enabled;
    }

    playTone(freq, type = 'sine', duration = 0.2, gainValue = 0.15, startTime = 0) {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;

        const now = this.ctx.currentTime + startTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = type;
        osc.frequency.setValueAtTime(freq, now);

        gain.gain.setValueAtTime(gainValue, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start(now);
        osc.stop(now + duration);
    }

    // Lobby joining "blip"
    playJoin() {
        this.playTone(523.25, 'triangle', 0.1, 0.15); // C5
        this.playTone(659.25, 'triangle', 0.15, 0.15, 0.08); // E5
    }

    // Countdown tick
    playTick(isFast = false) {
        const freq = isFast ? 880 : 440;
        this.playTone(freq, 'sine', 0.08, 0.12);
    }

    // Time's up gong
    playTimesUp() {
        this.playTone(220, 'sawtooth', 0.4, 0.2);
        this.playTone(164.81, 'sawtooth', 0.6, 0.2, 0.1);
    }

    // Correct Answer Fanfare
    playCorrect() {
        // C - E - G - C major arpeggio
        this.playTone(523.25, 'triangle', 0.15, 0.2, 0);
        this.playTone(659.25, 'triangle', 0.15, 0.2, 0.1);
        this.playTone(783.99, 'triangle', 0.2, 0.2, 0.2);
        this.playTone(1046.50, 'triangle', 0.4, 0.25, 0.3);
    }

    // Wrong Answer Thud
    playWrong() {
        this.playTone(293.66, 'sawtooth', 0.25, 0.2, 0); // D4
        this.playTone(277.18, 'sawtooth', 0.4, 0.2, 0.2); // C#4
    }

    // Podium Celebration Fanfare
    playPodiumFanfare() {
        const notes = [
            { f: 523.25, t: 0.15, d: 0 },
            { f: 523.25, t: 0.15, d: 0.15 },
            { f: 523.25, t: 0.15, d: 0.3 },
            { f: 659.25, t: 0.3, d: 0.45 },
            { f: 523.25, t: 0.2, d: 0.75 },
            { f: 783.99, t: 0.5, d: 0.95 },
            { f: 1046.50, t: 0.8, d: 1.45 }
        ];
        notes.forEach(n => this.playTone(n.f, 'triangle', n.t, 0.22, n.d));
    }

    // Gentle Lobby Tune Loop
    startLobbyMusic() {
        if (!this.enabled || this.isLooping) return;
        this.init();
        this.isLooping = true;

        const chords = [
            [261.63, 329.63, 392.00], // C
            [220.00, 261.63, 329.63], // Am
            [174.61, 220.00, 261.63], // F
            [196.00, 246.94, 293.66]  // G
        ];

        let chordIdx = 0;
        const playPattern = () => {
            if (!this.isLooping || !this.enabled) return;
            const c = chords[chordIdx % chords.length];
            // Arpeggio
            this.playTone(c[0], 'sine', 0.3, 0.05, 0);
            this.playTone(c[1], 'sine', 0.3, 0.05, 0.25);
            this.playTone(c[2], 'sine', 0.3, 0.05, 0.5);
            this.playTone(c[1], 'sine', 0.3, 0.05, 0.75);

            chordIdx++;
            this.lobbyLoopId = setTimeout(playPattern, 1000);
        };
        playPattern();
    }

    stopLobbyMusic() {
        this.isLooping = false;
        if (this.lobbyLoopId) {
            clearTimeout(this.lobbyLoopId);
            this.lobbyLoopId = null;
        }
    }
}

window.sounds = new SoundEngine();
