/* Humo del fondo y medidores decorativos de Octane (los valores son al azar, no son datos reales). */
(function () {
    const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ---- Humo
    const canvas = document.getElementById('smokeCanvas');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        const ajustar = () => { canvas.width = canvas.parentElement.offsetWidth; canvas.height = canvas.parentElement.offsetHeight; };
        ajustar();
        window.addEventListener('resize', ajustar);

        class Particula {
            constructor() { this.reiniciar(); }
            reiniciar() {
                this.x = Math.random() * canvas.width;
                this.y = canvas.height + 40;
                this.size = Math.random() * 80 + 30;
                this.speedY = -(Math.random() * 0.6 + 0.2);
                this.speedX = (Math.random() - 0.5) * 0.4;
                this.opacity = Math.random() * 0.35 + 0.1;
            }
            actualizar() {
                this.y += this.speedY; this.x += this.speedX; this.size += 0.2; this.opacity -= 0.002;
                if (this.opacity <= 0) this.reiniciar();
            }
            dibujar() {
                const g = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, this.size);
                g.addColorStop(0, `rgba(175,14,175,${this.opacity})`);
                g.addColorStop(1, 'transparent');
                ctx.beginPath(); ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill();
            }
        }
        const particulas = Array.from({ length: 20 }, () => new Particula());
        let activo = true;
        const animar = () => {
            if (!activo) return;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            particulas.forEach(p => { p.actualizar(); p.dibujar(); });
            if (!sinMovimiento) requestAnimationFrame(animar);
        };
        document.addEventListener('visibilitychange', () => { activo = !document.hidden; if (activo) animar(); });
        animar();
    }

    // ---- Medidores
    const medidores = [
        { id: 'bars-angle', valId: 'val-angle', min: 35, max: 60, sufijo: '°' },
        { id: 'bars-grip', valId: 'val-grip', min: 50, max: 90, sufijo: '%' },
        { id: 'bars-smoke', valId: 'val-smoke', min: 80, max: 100, sufijo: '%' },
        { id: 'bars-boost', valId: 'val-boost', min: 1.2, max: 2.0, sufijo: ' BAR', decimal: true },
    ];
    medidores.forEach(m => {
        const el = document.getElementById(m.id);
        if (!el) return;
        for (let i = 0; i < 10; i++) {
            const barra = document.createElement('div');
            barra.className = 'rpm-bar-item';
            barra.style.height = (10 + i * 4) + 'px';
            el.appendChild(barra);
        }
    });
    function actualizar() {
        medidores.forEach(m => {
            const el = document.getElementById(m.id);
            if (!el) return;
            const v = m.decimal ? Math.random() * (m.max - m.min) + m.min : Math.floor(Math.random() * (m.max - m.min) + m.min);
            const activas = Math.round(((v - m.min) / (m.max - m.min)) * 10);
            el.querySelectorAll('.rpm-bar-item').forEach((b, i) => { b.style.background = i < activas ? '#af0eaf' : '#1a1a1a'; });
            document.getElementById(m.valId).textContent = m.decimal ? v.toFixed(1) + m.sufijo : v + m.sufijo;
        });
    }
    actualizar();
    if (!sinMovimiento) {
        let reloj = setInterval(actualizar, 900);
        document.addEventListener('visibilitychange', () => {
            clearInterval(reloj);
            if (!document.hidden) reloj = setInterval(actualizar, 900);
        });
    }
})();
