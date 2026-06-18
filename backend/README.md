# Coffee XRPL — Signing Backend

Proxy ligero entre las apps de escritorio y la API de Xaman (XUMM).
Guarda el `XUMM_APISECRET` en el servidor — nunca en el `.exe` repartido.

## Responsabilidades

- Crear sign requests (payloads) en Xaman
- Devolver QR + deeplink al desktop
- Sondear estado de firma y devolver resultado
- Guardar `user_token` por operador para notificaciones push
- Autenticar instalaciones autorizadas con device API keys

## Requisitos

Python 3.11+ y las dependencias de `requirements.txt`.

## Configuración

Crear `backend/.env` a partir de `.env.example`:

```
XUMM_APIKEY=<tu key pública de Xaman Developer Console>
XUMM_APISECRET=<tu secret privado — NUNCA al repo>
DATABASE_URL=sqlite:///./backend.db
```

Obtener credenciales en: https://apps.xaman.dev

## Arrancar en desarrollo

```bash
cd coffee_xrpl_platform/backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

## Despliegue en producción

Cualquier PaaS que soporte Python (Railway, Render, Fly.io):

1. Configurar las variables de entorno (`XUMM_APIKEY`, `XUMM_APISECRET`, `DATABASE_URL`).
2. El PaaS gestiona HTTPS automáticamente.
3. Comando de inicio: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
4. Costo estimado: ~$5–10 USD/mes en el tier gratuito/básico.

**Punto único de falla:** si el backend cae, los pagos no se pueden firmar.
Mitigación: configurar healthcheck en el PaaS y alertas de uptime.

## Emitir device API keys

Por cada instalación autorizada, ejecutar desde la raíz del proyecto:

```bash
python -m backend.issue_device_key --username <username_del_operador> --label "Oficina Chiapas"
```

La clave se imprime UNA sola vez. Entregarla al operador para que la pegue
en el diálogo de Ajustes de la app de pagos.

## Seguridad

- El `XUMM_APISECRET` vive solo aquí (env var del servidor).
- Las device keys se almacenan como SHA-256; no son recuperables.
- El seed/llave privada del operador nunca llega al backend — vive solo en Xaman.
- Para revocar un dispositivo: `UPDATE devices SET is_active=0 WHERE id=<id>`.
