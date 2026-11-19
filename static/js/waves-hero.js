/* Fondo de la colección Waves: ecualizador de puntos con la palabra WAVES recortada. */
(function () {
    const canvas = document.getElementById('waveCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let W = 0, H = 0, t = 0, corriendo = true;

    function ajustar() {
        const dpr = window.devicePixelRatio || 1;   // nítido también en pantallas de alta densidad
        W = canvas.parentElement.offsetWidth;
        H = canvas.parentElement.offsetHeight;
        canvas.width = W * dpr;
        canvas.height = H * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    window.addEventListener('resize', ajustar);
    ajustar();
    document.addEventListener('visibilitychange', () => { corriendo = !document.hidden; if (corriendo) dibujar(); });

    function dibujar() {
        if (!corriendo) return;
        ctx.fillStyle = '#fff';
        ctx.fillRect(0, 0, W, H);

        const numCols = 64, numRows = 22, dotR = 4;
        const gapX = W / numCols, gapY = H / numRows;

        for (let col = 0; col < numCols; col++) {
            const x = col * gapX + gapX / 2;
            const normX = (col / numCols) * 2 - 1;
            const wave1 = Math.sin(normX * Math.PI * 3 + t * 1.8) * 0.5;
            const wave2 = Math.sin(normX * Math.PI * 5 - t * 2.3) * 0.3;
            const wave3 = Math.sin(normX * Math.PI * 1.5 + t * 0.9) * 0.2;
            const amp = Math.abs(wave1 + wave2 + wave3);
            const litRows = Math.round(amp * (numRows / 2));

            for (let row = 0; row < numRows; row++) {
                const y = row * gapY + gapY / 2;
                const rowFromCenter = Math.abs(row - (numRows / 2 - 0.5));
                if (rowFromCenter <= litRows) {
                    ctx.fillStyle = `rgba(0,0,0,${1 - (rowFromCenter / (numRows / 2)) * 0.4})`;
                } else {
                    ctx.fillStyle = 'rgba(0,0,0,0.07)';
                }
                ctx.beginPath();
                ctx.arc(x, y, dotR, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Recorte tipográfico WAVES + contorno
        ctx.save();
        ctx.globalCompositeOperation = 'destination-out';
        ctx.font = `900 ${W * 0.12}px 'Arial Black', sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = 'rgba(255,255,255,1)';
        ctx.fillText('WAVES', W / 2, H / 2);
        ctx.restore();

        ctx.save();
        ctx.font = `900 ${W * 0.12}px 'Arial Black', sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.strokeStyle = 'rgba(0,0,0,0.85)';
        ctx.lineWidth = 2;
        ctx.strokeText('WAVES', W / 2, H / 2);
        ctx.restore();

        t += 0.04;
        if (!sinMovimiento) requestAnimationFrame(dibujar);
    }
    dibujar();
})();
