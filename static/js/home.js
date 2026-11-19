/* Carrusel principal */
(function () {
    const slides = document.querySelectorAll('.hero-slide');
    const dots = document.querySelectorAll('.hero-dot');
    const numero = document.getElementById('slide-num');
    if (!slides.length) return;
    let actual = 0;

    function irA(i) {
        slides[actual].classList.remove('active');
        dots[actual].classList.remove('active');
        actual = (i + slides.length) % slides.length;
        slides[actual].classList.add('active');
        dots[actual].classList.add('active');
        numero.textContent = String(actual + 1).padStart(2, '0');
    }
    document.querySelectorAll('[data-slide-dir]').forEach(b => b.addEventListener('click', () => irA(actual + Number(b.dataset.slideDir))));
    dots.forEach((d, i) => d.addEventListener('click', () => irA(i)));
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) setInterval(() => irA(actual + 1), 5500);
})();

/* Fila de Essentials */
(function () {
    const track = document.getElementById('essentials-track');
    if (!track) return;
    let indice = 0;
    const VISIBLES = 3, ESPACIO = 20;
    function mover(dir) {
        const total = track.children.length;
        const max = Math.max(0, total - VISIBLES);
        indice = Math.max(0, Math.min(indice + dir, max));
        const paso = track.children[0].offsetWidth + ESPACIO; // ancho de la tarjeta + el espacio entre tarjetas
        track.style.transform = `translateX(-${indice * paso}px)`;
    }
    document.querySelectorAll('[data-ess-dir]').forEach(b => b.addEventListener('click', () => mover(Number(b.dataset.essDir))));
})();
