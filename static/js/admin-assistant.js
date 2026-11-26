(function () {
    const form = document.getElementById('assistant-form');
    const messages = document.getElementById('assistant-messages');
    if (!form || !messages) return;

    function addMessage(label, content, question) {
        const article = document.createElement('article');
        article.className = `assistant-message${question ? ' assistant-question' : ''}`;
        const heading = document.createElement('strong');
        const paragraph = document.createElement('p');
        heading.textContent = label;
        paragraph.textContent = content;
        article.append(heading, paragraph);
        messages.appendChild(article);
        article.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        return paragraph;
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const input = form.querySelector('[name="question"]');
        const button = form.querySelector('button[type="submit"]');
        const question = input.value.trim();
        if (!question) return;

        const empty = messages.querySelector('.assistant-empty');
        if (empty) empty.remove();
        addMessage('Tú', question, true);
        const answer = addMessage('STATELESS IA', 'Consultando los datos actuales...', false);
        input.value = '';
        button.disabled = true;

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value
                },
                body: JSON.stringify({ question })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'No se pudo completar la consulta.');
            answer.textContent = `${data.answer}\n\nDatos consultados: ${data.updated_at}`;
        } catch (error) {
            answer.textContent = error.message;
            answer.classList.add('assistant-error');
        } finally {
            button.disabled = false;
            input.focus();
        }
    });
})();
