(function () {
    const form = document.getElementById('checkoutForm');
    if (!form) return;
    const btn = document.getElementById('btnProcesar');
    const errorDiv = document.getElementById('error-msg');
    const urlProcesar = form.dataset.urlProcesar;
    const confirmationDialog = document.getElementById('confirmacionPago');
    const confirmButton = document.getElementById('confirmarPago');
    const cancelConfirmationButton = document.getElementById('cancelarConfirmacion');
    const textoBoton = 'Pagar ahora';
    let expressActivo = null;   // { metodo, nombre }

    const $ = id => document.getElementById(id);
    const metodoSeleccionado = () => (document.querySelector('input[name="metodo_pago"]:checked') || {}).value;

    function cookie(nombre) {
        const par = document.cookie.split('; ').find(c => c.startsWith(nombre + '='));
        return par ? decodeURIComponent(par.split('=')[1]) : '';
    }
    function mostrarError(texto) { errorDiv.textContent = texto; errorDiv.style.display = 'block'; }

    // ---- Pago exprés (Shop Pay, PayPal, Google Pay)
    document.querySelectorAll('.btn-express').forEach(b => b.addEventListener('click', () => {
        expressActivo = { metodo: b.dataset.metodo, nombre: b.dataset.nombre };
        document.querySelectorAll('.btn-express').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        btn.textContent = 'PAGAR CON ' + expressActivo.nombre.toUpperCase() + ' (' + $('total-val').textContent + ')';
        $('expressNoticeText').textContent = '✓ ' + expressActivo.nombre + ' activado. Haz clic en el botón inferior para confirmar.';
        $('expressNotice').style.display = 'flex';
        $('tarjetaFields').style.display = 'none';
    }));

    function cancelarExpress() {
        expressActivo = null;
        document.querySelectorAll('.btn-express').forEach(x => x.classList.remove('active'));
        $('expressNotice').style.display = 'none';
        $('rb_tarjeta').checked = true;
        $('tarjetaFields').style.display = 'block';
        btn.textContent = textoBoton;
    }
    $('expressReset').addEventListener('click', cancelarExpress);

    document.querySelectorAll('input[name="metodo_pago"]').forEach(r => r.addEventListener('change', () => {
        $('tarjetaFields').style.display = (r.value === 'tarjeta_credito' && r.checked) ? 'block' : 'none';
        if (expressActivo && r.value === 'tarjeta_credito') cancelarExpress();
    }));

    // ---- Formato de la tarjeta (solo en el navegador: estos datos NO se envían al servidor)
    const ccNum = $('cc_numero'), ccExp = $('cc_exp');
    ccNum.addEventListener('input', e => {
        const v = e.target.value.replace(/\D/g, '').substring(0, 16);
        e.target.value = (v.match(/.{1,4}/g) || []).join(' ');
    });
    ccExp.addEventListener('input', e => {
        const v = e.target.value.replace(/\D/g, '').substring(0, 4);
        e.target.value = v.length >= 2 ? v.substring(0, 2) + '/' + v.substring(2) : v;
    });

    function metodoActual() {
        return expressActivo ? expressActivo.metodo : metodoSeleccionado();
    }

    function mostrarConfirmacion(metodo) {
        const ubicacion = [
            $('ciudad').value.trim(),
            $('departamento').value.trim(),
            $('codigoPostal').value.trim(),
        ].filter(Boolean).join(' · ');
        const direccion = [
            $('direccion').value.trim(),
            $('apartamento').value.trim(),
        ].filter(Boolean).join(' · ');
        const nombreMetodo = {
            tarjeta_credito: 'Tarjeta de crédito / débito',
            paypal: 'PayPal / Billetera digital',
            shop_pay: 'Shop Pay',
            google_pay: 'Google Pay',
            mercado_pago: 'Mercado Pago · Sandbox',
        };

        $('confirmacionNombre').textContent = [$('nombre').value.trim(), $('apellidos').value.trim()].filter(Boolean).join(' ') || '—';
        $('confirmacionCorreo').textContent = $('email').value.trim() || '—';
        $('confirmacionDireccion').textContent = direccion || '—';
        $('confirmacionUbicacion').textContent = ubicacion || '—';
        $('confirmacionTelefono').textContent = $('telefono').value.trim() || '—';
        $('confirmacionMetodo').textContent = nombreMetodo[metodo] || metodo;
        $('confirmacionTotal').textContent = $('total-val').textContent.trim() + ' COP';

        const mercadoPago = metodo === 'mercado_pago';
        $('confirmacionSandbox').hidden = !mercadoPago;
        $('confirmarPago').textContent = mercadoPago
            ? 'Confirmar y continuar al sandbox'
            : 'Confirmar y continuar';
        confirmationDialog.showModal();
    }

    function validarTarjeta() {
        if (ccNum.value.replace(/\s/g, '').length !== 16) {
            mostrarError('❌ El número de tarjeta debe tener 16 dígitos.');
            ccNum.focus();
            return false;
        }
        if (ccExp.value.trim().length !== 5) {
            mostrarError('❌ Fecha de expiración inválida (MM/AA).');
            ccExp.focus();
            return false;
        }
        if ($('cc_cvv').value.trim().length < 3) {
            mostrarError('❌ Ingresa un CVV válido.');
            return false;
        }
        if ($('cc_titular').value.trim().length < 3) {
            mostrarError('❌ Ingresa el titular de la tarjeta.');
            return false;
        }
        return true;
    }

    async function enviarPedido() {
        errorDiv.style.display = 'none';
        const metodo = metodoActual();
        if (metodo === 'tarjeta_credito' && !validarTarjeta()) {
            confirmationDialog.close();
            return;
        }
        btn.disabled = true;
        btn.textContent = 'PROCESANDO TRANSACCIÓN...';
        const payload = {
            nombre: $('nombre').value, apellidos: $('apellidos').value,
            direccion: $('direccion').value, apartamento: $('apartamento').value,
            ciudad: $('ciudad').value, departamento: $('departamento').value,
            codigo_postal: $('codigoPostal').value, telefono: $('telefono').value,
            metodo_pago: metodo,
        };
        confirmationDialog.close();
        try {
            const resp = await fetch(urlProcesar, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cookie('csrftoken') },
                body: JSON.stringify(payload),
            });
            let data = {};
            try { data = await resp.json(); } catch (_) { /* respuesta sin JSON */ }
            if (resp.ok && data.redirect) { window.location.href = data.redirect; return; }
            if (data.redirect) { window.location.href = data.redirect; return; }
            mostrarError(data.error || 'No se pudo procesar el pago.');
        } catch (err) {
            mostrarError('Error de comunicación con el servidor. Revisa tu conexión.');
        }
        btn.disabled = false;
        btn.textContent = expressActivo ? 'PAGAR CON ' + expressActivo.nombre.toUpperCase() + ' (' + $('total-val').textContent + ')' : textoBoton;
    }

    // ---- Confirmación antes de procesar el pedido
    form.addEventListener('submit', e => {
        e.preventDefault();
        errorDiv.style.display = 'none';

        const metodo = metodoActual();
        mostrarConfirmacion(metodo);
    });

    confirmButton.addEventListener('click', enviarPedido);
    cancelConfirmationButton.addEventListener('click', () => confirmationDialog.close());
    confirmationDialog.addEventListener('click', event => {
        if (event.target === confirmationDialog) confirmationDialog.close();
    });
})();
