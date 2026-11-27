(function () {
    const form = document.getElementById('ai-style-form');
    const results = document.getElementById('ai-style-results');
    if (!form || !results) return;
    const formatoCOP = new Intl.NumberFormat('es-CO', {
        style: 'currency',
        currency: 'COP',
        maximumFractionDigits: 0
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const button = form.querySelector('button[type="submit"]');
        const question = form.querySelector('[name="request"]').value.trim();
        const csrf = form.querySelector('[name="csrfmiddlewaretoken"]').value;
        button.disabled = true;
        results.textContent = 'Consultando el catálogo y generando combinaciones...';

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ request: question })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'No se pudieron cargar las recomendaciones.');

            results.replaceChildren();
            if (!data.recommendations.length) {
                results.textContent = 'No encontramos otras prendas disponibles para recomendar en este momento.';
                return;
            }
            data.recommendations.forEach((item) => {
                const card = document.createElement('article');
                const link = document.createElement('a');
                const reason = document.createElement('p');
                link.href = item.url;
                link.textContent = `${item.name} · ${formatoCOP.format(Number(item.price))}`;
                reason.textContent = item.reason;
                card.append(link, reason);
                results.appendChild(card);
            });
        } catch (error) {
            results.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    });
})();
