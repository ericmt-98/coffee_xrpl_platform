# Plan de Implementación — Pago contra Calidad (Escrow XRPL)

**Origen:** Propuesta 8.9 derivada de la discusión de producto (2026-06-11). Ver `AUDITORIA.md` sección 8.
**Ejecutor previsto:** Claude (Sonnet). Documento autocontenido.
**Concepto:** Modo de pago opcional donde los fondos quedan bloqueados en un escrow nativo de XRPL al registrar la entrega, y se liberan al aprobar la calidad del lote. El mensaje ISO 20022 `pacs.002 ACSC` transporta el *fulfillment* criptográfico que desbloquea los fondos — el mensaje contiene literalmente la llave de liberación.

---

## Prerrequisitos (NO empezar sin esto)

1. **Fases 1, 2 y 3 de `PLAN_IMPLEMENTACION.md` completadas.** Este plan depende de:
   - Fase 1: validación criptográfica de direcciones, AuditLog en flujos de pago.
   - Fase 2: `Numeric` para montos, estados de pago ampliados, `datetime.now(timezone.utc)`.
   - Fase 3: generador `pacs.002` (sección 3.7) y validación XSD — el ciclo PDNG→ACSC/RJCT de este plan se construye encima.
2. **Aplican las Reglas Generales** de `PLAN_IMPLEMENTACION.md` (UI en español, estilo existente, commits por tarea, verificación por fase).
3. **Alcance: solo XRP.** El escrow clásico de XRPL es XRP-only. El escrow de tokens emitidos (XLS-85 TokenEscrow) queda fuera; documentarlo como limitación en docstrings.

---

## Decisiones de Diseño (leer antes de codificar)

### D1. Crypto-condición PREIMAGE-SHA-256, no solo tiempo
El escrow se crea con `Condition` (hash del preimage secreto) + `CancelAfter` (red de seguridad). La liberación requiere presentar el `Fulfillment`. Esto permite que el mensaje ISO sea el portador de la llave (ver D3).

### D2. La ventana de calidad ES el `CancelAfter` — regla de XRPL crítica
**`EscrowCancel` solo es válido DESPUÉS de `CancelAfter`; `EscrowFinish` solo ANTES.** No se puede "cancelar anticipadamente" un escrow en XRPL. Implicaciones de diseño:
- Aprobar calidad → `EscrowFinish` en cualquier momento dentro de la ventana.
- Rechazar calidad → se marca el pago como `REJECTED` en la DB de inmediato, pero el **reembolso on-ledger** (`EscrowCancel`) solo se puede ejecutar cuando venza la ventana. La UI debe comunicar esto claramente ("Reembolso disponible a partir de \<fecha\>").
- Ventana por defecto: **48 horas** (configurable 1h–7 días en la UI). Corta = reembolsos rápidos; larga = más margen para inspección.
- Si el fulfillment se pierde (DB corrupta), los fondos regresan solos al vencer la ventana. Red de seguridad por diseño — documentar.

### D3. El fulfillment viaja en el pacs.002 ACSC
Al aprobar calidad, el `pacs.002` con `TxSts=ACSC` incluye en `SplmtryData/Envlp` el elemento `<EscrowFulfillment>` con el preimage en hex. Publicado el mensaje, **cualquiera** puede ejecutar el `EscrowFinish` (XRPL permite que cualquier cuenta lo envíe; los fondos solo pueden ir al destino original — es seguro). En la práctica lo envía la plataforma con la wallet del operador, pero el diseño demuestra el concepto: el mensaje ISO desbloquea los fondos.

### D4. Codificación de la condición sin dependencias nuevas
No agregar la librería `cryptoconditions` (sin mantenimiento, riesgo en Python 3.13). Para preimages de exactamente 32 bytes, la estructura DER de PREIMAGE-SHA-256 es fija:

```python
import os, hashlib

def generate_escrow_condition() -> tuple[str, str]:
    """Generate a PREIMAGE-SHA-256 crypto-condition pair for XRPL escrow.
    Returns (condition_hex, fulfillment_hex). Preimage is 32 random bytes.
    DER layout (fixed for 32-byte preimages):
      condition   = A0 25 80 20 <sha256(preimage)> 81 01 20
      fulfillment = A0 22 80 20 <preimage>
    """
    preimage = os.urandom(32)
    condition = bytes.fromhex("A0258020") + hashlib.sha256(preimage).digest() + bytes.fromhex("810120")
    fulfillment = bytes.fromhex("A0228020") + preimage
    return condition.hex().upper(), fulfillment.hex().upper()
```

⚠️ **Esta codificación DEBE verificarse contra testnet en la Fase E0 antes de construir nada encima.** Si el spike falla, alternativa: librería `cryptoconditions` con pin de versión.

### D5. Estados del ciclo de vida
Añadir a `PaymentStatus`: `ESCROWED` (bloqueado, en ventana de calidad), `REJECTED` (calidad rechazada, esperando vencimiento para reembolso), `REFUNDED` (EscrowCancel ejecutado). `COMPLETED` se reutiliza para escrow liberado.

```
              ┌─ aprobar calidad ──► COMPLETED   (EscrowFinish + pacs.002 ACSC)
ESCROWED ─────┤
              └─ rechazar ─► REJECTED ─ vence ventana ─► REFUNDED   (EscrowCancel + pacs.002 RJCT)
```

---

## FASE E0 — Spike Técnico en Testnet (de-risk, sin tocar la app)

**Objetivo:** Probar los primitivos antes de integrar. Crear `scripts/spike_escrow.py` (standalone, no importa nada de la app):

1. Generar dos wallets de testnet con el faucet (`xrpl.wallet.generate_faucet_wallet`).
2. Crear escrow condicional de 5 XRP con la condición de D4, `CancelAfter` = ahora + 10 min (usar `xrpl.utils.datetime_to_ripple_time` — XRPL usa época Ripple, segundos desde 2000-01-01, NO Unix).
3. Capturar del resultado: hash de la transacción y **`Sequence`** de la cuenta creadora (necesario como `offer_sequence` para finish/cancel).
4. Ejecutar `EscrowFinish` con `owner`, `offer_sequence`, `condition` y `fulfillment`. Verificar `tesSUCCESS` y que el saldo del destino aumentó 5 XRP.
5. Repetir creación y probar que `EscrowFinish` con fulfillment INCORRECTO falla.
6. Imprimir cada paso con los hashes y URLs del explorador.

**Criterio de aceptación de la fase:** el script corre de punta a punta en testnet con la codificación manual de D4. Si falla la condición, resolver ahí (no avanzar a E1 con el problema abierto). Dejar el script en `scripts/` como material educativo.

---

## FASE E1 — Núcleo: Cliente XRPL y Modelo de Datos

### E1.1 Métodos de escrow en `core/xrpl_client.py`
Añadir a `XRPLClient` (mismo estilo que `send_xrp_payment`: try/except, dict de retorno):

```python
def create_escrow(self, sender_seed, destination, amount_xrp,
                  condition_hex, cancel_after: datetime, memo=None) -> dict:
    """EscrowCreate. Returns {'hash', 'offer_sequence', 'validated', 'result'}."""

def finish_escrow(self, sender_seed, owner_address, offer_sequence,
                  condition_hex, fulfillment_hex) -> dict:
    """EscrowFinish. Returns {'hash', 'validated', 'result'}."""

def cancel_escrow(self, sender_seed, owner_address, offer_sequence) -> dict:
    """EscrowCancel. Only valid after CancelAfter. Returns {'hash', 'validated', 'result'}."""
```

Notas de implementación:
- Modelos: `xrpl.models.transactions.EscrowCreate/EscrowFinish/EscrowCancel`.
- `cancel_after` → `datetime_to_ripple_time(cancel_after)`.
- `offer_sequence` se extrae de la respuesta del EscrowCreate validado (`response.result["tx_json"]["Sequence"]` o `response.result["Sequence"]` según versión de xrpl-py — el spike E0 ya identificó cuál).
- El fee del EscrowFinish condicional es mayor (escala con el tamaño del fulfillment); `submit_and_wait` lo autocompleta — no hardcodear fees.
- Mover `generate_escrow_condition()` (D4) a `core/security.py`.

### E1.2 Modelo de datos
`core/models.py`:
- `PaymentStatus` → añadir `ESCROWED`, `REJECTED`, `REFUNDED` (D5).
- Nueva tabla:
  ```python
  class EscrowDetail(Base):
      __tablename__ = "escrow_details"
      id = Column(Integer, primary_key=True)
      payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, unique=True)
      offer_sequence = Column(Integer, nullable=False)
      condition_hex = Column(String(100), nullable=False)
      fulfillment_hex = Column(String(100), nullable=False)  # the release key; leaking it only allows paying the producer
      cancel_after = Column(DateTime, nullable=False)        # UTC
      create_tx_hash = Column(String(100), nullable=False)
      finish_tx_hash = Column(String(100), nullable=True)
      cancel_tx_hash = Column(String(100), nullable=True)
      quality_notes = Column(Text, nullable=True)            # approval/rejection reason
      resolved_at = Column(DateTime, nullable=True)
      payment = relationship("Payment", backref="escrow_detail")
  ```
- En `Payment`, `xrpl_tx_hash` guarda el hash del EscrowCreate (los de finish/cancel viven en EscrowDetail).
- Migración: tabla nueva sale gratis con `create_all`; valores nuevos del enum no requieren ALTER en SQLite (se guardan como texto). Documentar.

### E1.3 Verificación de saldo con reserva
El XRP en escrow sale del saldo del operador Y cada escrow suma reserva de objeto (~0.2 XRP) mientras existe. En la verificación previa al pago (tarea 4.1 del plan base), para modo escrow exigir `saldo >= monto + 1.5 XRP` de margen.

**Tests E1:** roundtrip de `generate_escrow_condition` (condición de 39 bytes, fulfillment de 34, hash correcto); creación de EscrowDetail en DB con todos los campos.

---

## FASE E2 — Integración ISO 20022

### E2.1 pacs.002 con fulfillment (extiende el generador de la Fase 3.7 del plan base)
- `generate_pacs002` acepta parámetro opcional `escrow_fulfillment: str = None`. Si se provee y `TxSts=ACSC`, añadir en `SplmtryData/Envlp`:
  ```xml
  <EscrowFulfillment>A0228020...</EscrowFulfillment>
  <EscrowReleaseNote>PREIMAGE-SHA-256 fulfillment - releases XRPL escrow via EscrowFinish</EscrowReleaseNote>
  ```
- Docstring explicando el concepto: el mensaje de estado del pago transporta la llave de liquidación.

### E2.2 Mapeo completo de eventos a mensajes
| Evento | Estado DB | Mensajes generados (todos a `IsoMessage`) |
|--------|-----------|-------------------------------------------|
| EscrowCreate validado | `ESCROWED` | `pacs.008` (instrucción) + `pacs.002 PDNG` |
| Calidad aprobada + EscrowFinish | `COMPLETED` | `pacs.002 ACSC` con fulfillment + `camt.054 CRDT` |
| Calidad rechazada | `REJECTED` | `pacs.002 RJCT` con `StsRsnInf/AddtlInf` = motivo de rechazo |
| EscrowCancel ejecutado | `REFUNDED` | `camt.054` con `CdtDbtInd=DBIT` reverso (notificación de devolución al operador) |

- En pacs.008 de pagos escrow, `SttlmInf/SttlmMtd` sigue siendo `CLRG`; añadir en `SplmtryData` el elemento `<XRPLEscrowSequence>` con el offer_sequence (trazabilidad mensaje↔objeto de ledger).

**Tests E2:** pacs.002 ACSC con fulfillment valida contra XSD (los elementos custom van en Envlp, que es de contenido abierto); RJCT incluye el motivo; mapeo de los 4 eventos genera los tipos correctos.

---

## FASE E3 — UI

### E3.1 Selector de modo en `payment_flow.py`
- En la sección "Ejecutar Pago XRPL", añadir radio buttons: `(•) Pago directo  ( ) Pago contra calidad (Escrow)`.
- Modo escrow **solo habilitado si currency == XRP** (deshabilitar y mostrar tooltip "Escrow disponible solo para XRP" en otros tokens).
- Al elegir escrow, mostrar combo "Ventana de calidad": 24h / 48h (default) / 72h / 7 días.
- `execute_payment` en modo escrow:
  1. Generar UETR + condición/fulfillment.
  2. `create_escrow(...)` con memo `f"Coffee Escrow - UETR: {uetr}"`.
  3. Guardar `Payment` (status `ESCROWED`) + `Delivery` + `EscrowDetail` + pacs.008 + pacs.002 PDNG en una sola transacción de DB.
  4. AuditLog: `"Pago en escrow creado"` con UETR y vencimiento.
  5. Mensaje de éxito explicando: fondos bloqueados, productor puede verificarlo en el explorador (incluir URL), liberar antes de \<fecha\> o se reembolsan.

### E3.2 Nueva pestaña "⏳ Escrows" (`payment_app/ui_payment/escrow_view.py`)
- Tabla de pagos `ESCROWED` y `REJECTED` del operador: Fecha, Productor, Monto XRP, Vence (con countdown "en Xh"), Estado.
- Botones por selección:
  - **"✓ Aprobar Calidad y Liberar"** (solo `ESCROWED`): diálogo de confirmación con campo de notas → `finish_escrow` → actualizar Payment a `COMPLETED`, EscrowDetail (finish_tx_hash, resolved_at), generar pacs.002 ACSC + camt.054, AuditLog. Mostrar URL del explorador del EscrowFinish.
  - **"✗ Rechazar Calidad"** (solo `ESCROWED`): exige motivo obligatorio → status `REJECTED`, pacs.002 RJCT, AuditLog. Informar: "El reembolso estará disponible el \<cancel_after\>".
  - **"↩ Ejecutar Reembolso"** (solo `REJECTED` y `now > cancel_after`; deshabilitado con tooltip si aún no vence): `cancel_escrow` → `REFUNDED`, camt.054 DBIT, AuditLog.
- Registrar la pestaña en `dashboard.py` entre Pago e Historial. Refrescar al completar pagos.
- Manejo de errores on-ledger: si `finish_escrow` devuelve `tec*` (p. ej. ventana vencida justo antes del clic), mostrar el código y NO cambiar el estado en DB; sugerir refrescar.

### E3.3 Historial y recibos
- `history_view.py`: colores/etiquetas para los estados nuevos — `ESCROWED` azul "En escrow", `REJECTED` naranja "Rechazado", `REFUNDED` gris "Reembolsado".
- Si la tarea 4.3 del plan base (recibo PDF) ya está hecha: el recibo de un pago `ESCROWED` lleva la leyenda "FONDOS EN ESCROW — pendiente de calidad" y el QR apunta al EscrowCreate; al liberarse, regenerar con el hash del finish.

---

## FASE E4 — Pruebas, Documentación y Cierre

### E4.1 Tests
- Unitarios (sin red): condición/fulfillment (estructura DER), transiciones de estado válidas e inválidas (no se puede reembolsar antes de `cancel_after`; no se puede liberar un `REJECTED`), generación de los 4 mensajes ISO del mapeo E2.2.
- Integración manual en testnet (checklist documentado en el plan, ejecutar a mano): ciclo completo aprobar (crear→liberar→verificar saldo del productor) y ciclo completo rechazar (crear→rechazar→esperar ventana corta de 1h... usar ventana mínima para la prueba→reembolsar).

### E4.2 Documentación
- `README.md`: nueva sección "Pago contra Calidad (Escrow)" con el diagrama de estados de D5 y el párrafo conceptual: *el pacs.002 ACSC transporta el fulfillment — el mensaje ISO es la llave que libera la liquidación*. Mencionar limitación XRP-only.
- `AUDITORIA.md`: marcar 8.9 como implementado.
- Docstring de módulo en `escrow_view.py` explicando la regla de XRPL de D2 (cancel solo post-vencimiento).

### E4.3 Verificación final
- `pytest tests/ -v` en verde.
- Humo en testnet: un escrow creado, liberado y visible en historial con sus 4+ mensajes ISO en la DB.

---

## Resumen de Secuencia

| Fase | Contenido | Riesgo | Dependencia |
|------|-----------|--------|-------------|
| E0 | Spike testnet: primitivos escrow + condición DER | Alto (por eso va primero) | Ninguna |
| E1 | xrpl_client + modelos + estados | Bajo | E0 |
| E2 | pacs.002 con fulfillment + mapeo de eventos | Medio | E1 + Fase 3 del plan base |
| E3 | UI: selector de modo + pestaña Escrows | Medio | E1, E2 |
| E4 | Tests, docs, verificación testnet | Bajo | Todo |

---

## Apéndice — Etapa 2: Visión B2B (NO implementar)

Registro de la decisión de producto, fuera de alcance de este plan:

La rama de producto natural del escrow no es el pago operador→productor en báscula (donde el pago inmediato es el valor), sino **un eslabón arriba**: liquidación de lotes entre cooperativa/exportador y comprador (tostador/importador), donde pagar contra catación (puntaje SCA) es práctica estándar. Beneficiarios: comprador (no paga lotes malos), cooperativa (verifica on-ledger que los fondos del comprador existen antes de embarcar), financiadores de cosecha (desembolsos por etapas).

Si ese segmento se persigue, la arquitectura correcta es una **tercera app** (`trade_app/`) sobre el mismo `core/`, con modelo propio (lotes, contratos, certificados de calidad) — NO extender `payment_app`. Son personas distintas: el operador de báscula optimiza velocidad con tickets chicos; el gerente comercial optimiza riesgo con tickets grandes. Prerequisito técnico adicional: escrow de tokens (XLS-85) si se liquida en stablecoins, verificar estado del amendment. Requiere su propio plan.
