/* Fondo de puntos que ondulan (login, registro y recuperación). */
(function () {
    const canvas = document.getElementById('wavesCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let w, h, dots = [], t = 0, corriendo = true;

    function resize() {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
        dots = [];
        const spacing = 26;
        for (let x = 0; x < w + spacing; x += spacing) {
            for (let y = 0; y < h + spacing; y += spacing) dots.push({ baseX: x, baseY: y });
        }
    }
    resize();
    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', () => { corriendo = !document.hidden; if (corriendo) animate(); });

    function animate() {
        if (!corriendo) return;
        t += 0.012;
        ctx.clearRect(0, 0, w, h);
        for (const d of dots) {
            const dx = (d.baseX - w / 2) / w;
            const dy = (d.baseY - h / 2) / h;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const wave = Math.sin(dist * 10 - t * 2) * 0.5 + 0.5;
            ctx.beginPath();
            ctx.arc(d.baseX, d.baseY, 1 + wave * 2.2, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${0.12 + wave * 0.45})`;
            ctx.fill();
        }
        if (!sinMovimiento) requestAnimationFrame(animate);
    }
    animate();
})();
