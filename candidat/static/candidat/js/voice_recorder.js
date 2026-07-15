/**
 * VoiceRecorder — enregistreur audio intégré avec visualisation waveform.
 * Utilise MediaRecorder + Web Audio API (natifs navigateur, aucune dépendance externe).
 *
 * Usage :
 *   const rec = new VoiceRecorder({ canvasId: 'my-canvas', color: '#F77F00', ... });
 *   await rec.start();
 *   rec.stop();   // déclenche onStop(blob, dureeSecondes)
 *   rec.cancel(); // abandonne sans déclencher onStop
 */
class VoiceRecorder {
    constructor({
        canvasId  = null,
        color     = '#F77F00',
        maxSec    = 120,
        onStart   = () => {},
        onTick    = (_sec) => {},
        onStop    = (_blob, _sec) => {},
        onError   = (_msg) => {},
    } = {}) {
        this.canvasId = canvasId;
        this.color    = color;
        this.maxSec   = maxSec;
        this.onStart  = onStart;
        this.onTick   = onTick;
        this.onStop   = onStop;
        this.onError  = onError;

        this._recorder   = null;
        this._stream     = null;
        this._chunks     = [];
        this._duration   = 0;
        this._timer      = null;
        this._animFrame  = null;
        this._audioCtx   = null;
        this._analyser   = null;
    }

    /* ── API publique ─────────────────────────────────────────────── */

    async start() {
        try {
            this._stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (_) {
            this.onError('Microphone non disponible. Vérifiez les permissions du navigateur.');
            return false;
        }

        this._chunks   = [];
        this._duration = 0;
        this._initAnalyser();

        const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '');
        this._recorder = new MediaRecorder(this._stream, mime ? { mimeType: mime } : {});

        this._recorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) this._chunks.push(e.data);
        };
        this._recorder.onstop = () => {
            const blob = new Blob(this._chunks, { type: this._recorder.mimeType || 'audio/webm' });
            const dur  = this._duration;
            this._cleanupHardware();
            this.onStop(blob, dur);
        };

        this._recorder.start(100); // slice toutes les 100 ms

        this._timer = setInterval(() => {
            this._duration++;
            this.onTick(this._duration);
            if (this._duration >= this.maxSec) this.stop();
        }, 1000);

        this.onStart();
        return true;
    }

    stop() {
        if (this._recorder && this._recorder.state === 'recording') {
            this._recorder.stop();
        }
        clearInterval(this._timer);
    }

    cancel() {
        clearInterval(this._timer);
        if (this._recorder && this._recorder.state !== 'inactive') {
            this._recorder.ondataavailable = null;
            this._recorder.onstop = () => {};
            this._recorder.stop();
        }
        this._cleanupHardware();
    }

    /* ── Interne ──────────────────────────────────────────────────── */

    _initAnalyser() {
        try {
            this._audioCtx  = new (window.AudioContext || window.webkitAudioContext)();
            const src       = this._audioCtx.createMediaStreamSource(this._stream);
            this._analyser  = this._audioCtx.createAnalyser();
            this._analyser.fftSize        = 64;
            this._analyser.smoothingTimeConstant = 0.75;
            src.connect(this._analyser);
            this._drawLoop();
        } catch (_) { /* waveform non critique */ }
    }

    _drawLoop() {
        const canvas = this.canvasId ? document.getElementById(this.canvasId) : null;
        if (!canvas || !this._analyser) return;

        const ctx    = canvas.getContext('2d');
        const W      = canvas.width;
        const H      = canvas.height;
        const nBars  = this._analyser.frequencyBinCount; // fftSize / 2 = 32
        const data   = new Uint8Array(nBars);
        const gap    = 2;
        const barW   = Math.max(2, Math.floor((W - gap * (nBars - 1)) / nBars));
        const color  = this.color;

        const draw = () => {
            this._animFrame = requestAnimationFrame(draw);
            if (!this._analyser) return;

            this._analyser.getByteFrequencyData(data);
            ctx.clearRect(0, 0, W, H);

            for (let i = 0; i < nBars; i++) {
                const ratio  = data[i] / 255;
                const barH   = Math.max(3, ratio * H * 0.92);
                const x      = i * (barW + gap);
                const y      = (H - barH) / 2;
                const radius = Math.min(barW / 2, 3);

                ctx.globalAlpha = 0.35 + ratio * 0.65;
                ctx.fillStyle   = color;

                // Barres arrondies
                ctx.beginPath();
                ctx.moveTo(x + radius, y);
                ctx.lineTo(x + barW - radius, y);
                ctx.quadraticCurveTo(x + barW, y, x + barW, y + radius);
                ctx.lineTo(x + barW, y + barH - radius);
                ctx.quadraticCurveTo(x + barW, y + barH, x + barW - radius, y + barH);
                ctx.lineTo(x + radius, y + barH);
                ctx.quadraticCurveTo(x, y + barH, x, y + barH - radius);
                ctx.lineTo(x, y + radius);
                ctx.quadraticCurveTo(x, y, x + radius, y);
                ctx.closePath();
                ctx.fill();
            }
            ctx.globalAlpha = 1;
        };
        draw();
    }

    _cleanupHardware() {
        cancelAnimationFrame(this._animFrame);
        this._animFrame = null;
        if (this._stream)   { this._stream.getTracks().forEach(t => t.stop()); this._stream = null; }
        if (this._audioCtx) { try { this._audioCtx.close(); } catch (_) {} this._audioCtx = null; }
        this._analyser = null;

        // Effacer le canvas
        const canvas = this.canvasId ? document.getElementById(this.canvasId) : null;
        if (canvas) { canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height); }
    }
}
