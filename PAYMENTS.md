# Mercado Pago

El checkout usa Mercado Pago Checkout Pro. Configura estas variables en el `.env` del proyecto:

```dotenv
MERCADOPAGO_ACCESS_TOKEN=
MERCADOPAGO_WEBHOOK_SECRET=
MERCADOPAGO_PUBLIC_URL=https://tu-dominio-publico
BASE_URL=https://tu-dominio-publico
```

Para usar SQLite en lugar del backend configurado por defecto, añade al `.env`:

```dotenv
DB_ENGINE=sqlite
DB_NAME=db.sqlite3
```

Esta configuración aplica a toda la aplicación (usuarios, pedidos y pagos). Después de
cambiar el backend, ejecuta `python manage.py migrate`.

Para probar el sandbox, deja `DEBUG=True` y usa el Access Token que Mercado Pago identifica
como credencial de prueba; no dependas del prefijo del token. En ese modo la
opción **Mercado Pago** del checkout redirige a `sandbox_init_point`; si Mercado Pago no
devuelve ese enlace, el pedido se revierte y no se usa el enlace de producción como alternativa.
Para cobros reales, configura `DEBUG=False` y credenciales de producción.

En Mercado Pago, registra como URL de notificaciones:
`https://tu-dominio-publico/api/payments/webhook/`.
El endpoint valida la firma del webhook y consulta el pago directamente en Mercado Pago antes
de confirmar la venta. En producción, configura un `MERCADOPAGO_WEBHOOK_SECRET` real y usa HTTPS.

Después de configurar las variables, ejecuta `python manage.py migrate`. En desarrollo,
`BASE_URL` puede apuntar a localhost para las redirecciones del checkout; una URL local de
webhook se omite automáticamente para permitir crear la preferencia, pero Mercado Pago no podrá
notificar el resultado y el pedido permanecerá pendiente. Para probar webhooks localmente,
configura `MERCADOPAGO_PUBLIC_URL` con una URL HTTPS pública (por ejemplo, un túnel de desarrollo).
