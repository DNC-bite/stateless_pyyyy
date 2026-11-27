(function () {
    const modal = document.getElementById('modalQueja');
    if (!modal) return;
    const opciones = JSON.parse(document.getElementById('opciones-prendas').textContent || '[]');
    const selectPrenda = document.getElementById('selectPrenda');
    const tipo = document.getElementById('selectTipo');
    const ventaInput = document.getElementById('modalVentaId');
    const productoInput = document.getElementById('modalProductoId');
    const pedidoField = document.getElementById('solicitud-pedido-field');
    const prendaField = document.getElementById('solicitud-prenda-field');

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

    selectPrenda.addEventListener('change', () => {
        productoInput.value = selectPrenda.value;
    });
    ventaInput.addEventListener('change', () => {
        productoInput.value = '';
        cargarPrendas(Number(ventaInput.value));
    });
    tipo.addEventListener('change', () => {
        const general = tipo.value === 'QUEJA_GENERAL';
        pedidoField.hidden = general;
        prendaField.hidden = general;
        ventaInput.required = !general;
        selectPrenda.required = !general;
        selectPrenda.disabled = general;
        if (general) {
            ventaInput.value = '';
            productoInput.value = '';
            selectPrenda.value = '';
        }
    });
    document.querySelectorAll('[data-reportar]').forEach(btn => btn.addEventListener('click', () => {
        const ventaId = Number(btn.dataset.reportar);
        tipo.value = 'PRENDA_DANADA';
        tipo.dispatchEvent(new Event('change'));
        ventaInput.value = String(ventaId);
        ventaInput.dispatchEvent(new Event('change'));
        modal.style.display = 'block';
        window.scrollTo({ top: modal.offsetTop - 40, behavior: 'smooth' });
    }));
    document.querySelector('[data-reportar-general]').addEventListener('click', () => {
        ventaInput.value = '';
        productoInput.value = '';
        selectPrenda.value = '';
        tipo.value = 'QUEJA_GENERAL';
        tipo.dispatchEvent(new Event('change'));
        modal.style.display = 'block';
        window.scrollTo({ top: modal.offsetTop - 40, behavior: 'smooth' });
    });
    document.getElementById('cerrarModal').addEventListener('click', () => { modal.style.display = 'none'; });
})();
