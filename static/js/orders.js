(function () {
    const modal = document.getElementById('modalQueja');
    if (!modal) return;
    const opciones = JSON.parse(document.getElementById('opciones-prendas').textContent || '[]');
    const selectPrenda = document.getElementById('selectPrenda');

    function cargarPrendas(ventaId) {
        // Solo las prendas de ESE pedido
        selectPrenda.innerHTML = '';
        const vacio = document.createElement('option');
        vacio.value = '';
        vacio.textContent = '-- Seleccionar Prenda con Defecto --';
        selectPrenda.appendChild(vacio);
        opciones.filter(o => o.venta === ventaId).forEach(o => {
            const op = document.createElement('option');
            op.value = o.producto;
            op.textContent = o.texto;
            selectPrenda.appendChild(op);
        });
    }

    document.querySelectorAll('[data-reportar]').forEach(btn => btn.addEventListener('click', () => {
        const ventaId = Number(btn.dataset.reportar);
        document.getElementById('modalVentaId').value = ventaId;
        cargarPrendas(ventaId);
        modal.style.display = 'block';
        window.scrollTo({ top: modal.offsetTop - 40, behavior: 'smooth' });
    }));
    document.getElementById('cerrarModal').addEventListener('click', () => { modal.style.display = 'none'; });
})();
