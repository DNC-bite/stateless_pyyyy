/* Mapa de confirmación de la dirección de entrega (OpenStreetMap + Leaflet). */
(function () {
    const caja = document.getElementById('map-box');
    if (!caja || !window.L) return;
    const estado = document.getElementById('map-status');
    const direccion = caja.dataset.direccion || '';
    const ciudad = caja.dataset.ciudad || '';
    const departamento = caja.dataset.departamento || '';

    const mapa = L.map('map-box').setView([4.6, -74.1], 5);   // vista general de Colombia, sin pin hasta ubicar algo
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap' }).addTo(mapa);

    async function buscar(texto) {
        const url = 'https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=co&q=' + encodeURIComponent(texto);
        const resp = await fetch(url, { headers: { 'Accept-Language': 'es' } });
        const datos = await resp.json();
        return datos && datos.length ? datos[0] : null;
    }

    (async () => {
        try {
            // Solo la parte principal de la dirección (sin torre/apartamento) y "#" como "No." para OpenStreetMap.
            const calle = direccion.replace(/#/g, 'No.').trim();
            let hallado = await buscar([calle, ciudad, departamento, 'Colombia'].filter(Boolean).join(', '));
            if (hallado) {
                const p = [parseFloat(hallado.lat), parseFloat(hallado.lon)];
                mapa.setView(p, 16);
                L.marker(p).addTo(mapa).bindPopup('<b>Destino de entrega:</b><br>' + direccion.replace(/</g, '&lt;') + '<br><i>' + ciudad.replace(/</g, '&lt;') + '</i>').openPopup();
                estado.textContent = '📍 Casa ubicada exitosamente';
                return;
            }
            hallado = await buscar([ciudad, departamento, 'Colombia'].filter(Boolean).join(', '));
            if (hallado) {
                mapa.setView([parseFloat(hallado.lat), parseFloat(hallado.lon)], 12);
                estado.textContent = '📍 Ubicación aproximada: ' + ciudad;
                return;
            }
            estado.textContent = '📍 No pudimos ubicar la dirección en el mapa';
        } catch (e) {
            estado.textContent = '📍 Destino: ' + ciudad;
        }
    })();
})();
