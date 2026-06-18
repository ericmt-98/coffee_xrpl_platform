# Plan de Implementación — Integración de Billetera Xaman (XUMM)

**Origen:** Decisión de producto (2026-06-17). Sustituir la firma por seed por firma remota con la app Xaman.
**Ejecutor previsto:** Claude (Sonnet). Documento autocontenido; no requiere leer otra conversación.
**Concepto:** El operador deja de teclear su seed en la plataforma. En su lugar, el programa pide una firma y el operador la aprueba **en su teléfono** con la app Xaman. La llave privada nunca toca el software. Un **backend propio** guarda el secreto de la API de Xaman; el `.exe` repartido nunca lo contiene.

---

## Arquitectura elegida (leer antes de todo)

Se evaluaron cuatro modelos. Se eligió **backend central** por robustez y porque es el cimiento del crecimiento futuro (SPEI, banca, webhooks):

```
  .exe del operador            Backend propio (guarda el Secret)         Xaman (XRPL Labs)
        │                              │                                       │
        │  POST /sign-requests ──────▶ │  sdk.payload.create(...) ───────────▶ │
        │  ◀── {uuid, qr, deeplink} ── │                                       │
        │                              │                          (operador firma en su teléfono)
        │  GET /sign-requests/{uuid} ▶ │  sdk.payload.get(uuid) ─────────────▶ │
        │  ◀── {signed, txid, acct} ── │                                       │
```

**Invariantes de seguridad — no violar:**
- **I1.** El `XUMM_APISECRET` vive SOLO en el backend (variable de entorno). Nunca en el `.exe`, nunca en el repo, nunca en logs.
- **I2.** El **seed / llave privada del operador NUNCA** llega al backend ni al `.exe`. Vive solo en el teléfono, dentro de Xaman. El backend solo recibe transacciones SIN firmar y devuelve hashes de transacciones YA firmadas.
- **I3.** Cada `.exe` se autentica ante el backend con una **API key de dispositivo** (Bearer token) emitida por el administrador, guardada localmente cifrada. Sin key válida, el backend rechaza.
- **I4.** El backend verifica que la cuenta que firmó coincide con la dirección XRPL registrada del operador antes de aceptar el resultado (evita firmar con otra wallet).

---

## Prerrequisitos

1. **Reglas generales del proyecto** (de `PLAN_IMPLEMENTACION.md`): UI en español; docstrings/comentarios en inglés; estilo PySide6 existente con `get_session()`/`close_session()` en try/finally; un commit por tarea con mensaje en español; verificación por fase (`pytest tests/ -v` + humo de ambas apps).
2. **No romper lo que funciona durante la migración.** El camino de seed se mantiene operativo hasta que el camino Xaman esté probado en testnet (Fase X4). La eliminación del seed es la última tarea (X7).
3. **Cuenta de desarrollador Xaman.** Antes de la Fase X0 hay que registrar UNA app en el Developer Console de Xaman (https://apps.xaman.dev) y obtener `API Key` (pública) + `API Secret` (privada). Si no hay acceso, documentar en `backend/README.md` los pasos y dejar el spike con `pytest.mark.skipif` cuando falten credenciales.
4. **Dependencias nuevas:**
   - Backend: `fastapi`, `uvicorn[standard]`, `xumm` (paquete `xumm-sdk-py`), `pydantic`, `python-dotenv`. Van en `backend/requirements.txt` (SEPARADO del `requirements.txt` raíz — el backend se despliega aparte).
   - Desktop: `requests` (cliente HTTP hacia el backend) y `qrcode`/`Pillow` solo si hiciera falta render local; preferir descargar el `qr_png` que ya da Xaman. Añadir `requests` a `requirements.txt` raíz si no está.

---

## Decisiones de Diseño (D)

### D1. El backend es delgado: solo proxy de firma + auth + tokens
El backend NO genera mensajes ISO 20022 ni guarda pagos (eso sigue en la app de escritorio y su SQLite local, como hoy). El backend solo: (a) crea sign requests en Xaman, (b) consulta su estado, (c) autentica dispositivos, (d) guarda el `user_token` de cada operador para push. Esto mantiene el alcance acotado y la separación limpia. La centralización de datos de pago es trabajo de la era SPEI (ver apéndice), no de este plan.

### D2. Polling, no websocket (v1)
La app de escritorio consulta `GET /sign-requests/{uuid}` cada ~2 s desde un `FunctionWorker` (QThread) hasta que el estado sea `signed`/`cancelled`/`expired` o se agote el timeout (5 min). Es más robusto en Qt que el websocket de Xaman. El `subscribe` por websocket queda como mejora futura (anotarlo, no implementarlo).

### D3. Red testnet — VERIFICAR EN EL SPIKE
Xaman firma sobre la red en la que esté la cuenta del operador. Para testnet, el operador debe tener una cuenta de **Testnet** activa en su Xaman. El spike X0 DEBE confirmar el mecanismo exacto (cuenta testnet en la app y/o opción `force_network` en el payload, según la versión de la API). No avanzar a X4 sin esto resuelto. Mantener `TESTNET_URL` y el explorador testnet de `core/xrpl_client.py`.

### D4. Push notifications con `user_token` (mejora de UX progresiva)
La primera vez que un operador firma (o hace Sign In), Xaman devuelve un `issued_user_token`. El backend lo guarda asociado al operador. En las siguientes solicitudes, el backend incluye `user_token` en el payload → el operador recibe una **notificación push** directa en su teléfono en vez de escanear un QR. Si no hay token (primer uso), se cae al QR. Se implementa en X6 pero el modelo de datos lo contempla desde X1.

### D5. Migración sin big-bang
Orden: backend (X1) → cliente + diálogo de firma (X2) → Sign In en login (X3) → pago directo (X4) → escrow (X5) → push (X6) → quitar seed + cierre (X7). Hasta X7 conviven ambos caminos detrás de una bandera de configuración `USE_XAMAN` (en la config local). Esto permite probar en testnet sin dejar la app inutilizable.

### D6. Escrow vía Xaman necesita el `Sequence` post-firma
Hoy `create_escrow` obtiene el `offer_sequence` de la respuesta del `submit_and_wait`. Con Xaman, el operador firma el `EscrowCreate` y solo recibimos el `txid`. El `offer_sequence` es el `Sequence` de cuenta de esa transacción: se obtiene consultando la tx ya validada (`XRPLClient.verify_transaction` extendido para devolver `Sequence`, o `sdk.get_transaction` en el backend). El `EscrowFinish`/`EscrowCancel` también pasan a ser sign requests. Por su complejidad, el escrow va en su propia fase (X5), después de que el pago directo funcione.

### D7. Almacenamiento local de configuración (cifrado)
El `.exe` necesita guardar: `backend_url`, `device_api_key`, y la bandera `USE_XAMAN`. Se guardan **cifrados en reposo** reutilizando `core/security.py::encrypt_data` + `get_or_create_encryption_key` (ya existen en el proyecto). Nueva tabla `AppConfig` (clave/valor) en el SQLite local, o un archivo `config.enc`. Preferir tabla `AppConfig` por consistencia con el ORM. El administrador captura estos valores una vez en un diálogo de Ajustes (X2.3).

---

## FASE X0 — Spike Técnico (de-risk, standalone, sin tocar la app)

**Objetivo:** Probar el ciclo completo de firma con Xaman antes de construir nada. Crear `scripts/spike_xaman.py` (no importa nada de la app, lee credenciales de `.env`):

1. `sdk = xumm.XummSdk(apikey, apisecret)`; `sdk.ping()` → confirmar credenciales válidas e imprimir el nombre de la app.
2. **Sign In:** crear payload `{"txjson": {"TransactionType": "SignIn"}}`. Imprimir `payload.refs.qr_png` (URL) y `payload.next.always` (deeplink). Escanear con Xaman. Hacer polling con `sdk.payload.get(uuid)` hasta `meta.signed`. Imprimir `response.account` (la dirección que firmó) y `application.issued_user_token`.
3. **Pago testnet:** crear payload de `Payment` por 1 XRP a una segunda cuenta testnet, con `options.submit=True` y `expire=5`. Polling hasta firmar. Imprimir `response.txid` y la URL del explorador testnet. Verificar la tx en el ledger.
4. **Confirmar red:** validar que la firma se hizo en TESTNET (D3). Documentar en comentarios EXACTAMENTE cómo se forzó/seleccionó testnet.
5. **Rechazo:** crear otro payload y rechazarlo en el teléfono; confirmar que el polling reporta `meta.cancelled`.
6. **Expiración:** crear un payload con `expire=1` y no firmarlo; confirmar `meta.expired` tras el minuto.

**Criterio de aceptación:** el script corre de punta a punta en testnet (sign in, pago firmado y verificado, rechazo y expiración detectados). Si algo falla (especialmente la red testnet, D3), resolver aquí. Dejar el script en `scripts/` como material educativo, igual que `spike_escrow.py`.

---

## FASE X1 — Backend de Firma

Crear directorio `backend/` (deployable independiente):

```
backend/
├── app.py              # FastAPI: endpoints
├── xumm_service.py     # wrapper sobre xumm-sdk-py
├── auth.py             # validación de device API keys (Bearer)
├── models.py           # SQLAlchemy: Device, OperatorToken, SignRequestLog
├── database.py         # sesión SQLite del backend
├── config.py           # carga de env (.env): XUMM_APIKEY, XUMM_APISECRET, DB_URL
├── requirements.txt
├── .env.example        # plantilla SIN valores reales
└── README.md           # despliegue, variables de entorno, cómo emitir device keys
```

### X1.1 Servicio Xaman (`xumm_service.py`)
```python
import os, xumm

_sdk = xumm.XummSdk(os.environ["XUMM_APIKEY"], os.environ["XUMM_APISECRET"])

def create_sign_request(txjson: dict, *, identifier: str, instruction: str,
                        user_token: str | None = None, expire_minutes: int = 5) -> dict:
    """Create a Xaman payload. Returns uuid, qr_png, deeplink, pushed."""
    payload = {
        "txjson": txjson,
        "options": {"submit": True, "expire": expire_minutes},
        "custom_meta": {"identifier": identifier, "instruction": instruction},
    }
    if user_token:
        payload["user_token"] = user_token
    created = _sdk.payload.create(payload)
    return {
        "uuid": created.uuid,
        "qr_png": created.refs.qr_png,
        "deeplink": created.next.always,
        "pushed": bool(getattr(created, "pushed", False)),
    }

def get_sign_request(uuid: str) -> dict:
    """Poll a payload. Returns resolved/signed/cancelled/expired, txid, account, issued_user_token."""
    p = _sdk.payload.get(uuid)
    return {
        "resolved": p.meta.resolved,
        "signed": p.meta.signed,
        "cancelled": p.meta.cancelled,
        "expired": p.meta.expired,
        "txid": p.response.txid,
        "account": p.response.account,
        "issued_user_token": getattr(p.application, "issued_user_token", None),
    }
```
*(Los nombres exactos de atributos los confirma el spike X0; ajustar si difieren.)*

### X1.2 Modelos del backend (`models.py`)
- `Device`: `id`, `api_key_hash` (hash Argon2 de la device key — nunca en claro), `operator_username`, `label`, `is_active`, `created_at`.
- `OperatorToken`: `id`, `operator_username` (unique), `user_token`, `xrpl_address`, `updated_at`. (Para push, D4.)
- `SignRequestLog`: `id`, `uuid`, `operator_username`, `identifier` (UETR), `kind` (`signin`/`payment`/`escrow_create`/...), `status`, `txid`, `created_at`, `resolved_at`. (Auditoría del backend.)
- DB SQLite del backend con `create_all` (separada de la del desktop).

### X1.3 Auth de dispositivos (`auth.py`)
- Dependencia FastAPI que lee `Authorization: Bearer <device_api_key>`, hashea y compara contra `Device.api_key_hash` (Argon2, reutilizar enfoque de `core/security.py`), valida `is_active`. Devuelve el `Device` o lanza `401`.
- Script `backend/issue_device_key.py`: genera una device key aleatoria (`secrets.token_urlsafe(32)`), la asocia a un operador, guarda su hash, e imprime la key UNA sola vez (para entregarla al operador). Esto resuelve I3.

### X1.4 Endpoints (`app.py`)
- `GET /health` → `{"status": "ok"}` (sin auth).
- `POST /sign-requests` (auth) — body: `{txjson, identifier, instruction, kind}`. Si hay `OperatorToken` para el operador del device, pásalo como `user_token`. Registra en `SignRequestLog`. Devuelve `{uuid, qr_png, deeplink, pushed}`.
- `GET /sign-requests/{uuid}` (auth) — llama `get_sign_request`. Si `signed` y hay `issued_user_token`, hace upsert en `OperatorToken`. Actualiza `SignRequestLog`. **Verifica I4 NO aquí** sino en el cliente (el cliente conoce la dirección esperada); el backend devuelve `account` y el cliente compara. Devuelve el dict de estado.
- (Opcional, anotar como futuro) `POST /webhooks/xumm` para actualizaciones push de Xaman; en v1 basta el polling.
- CORS innecesario (no es navegador). Forzar HTTPS en despliegue.

### X1.5 Despliegue (`README.md`)
- Correr local: `uvicorn app:app --reload`.
- Producción: VPS o PaaS (Railway/Render/Fly.io). Variables `XUMM_APIKEY`, `XUMM_APISECRET`, `DB_URL`. HTTPS gestionado por la plataforma. Documentar costo aproximado (~$5–10 USD/mes) y que sin el backend arriba no se pueden firmar pagos (punto único de falla — anotar mitigación futura: réplica/healthcheck).

**Tests X1:** con `TestClient` de FastAPI y el SDK de Xaman *mockeado*: `/health`; rechazo sin Bearer (401); `/sign-requests` con device válido devuelve la forma esperada; el upsert de `OperatorToken` ocurre cuando llega `issued_user_token`.

---

## FASE X2 — Cliente Desktop, Config y Diálogo de Firma

### X2.1 Cliente HTTP (`core/xaman_client.py`)
```python
import requests

class XamanClient:
    """Talks to the SIGNING BACKEND (never to Xaman directly, never sees the secret)."""
    def __init__(self, base_url: str, device_api_key: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {device_api_key}"}
        self.timeout = timeout

    def create_sign_request(self, txjson: dict, *, identifier: str,
                            instruction: str, kind: str) -> dict:
        r = requests.post(f"{self.base_url}/sign-requests",
                          json={"txjson": txjson, "identifier": identifier,
                                "instruction": instruction, "kind": kind},
                          headers=self._headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()   # {uuid, qr_png, deeplink, pushed}

    def get_sign_status(self, uuid: str) -> dict:
        r = requests.get(f"{self.base_url}/sign-requests/{uuid}",
                         headers=self._headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()   # {resolved, signed, cancelled, expired, txid, account, ...}
```

### X2.2 Almacenamiento de configuración (D7)
- `core/models.py` → tabla `AppConfig(key: String unique, value_encrypted: String)`.
- Helpers en `core/config_store.py`: `set_config(key, value)` (cifra con `encrypt_data`), `get_config(key)` (descifra), para `backend_url`, `device_api_key`, `use_xaman` (`"1"/"0"`).
- Migración: tabla nueva sale con `create_all`; documentar.

### X2.3 Diálogo de Ajustes (`admin_app` y/o pantalla inicial de `payment_app`)
- Formulario: URL del backend, device API key (campo password con 👁 mostrar, mismo patrón que el seed actual en `auth_flow.py:186`), checkbox "Usar Xaman para firmar". Botón "Probar conexión" → llama `GET /health`. Guardar con `set_config`. Registrar en AuditLog.

### X2.4 Diálogo de firma reutilizable (`payment_app/ui_payment/xaman_sign_dialog.py`)
Componente central que TODO flujo de firma usará:
- Entrada: `XamanClient`, `txjson`, `identifier` (UETR), `instruction` (texto humano: "Pago de $X a Productor Y"), `expected_account` (para I4), `kind`.
- Al abrir: `create_sign_request(...)`. Si `pushed` → muestra "📲 Revisa tu teléfono"; siempre muestra también el **QR** (descargar `qr_png` con `requests` → `QPixmap`) y un botón "Abrir en Xaman" (deeplink).
- Polling en `FunctionWorker` (D2) cada 2 s; barra/spinner indeterminado; timeout 5 min.
- Resuelve con: `signed` (+ valida `account == expected_account`, I4; si no coincide → error y trata como fallo), `cancelled`, `expired`, `timeout`, o error de red.
- Devuelve `{"ok": bool, "txid": str|None, "account": str|None, "reason": str}`.
- Estilo y textos en español; reutilizar `StepIndicator`/toasts donde aplique.

**Tests X2:** `XamanClient` con `requests` mockeado (forma de payloads y headers); `config_store` roundtrip cifrado/descifrado; lógica de resolución del diálogo separada de Qt en una función pura testeable (`resolve_status(dict, expected_account) -> result`).

---

## FASE X3 — Conectar Wallet vía Xaman (login)

Reemplazar el **Paso 3 (seed)** de `auth_flow.py` cuando `use_xaman == "1"`:
- Título del paso: "Paso 3 de 3: Conectar Wallet (Xaman)". Quitar el campo de seed y la advertencia de RAM; poner texto: "Escanee el código con su app Xaman para conectar su wallet. Su llave privada nunca sale de su teléfono."
- Botón "🔗 Conectar con Xaman" → abre `XamanSignDialog` con `txjson={"TransactionType": "SignIn"}`, `kind="signin"`, `expected_account=self.user_xrpl_address` (la registrada).
- Si `ok` y `account == user_xrpl_address`: login exitoso. Ya **no se guarda seed**; en su lugar se construye un `XamanClient` (desde la config) que se pasará al dashboard. AuditLog "Inicio de sesión en Pagos (Xaman)".
- Si `account` no coincide con la registrada: mismo mensaje de "Dirección No Coincide" que hoy (`auth_flow.py:430`).
- `closeEvent`: ya no hay seed que limpiar en este camino (mantener limpieza del seed para el camino legacy mientras coexista).
- **Compat:** si `use_xaman == "0"`, conservar el flujo de seed actual intacto.

### X3.1 Cableado (`main_payment.py`)
- Tras autenticar, si Xaman: construir `XamanClient` con `get_config("backend_url"/"device_api_key")` y pasar `PaymentDashboard(user, xaman_client=...)` en vez de `seed`. Cambiar firmas de `PaymentDashboard` y `PaymentFlowWidget` para aceptar `xaman_client` (y dejar `xrpl_seed=None` opcional mientras coexisten).

---

## FASE X4 — Pago Directo vía Xaman

En `payment_flow.py`, cuando `use_xaman` y modo directo:
- En vez de `_do_payment` con `send_xrp_payment(seed,...)`:
  1. Validar saldo (la verificación previa de saldo sigue usando `XRPLClient.get_balance` sobre la dirección del operador — eso es solo lectura, no necesita firma).
  2. Construir el `txjson` del `Payment` (Destination = dirección del productor, Amount = drops vía `xrpl.utils.xrp_to_drops`, Memos con el UETR — replicar lo que hoy arma `send_xrp_payment`). **Solo XRP** dispara firma Xaman; los tokens "Simulado" siguen el camino simulado actual sin firma.
  3. Abrir `XamanSignDialog` con ese `txjson`, `instruction=f"Pago de {format_currency(total_mxn,'MXN')} a {productor}"`, `expected_account=operator_address`, `kind="payment"`.
  4. Si `ok`: tomar `txid` como `xrpl_tx_hash` y persistir EXACTAMENTE igual que hoy (Payment COMPLETED + Delivery + pacs.008 + camt.054 + AuditLog). Reusar el bloque de `_do_payment` desde `session = _gs()` en adelante, recibiendo `tx_hash` ya resuelto.
  5. Si `cancelled`/`expired`/`timeout`/error: no guardar el pago; mensaje claro ("El operador no firmó la transacción"). Opcional: registrar "Pago no firmado" en AuditLog.
- El diálogo de firma ya corre su propio polling en hilo; el `QProgressDialog` actual se sustituye por el diálogo Xaman. Mantener `pay_button` deshabilitado mientras está abierto.

**Verificación X4:** humo en testnet — pago XRP real firmado desde el teléfono, aparece en historial con su `txid`, explorador y mensajes ISO en la DB. Este es el hito que valida toda la arquitectura.

---

## FASE X5 — Escrow vía Xaman (depende de X4 y de D6)

Migrar los tres pasos de escrow de `payment_flow.py::_execute_escrow_payment` y `escrow_view.py`:
- **EscrowCreate:** construir `txjson` (EscrowCreate con `Condition`, `CancelAfter` vía `datetime_to_ripple_time`, Memos) → `XamanSignDialog` → al firmar, `txid`. Obtener el `offer_sequence`:
  - Extender `XRPLClient.verify_transaction` (o nuevo `get_tx_sequence(txid)`) para devolver el `Sequence` de la tx validada. Hacer polling breve hasta que la tx esté validada (puede tardar unos segundos tras la firma).
  - Persistir `EscrowDetail` con ese `offer_sequence` (resto igual que hoy).
- **EscrowFinish / EscrowCancel** (en `escrow_view.py`): cada acción construye su `txjson` y se firma con `XamanSignDialog`. `EscrowFinish` lleva `Owner`, `OfferSequence`, `Condition`, `Fulfillment`. Tras firmar, actualizar `EscrowDetail`/estado igual que el flujo actual.
- Mantener el mapeo ISO 20022 de `PLAN_ESCROW.md` intacto (la firma cambia, no los mensajes).

**Verificación X5:** ciclo escrow completo en testnet firmado con Xaman (crear → aprobar/liberar; crear → rechazar → reembolsar con ventana corta).

---

## FASE X6 — Push Notifications (mejora de UX, D4)

- El backend ya captura y guarda `issued_user_token` (X1.4). Confirmar que en `POST /sign-requests` se incluye `user_token` cuando existe para ese operador.
- En el `XamanSignDialog`, si la respuesta de creación trae `pushed=True`, mostrar primero "📲 Aprueba la solicitud en tu teléfono" y el QR como alternativa (por si el push no llega).
- Resultado: tras el primer Sign In, los pagos siguientes llegan como notificación push — sin escanear QR cada vez.

**Tests X6:** el backend incluye `user_token` en el payload cuando hay `OperatorToken` (con SDK mockeado, verificar el dict pasado a `create`).

---

## FASE X7 — Quitar el Seed, Tests y Cierre

### X7.1 Eliminar el camino de seed (una vez X4/X5 probados en testnet)
- `auth_flow.py`: borrar Paso 3 de seed, `validate_xrpl_seed`, `get_wallet_from_seed` en login, y el almacenamiento de `self.xrpl_seed`.
- `payment_flow.py`: borrar `xrpl_seed`, el branch de `send_xrp_payment(seed,...)` y los `sender_seed=` de escrow.
- `main_payment.py`: quitar `xrpl_seed` de la firma de `PaymentDashboard`.
- `core/xrpl_client.py`: `send_xrp_payment`, `create_escrow`, `finish_escrow`, `cancel_escrow` ya no se usan para firmar desde la app. Decidir: dejarlos para `scripts/` educativos (marcar docstring "legacy: server-side signing, not used by the app") o eliminarlos. Conservar `get_balance`, `verify_transaction`, `validate_xrpl_address`, explorador.
- `core/security.py::validate_xrpl_seed`: eliminar si nadie la usa (verificar con grep).
- Quitar la bandera `USE_XAMAN` (ya es el único camino) o dejarla en `"1"` fija.

### X7.2 Tests finales
- `pytest tests/ -v` en verde, incluyendo los nuevos: `xaman_client`, `config_store`, `resolve_status`, y backend (`backend/tests/`).
- Ajustar/eliminar tests que dependían del seed.

### X7.3 Documentación
- `README.md`: nueva sección "Firma con Xaman" — explicar que la llave nunca toca el software, el rol del backend, y el diagrama de arquitectura de arriba. Actualizar requisitos (el operador necesita la app Xaman con una cuenta testnet) y pasos de configuración (URL backend + device key).
- `backend/README.md`: despliegue completo y emisión de device keys.
- `QUICKSTART.md`: nuevas dependencias y el paso de configurar el backend.
- `AUDITORIA.md`: nota de que la firma por seed (riesgo de manejo de llave privada) queda resuelta por diseño.

---

## Resumen de Secuencia

| Fase | Contenido | Riesgo | Dependencia |
|------|-----------|--------|-------------|
| X0 | Spike testnet: ciclo de firma Xaman + red testnet | Alto (por eso va primero) | Credenciales Xaman |
| X1 | Backend FastAPI: proxy de firma, auth de dispositivos, tokens | Medio | X0 |
| X2 | Cliente HTTP, config cifrada, diálogo de firma reutilizable | Medio | X1 |
| X3 | Sign In en el login (conectar wallet) | Bajo | X2 |
| X4 | Pago directo vía Xaman (hito que valida todo) | Medio | X2, X3 |
| X5 | Escrow vía Xaman (create/finish/cancel) | Medio-alto | X4, D6 |
| X6 | Push notifications con user_token | Bajo | X1, X4 |
| X7 | Quitar seed, tests, docs, cierre | Bajo | Todo probado en testnet |

**Hito mínimo de valor:** completar X0–X4 entrega ya el beneficio central — el operador firma pagos directos desde su teléfono y su llave nunca toca el software. X5–X7 completan y endurecen.

---

## Apéndice — Camino a SPEI / Banca (NO implementar aquí)

Este backend es el cimiento de la visión fintech: una vez existe, agregar la integración SPEI es natural (webhooks del banco patrocinador, llamadas a la API del banco, conciliación de `camt.053`). Esos flujos requieren un servidor de todas formas y vivirían en este mismo backend (o un servicio hermano), reutilizando la auth de dispositivos y el patrón de proxy. El `pacs.008`/UETR que ya genera la plataforma es la pieza que ambos mundos comparten. Planificar por separado cuando haya cooperativa y banco patrocinador concretos.
```
