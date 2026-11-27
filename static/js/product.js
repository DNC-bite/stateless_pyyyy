(function () {
    const pagina = document.getElementById('producto-page');
    if (!pagina) return;

    const form = document.getElementById('form-add-cart');
    const inputTalla = document.getElementById('selected-talla');
    const inputVariante = document.getElementById('selected-variante-id');
    const etiquetaTalla = document.getElementById('talla-seleccionada-label');
    const aviso = document.getElementById('talla-alert');
    const boton = document.getElementById('btn-carrito');
    const imagen = document.getElementById('main-product-img');
    const requiereTalla = pagina.dataset.requiereTalla === 'true';

    const abrirModelo = document.getElementById('open-model-3d');
    const dialogoModelo = document.getElementById('model-3d-dialog');
    const cerrarModelo = document.getElementById('close-model-3d');
    if (abrirModelo && dialogoModelo && cerrarModelo) {
        abrirModelo.addEventListener('click', () => dialogoModelo.showModal());
        cerrarModelo.addEventListener('click', () => dialogoModelo.close());
        dialogoModelo.addEventListener('click', event => {
            if (event.target === dialogoModelo) dialogoModelo.close();
        });
    }

    // ---- Talla
    document.querySelectorAll('.talla-btn').forEach(btn => btn.addEventListener('click', () => {
        document.querySelectorAll('.talla-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        inputTalla.value = btn.dataset.talla;
        etiquetaTalla.textContent = btn.dataset.talla;
        aviso.style.display = 'none';
    }));

    form.addEventListener('submit', e => {
        if (requiereTalla && !inputTalla.value) {
            e.preventDefault();
            aviso.style.display = 'block';
        }
    });

    const GUIAS = {
        pantalon: "📏 GUÍA DE TALLAS STATELESS (Pantalones):\n• 28: Cintura 71-76 cm\n• 30: Cintura 76-81 cm\n• 32: Cintura 81-86 cm\n• 34: Cintura 86-91 cm\n• 36: Cintura 91-96 cm\n\nCorte: Straight / Relaxed Fit.",
        superior: "📏 GUÍA DE TALLAS STATELESS (Camisas y Busos):\n• S: Pecho 90-96 cm | Largo 72 cm\n• M: Pecho 96-102 cm | Largo 74 cm\n• L: Pecho 102-108 cm | Largo 76 cm\n• XL: Pecho 108-114 cm | Largo 78 cm\n\nCorte: Boxy Oversized Fit.",
    };
    const guia = document.getElementById('guia-tallas');
    if (guia) guia.addEventListener('click', () => alert(GUIAS[pagina.dataset.tipoTalla] || ''));

    // ---- Color / existencias
    function aplicarStock(stock) {
        const agotado = Number(stock) <= 0;
        boton.disabled = agotado;
        boton.textContent = agotado ? 'AGOTADO' : 'AÑADIR AL CARRITO';
    }
    function elegirColor(btn) {
        document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        document.getElementById('color-nombre').textContent = btn.dataset.nombre;
        inputVariante.value = btn.dataset.id || '';
        imagen.src = btn.dataset.imagen || imagen.dataset.original;
        aplicarStock(btn.dataset.stock);
    }
    document.querySelectorAll('.color-btn').forEach(btn => btn.addEventListener('click', () => elegirColor(btn)));

    const original = document.querySelector('.color-btn[data-id=""]');
    aplicarStock(original ? original.dataset.stock : pagina.dataset.stockUnico);
})();
