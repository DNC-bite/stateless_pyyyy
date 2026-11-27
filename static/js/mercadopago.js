(function () {
    function cookie(name) {
        const part = document.cookie.split('; ').find(item => item.startsWith(name + '='));
        return part ? decodeURIComponent(part.split('=')[1]) : '';
    }

    window.iniciarPagoMercadoPago = async function (url, ventaId) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': cookie('csrftoken'),
            },
            body: JSON.stringify({ venta_id: Number(ventaId) }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'No se pudo iniciar el pago.');
        if (!data.checkout_url) throw new Error('Mercado Pago no devolvió la URL de pago.');
        return data;
    };

    document.querySelectorAll('[data-pago-mp]').forEach(button => {
        button.addEventListener('click', async () => {
            const error = document.getElementById('error-pago-mp');
            button.disabled = true;
            button.textContent = 'Conectando con Mercado Pago...';
            error.textContent = '';
            try {
                const payment = await window.iniciarPagoMercadoPago(button.dataset.url, button.dataset.ventaId);
                window.location.href = payment.checkout_url;
            } catch (exception) {
                error.textContent = exception.message;
                button.disabled = false;
                button.textContent = 'Reintentar pago con Mercado Pago';
            }
        });
    });
})();
