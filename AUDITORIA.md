# Auditoría del Sistema — Coffee XRPL Platform

**Fecha:** 2026-06-11  
**Auditor:** Claude Sonnet 4.6  
**Rama auditada:** `main` (commit `0ff1d30`)

---

## Resumen Ejecutivo

El sistema está bien estructurado para un proyecto educativo. La separación entre `admin_app`, `payment_app` y `core` es sólida. Sin embargo, se identificaron **6 categorías de mejora** con un total de **24 hallazgos concretos** — algunos críticos si el proyecto evoluciona hacia producción.

---

## 1. Seguridad (Crítico)

### 1.1 Infraestructura de encriptación es código muerto (corregido tras verificación)
**Archivo:** `core/security.py:89-145` y `core/models.py:65`

**Verificación 2026-06-11:** `encrypt_data`, `decrypt_data` y `get_or_create_encryption_key` están implementados pero **nunca se invocan** desde ningún flujo. El campo `Producer.rfc_encrypted` existe en el modelo pero ningún formulario lo captura. El RFC de los productores simplemente no se está guardando.

Adicionalmente, si se llegara a usar, la llave Fernet se guardaría en `data/.encryption_key` sin protección.

**Propuesta:** (a) Añadir captura de RFC al formulario de nuevo productor usando la encriptación ya existente, y (b) leer la clave desde variable de entorno, con fallback al archivo solo en modo desarrollo.

```python
def get_or_create_encryption_key() -> bytes:
    key_env = os.environ.get("COFFEE_ENCRYPTION_KEY")
    if key_env:
        return key_env.encode()
    # fallback a archivo (solo dev)
    ...
```

### 1.2 Sin límite de intentos de autenticación
**Archivo:** `payment_app/ui_payment/auth_flow.py:206-252`

No hay bloqueo tras N intentos fallidos de contraseña. Un atacante con acceso físico puede hacer fuerza bruta.

**Propuesta:** Añadir contador de intentos al modelo `User` (campos `failed_login_count`, `locked_until`) y bloquear temporalmente tras 5 intentos fallidos.

### 1.3 Validación débil del seed XRPL
**Archivo:** `core/security.py:148-160`

Solo verifica que empiece con `'s'` y tenga 25+ caracteres. No valida el seed criptográficamente.

**Propuesta:** Usar `xrpl-py` para validar el seed real antes de almacenarlo en RAM:

```python
from xrpl.core.keypairs import decode_seed

def validate_xrpl_seed(seed: str) -> bool:
    try:
        decode_seed(seed)
        return True
    except Exception:
        return False
```

### 1.4 `except:` desnudo
**Archivo:** `payment_app/ui_payment/payment_flow.py:203`

Captura `KeyboardInterrupt`, `SystemExit` y cualquier otra excepción, silenciando errores reales de forma inadvertida.

**Propuesta:**
```python
# Cambiar:
except:
# Por:
except (ValueError, KeyError) as e:
    self.token_amount_label.setText(f"Error: {e}")
```

---

## 2. Modelo de Datos (Importante)

### 2.1 `Float` para montos financieros
**Archivo:** `core/models.py:81, 104`

`Float` de Python/SQLite tiene errores de precisión binaria. Para montos monetarios se debe usar `Numeric`.

**Propuesta:**
```python
from sqlalchemy import Numeric

amount     = Column(Numeric(precision=18, scale=8), nullable=False)
amount_mxn = Column(Numeric(precision=15, scale=2), nullable=True)
```

### 2.2 Estado `PENDING` para pagos simulados
**Archivo:** `payment_app/ui_payment/payment_flow.py:291`

Los pagos no-XRP quedan en estado `PENDING` indefinidamente. No existe un estado `SIMULATED` que refleje su naturaleza real.

**Propuesta:**
```python
class PaymentStatus(enum.Enum):
    PENDING   = "pending"
    COMPLETED = "completed"
    FAILED    = "failed"
    SIMULATED = "simulated"  # Añadir
```

### 2.3 `AuditLog.ip_address` nunca se popula
**Archivo:** `core/models.py:142`

El campo existe en el modelo pero en todo el código su valor siempre es `None`. Debe eliminarse o implementarse correctamente.

### 2.4 `generate_user_id` puede generar colisiones
**Archivo:** `core/utils.py:9-32`

Dos usuarios con mismas iniciales y fragmentos idénticos de dirección XRPL producirían el mismo ID. La validación en `create_user` lo rechaza, pero el mensaje de error es confuso para el operador.

**Propuesta:** Añadir un sufijo numérico incremental si el ID ya existe, en lugar de rechazar la creación.

---

## 3. Arquitectura (Moderado)

### 3.1 `XRPLClient` se instancia por widget
**Archivo:** `payment_app/ui_payment/payment_flow.py:32`

Cada `PaymentFlowWidget` crea su propio `JsonRpcClient`, generando conexiones innecesarias.

**Propuesta:** Crear el cliente una vez en `main_payment.py` e inyectarlo como dependencia.

### 3.2 Tasas de cambio hardcodeadas y desactualizadas
**Archivo:** `core/xrpl_client.py:186-191`

```python
MOCK_EXCHANGE_RATES = {
    'XRP_MXN': 20.0,   # XRP actualmente cotiza ~60-80 MXN
    ...
}
```

Las tasas son fijas e inexactas para uso real.

**Propuesta:** Implementar `fetch_live_rates()` que consulte un endpoint público (CoinGecko, Bitso) con caché local de 5 minutos y fallback a las tasas hardcodeadas si la API no responde.

### 3.3 `camt.053` implementado pero nunca invocado
**Archivo:** `core/iso_generator.py:203`

La función `generate_camt053()` está completa pero no se llama desde ningún flujo de pago ni de exportación.

**Propuesta:** Integrar la generación de `camt.053` en la vista de auditoría como exportación de estado de cuenta por periodo.

### 3.4 `Jinja2` en requirements pero no se usa
**Archivo:** `requirements.txt:11`

La dependencia está declarada pero el generador ISO usa `lxml` directamente. Eliminar la dependencia o adoptarla para templates XML más legibles y mantenibles.

---

## 4. Funcionalidades Faltantes (Alta Prioridad)

### 4.1 Sin gestión de productores en Admin
El admin puede crear usuarios operadores pero no puede gestionar productores (crear, editar, desactivar). Los productores solo se gestionan desde la app de pagos, rompiendo la separación de roles.

**Propuesta:** Añadir tab `"🌱 Productores"` en `admin_app` con un nuevo `ProducerAdminWidget`.

### 4.2 Sin activar/desactivar usuarios
**Archivo:** `admin_app/ui_admin/user_management.py`

El campo `is_active` existe en el modelo `User` pero no hay ningún control en la UI para cambiarlo.

**Propuesta:** Añadir botón `"🚫 Desactivar / ✅ Activar"` en la barra de acciones de la tabla de usuarios.

### 4.3 Sin filtros en historial de pagos
La vista de historial carga todos los pagos del operador sin posibilidad de filtrar por fecha, productor o estado.

**Propuesta:** Añadir controles de filtro por fecha y productor, similares a los del `AuditViewWidget`.

### ~~4.4 Sin visualización de foto de ID del productor~~ (RETIRADO tras verificación)

**Verificación 2026-06-11:** Este hallazgo era **incorrecto**. `producer_view.py:162-168` sí muestra la imagen de identificación (escalada a 300×300) al seleccionar un productor. No se requiere acción.

---

## 5. UX (Moderado)

### 5.1 Doble notificación al completar pago
**Archivos:** `payment_app/ui_payment/payment_flow.py:363` y `payment_app/ui_payment/dashboard.py:119-125`

`execute_payment()` muestra un `QMessageBox.information("Pago Exitoso")` y después `on_payment_completed()` muestra un segundo popup. El usuario recibe **dos ventanas de confirmación** consecutivas.

**Propuesta:** Eliminar el `QMessageBox` de `on_payment_completed` en el dashboard, dejando solo el de `execute_payment`.

### 5.2 Peso inicial en 0.0
**Archivo:** `payment_app/ui_payment/payment_flow.py:72-75`

El mínimo del campo es `0.01` pero el valor inicial es `0.0`. La validación en `execute_payment` lo captura, pero permite que el formulario muestre totales de $0.00 de forma confusa.

**Propuesta:** Usar `self.weight_input.setValue(0.01)` como valor inicial, o deshabilitar el botón de pago mientras el peso sea ≤ 0.

### 5.3 Sin paginación en tablas con muchos registros
Todas las tablas (`audit_table`, `user_table`, `history_table`) cargan todos los registros en memoria simultáneamente, lo que degradará el rendimiento con el tiempo.

**Propuesta:** Limitar las consultas con `.limit(200)` e implementar un botón "Cargar más" o paginación básica con offset.

---

## 6. Calidad de Código (Menor)

### 6.1 `datetime.utcnow()` deprecado desde Python 3.12
Usado en **13 lugares en 6 archivos** (verificado con grep). El método está marcado como deprecado.

**Propuesta:** Reemplazar globalmente:
```python
from datetime import datetime, timezone

# Reemplazar:
datetime.utcnow()
# Por:
datetime.now(timezone.utc)
```

### 6.2 Sin tests a pesar de tener `pytest` en requirements
No existe ningún archivo de test en el proyecto. Los módulos `core/utils.py`, `core/iso_generator.py` y `core/security.py` son perfectamente testeables sin necesidad de UI.

**Propuesta:** Crear `tests/test_core.py` con casos básicos para:
- `calculate_payment_total`
- `generate_uetr` (unicidad)
- `hash_password` / `verify_password`
- `validate_xrpl_seed`
- `generate_pacs008` / `generate_camt054` (validación XML)

### 6.3 Balance en `camt.053` hardcodeado a `"0.00"`
**Archivo:** `core/iso_generator.py:257`

```python
amt.text = "0.00"  # Placeholder
```

El balance de cierre siempre es cero. Debería calcularse sumando los montos de las transacciones del periodo incluidas en el estado de cuenta.

---

## 7. Hallazgos Adicionales (verificación 2026-06-11)

### 7.1 Detalle de pago vulnerable a desfase de filas
**Archivo:** `payment_app/ui_payment/history_view.py:158-169`

`show_payment_details` re-ejecuta el query completo y localiza el pago por **índice de fila**. Si se registra un pago nuevo entre la carga de la tabla y el doble clic, el detalle mostrado corresponde a otro pago.

**Propuesta:** Guardar `payment.id` en el item de la tabla con `setData(Qt.UserRole, payment.id)` y consultar por ID.

### 7.2 Enumeración de usuarios en login de pagos
**Archivo:** `payment_app/ui_payment/auth_flow.py:228-234`

El login admin responde "Usuario o contraseña incorrectos" (correcto, anti-enumeración), pero el login de pagos responde **"No se encontró un usuario con el ID: X"**, confirmando qué IDs existen. Dado que los IDs son derivables del nombre + dirección XRPL (`generate_user_id`), un atacante puede enumerar operadores válidos.

**Propuesta:** Unificar el mensaje genérico en ambos flujos, o aceptar el trade-off documentándolo (en un flujo de 3 pasos guiado puede ser deliberado por usabilidad).

### 7.3 Validación de dirección XRPL duplicada inline
**Archivo:** `payment_app/ui_payment/producer_view.py:262` y `admin_app/ui_admin/user_management.py:155-156`

Ambos formularios duplican la lógica `startswith('r') and len >= 25` en lugar de usar `XRPLClient.validate_address()`. Además, ninguna valida el checksum base58 real de la dirección — una dirección con un carácter mal tecleado pasa la validación y **el pago se enviaría a una cuenta inexistente o ajena**.

**Propuesta:** Centralizar en una sola función que use `xrpl.core.addresscodec.is_valid_classic_address()` para validación criptográfica real. Este es el hallazgo más importante de la verificación: en XRPL los fondos enviados a una dirección errónea son irrecuperables.

### 7.4 Sin registro de auditoría en flujos de pago
Los pagos ejecutados, creación de productores y logins de operadores **no escriben en `AuditLog`** — solo la app admin registra acciones. La tabla de auditoría queda ciega justo al flujo más crítico (movimiento de dinero).

**Propuesta:** Registrar en `AuditLog`: login/logout de operador, creación de productor, y cada pago ejecutado (con UETR en `details`).

---

## 8. Propuestas de Crecimiento del Producto

Funciones nuevas que son evolución natural del producto, ordenadas por relación valor/esfuerzo:

### 8.1 Recibo de pago imprimible (PDF con QR) — 🌟 Recomendada
Los productores de café son el usuario final del valor: necesitan un **comprobante físico** de su entrega y pago. Generar un PDF con datos de la entrega (peso, precio/kg, total), UETR, y un código QR apuntando al explorador XRPL de la transacción. Cualquiera puede verificar el pago escaneando el QR, sin confiar en la cooperativa.
- *Esfuerzo:* Medio (reportlab o qrcode + Pillow, ya hay Pillow en requirements)
- *Encaja en:* botón "🖨 Imprimir Recibo" tras pago exitoso y en detalles del historial

### 8.2 Precio de referencia del día (gestionado por admin) — 🌟 Recomendada
Hoy cada operador teclea el precio/kg manualmente (default fijo de $50). Esto es la fuente #1 de error y de posible fraude. El admin fija el **precio oficial del día** (tabla `DailyPrice`), la app de pagos lo carga automáticamente, y desviaciones manuales requieren nota obligatoria y quedan auditadas.
- *Esfuerzo:* Medio
- *Encaja en:* nuevo tab en admin + autocompletar en `payment_flow`

### 8.3 Saldo de wallet visible y verificación previa al pago
El operador no ve su saldo XRP en ninguna parte; se entera de que no alcanza cuando la transacción falla. Mostrar saldo en el header del dashboard (el método `get_balance` ya existe en `XRPLClient` y no se usa desde la UI) y pre-validar `saldo >= monto + reserva` antes de enviar.
- *Esfuerzo:* Bajo — el código del cliente ya está escrito

### 8.4 Perfil del productor con historial de entregas
Al seleccionar un productor, mostrar sus totales históricos: kg entregados en la temporada, número de entregas, último pago. Convierte la lista de productores en un mini-CRM y permite detectar productores frecuentes vs. nuevos.
- *Esfuerzo:* Bajo-medio (solo queries de agregación sobre datos existentes)

### 8.5 Cierre de día con camt.053
Conecta directamente con el hallazgo 3.3: botón "Cerrar Día" que genera el estado de cuenta camt.053 del periodo con el balance real calculado (resuelve también 6.3), lo guarda en `IsoMessage` y exporta el XML. Completa la narrativa ISO 20022 del producto: pacs.008 → camt.054 → camt.053.
- *Esfuerzo:* Medio — el generador ya existe, falta integrarlo

### 8.6 Dashboard de métricas en Admin
La app admin solo tiene gestión de usuarios y auditoría — no hay visión del negocio. Tab "📈 Resumen" con: total pagado del mes, kg acopiados, top productores, gráfica de volumen por semana (QtCharts viene incluido en PySide6).
- *Esfuerzo:* Medio

### 8.7 Cola de pagos offline
Contexto rural: la conectividad en zonas cafetaleras es intermitente. Permitir registrar la entrega (peso, precio, productor) sin conexión con estado `QUEUED`, y un botón "Sincronizar" que ejecute los pagos XRPL pendientes al recuperar señal.
- *Esfuerzo:* Alto — requiere repensar el flujo de estados, pero es el diferenciador más fuerte para el caso de uso real

### 8.9 Pago contra calidad con Escrow XRPL — 🌟 Pieza educativa estrella
Modo de pago opcional (solo XRP) donde los fondos se bloquean en un escrow nativo de XRPL con crypto-condición PREIMAGE-SHA-256 al registrar la entrega, y se liberan al aprobar la calidad. El `pacs.002 ACSC` transporta el *fulfillment* en `SplmtryData` — **el mensaje ISO 20022 contiene literalmente la llave que desbloquea los fondos**. Demuestra el ciclo de vida completo del pago (`PDNG → ACSC/RJCT`) con un primitivo que la banca tradicional no tiene.
- *Esfuerzo:* Alto — plan dedicado en `PLAN_ESCROW.md` (requiere Fases 1-3 del plan base)
- *Nota de producto:* el beneficiario natural a largo plazo es el eslabón cooperativa↔comprador (B2B), no el pago en báscula; la versión educativa va dentro de la app actual como modo opcional. Visión B2B documentada en el apéndice de `PLAN_ESCROW.md`.

### 8.8 Respaldo automático de base de datos
SQLite en un solo archivo local sin respaldo = todo el historial de pagos se pierde con un disco dañado. Copia automática a `data/backups/` al cerrar la app admin (rotando últimas N copias).
- *Esfuerzo:* Bajo

---

## 9. Evaluación Profunda: Capa ISO 20022

**Pregunta central: ¿está bien planteado, tiene sentido y es educativo?**

### Veredicto Ejecutivo

| Pregunta | Respuesta |
|----------|-----------|
| **¿Está bien planteado?** | ✅ **Sí.** La narrativa *"XRPL liquida, ISO 20022 reporta"* es como se posicionan los puentes blockchain-banca reales. El trío de mensajes, la ubicación del UETR y el uso de SplmtryData para el hash XRPL son decisiones correctas. |
| **¿Tiene sentido?** | ✅ **Sí, con una premisa pendiente de documentar.** pacs.008 es un mensaje entre bancos; saltarse pain.001 es defendible solo si se declara explícitamente que la plataforma actúa como agente del deudor y XRPL como sistema de liquidación. Hoy esa premisa está implícita. |
| **¿Es educativo?** | ⚠️ **A medias.** Los conceptos que enseña son los correctos, pero los XML generados no validarían contra los XSD oficiales (elementos obligatorios faltantes, gramática de versión incorrecta, montos truncados, divisa no-ISO 4217). Un estudiante que los tome como referencia aprendería estructuras que un validador real rechaza. Con validación XSD + pacs.002 + elementos obligatorios, pasaría de "ilustrativo" a "técnicamente verificable". |

### Veredicto conceptual: el planteamiento es correcto ✅

La narrativa del producto — *XRPL liquida, ISO 20022 reporta* — es genuinamente como se posicionan los puentes blockchain-banca reales. La selección de mensajes es un conjunto mínimo coherente y bien elegido:

| Mensaje | Rol en el flujo | ¿Cuándo se genera? |
|---------|----------------|---------------------|
| `pacs.008` | Instrucción de transferencia de crédito | Al ejecutar el pago ✅ |
| `camt.054` | Notificación de abono al beneficiario | Al ejecutar el pago ✅ |
| `camt.053` | Estado de cuenta del periodo | Nunca (hallazgo 3.3) ❌ |

El uso de **UETR en `PmtId/UETR`** es correcto y es exactamente donde va en SWIFT gpi. El uso de **`SplmtryData/Envlp`** para transportar el hash XRPL es una decisión inteligente: es el punto de extensión que el estándar contempla para datos propietarios. Estas dos decisiones son lo más valioso educativamente del módulo.

### Veredicto de ejecución: los XML generados NO validarían contra los XSD oficiales ❌

Aquí es donde el valor educativo se debilita. El README declara "ISO 20022 Compliance", pero los mensajes omiten elementos **obligatorios** del esquema y usan estructuras de versiones antiguas. Hallazgos concretos:

#### 9.1 `pacs.008`: faltan elementos obligatorios del esquema
**Archivo:** `core/iso_generator.py:40-139`

Contra el XSD oficial de `pacs.008.001.08`, faltan como mínimo:
- `GrpHdr/SttlmInf/SttlmMtd` (método de liquidación — **obligatorio**). Educativamente ideal: usar `CLRG` o documentar que XRPL actúa como el sistema de liquidación.
- `CdtTrfTxInf/IntrBkSttlmDt` (fecha de liquidación interbancaria — obligatoria en la práctica gpi).
- `CdtTrfTxInf/ChrgBr` (quién asume comisiones — **obligatorio**). Mapeo natural: el fee de XRPL lo paga el emisor → `DEBT`.
- `DbtrAgt` y `CdtrAgt` (agentes financieros — **obligatorios** en pacs.008; es un mensaje FI-a-FI). Aquí hay un punto conceptual importante, ver 9.4.

#### 9.2 `camt.054` y `camt.053`: estructura de versión incorrecta y elementos faltantes
**Archivo:** `core/iso_generator.py:141-287`

- `<Sts>BOOK</Sts>` es la estructura de las versiones `.02`. En la versión `.08` declarada en el namespace, `Sts` es un tipo complejo: `<Sts><Cd>BOOK</Cd></Sts>`. El mensaje declara una versión y usa la gramática de otra.
- `Ntry/BkTxCd` (código de transacción bancaria) es **obligatorio** en cada entrada de camt.053/054 y no se genera.
- `camt.054` no incluye el elemento `Acct` (¿a qué cuenta pertenece la notificación?). Sin cuenta, el `CdtDbtInd=CRDT` hardcodeado es ambiguo: ¿es el abono al productor o el cargo al operador? Educativamente lo correcto sería generar **dos** camt.054 (DBIT para el operador, CRDT para el productor) o al menos declarar la cuenta del productor.
- En `camt.053`, las entradas (`Ntry`) no llevan referencias (`NtryDtls/TxDtls/Refs/UETR`) — el estado de cuenta **no es conciliable** con los pacs.008, que es precisamente el propósito educativo de un camt.053.
- `from_date`/`to_date` se documentan en el docstring de `generate_camt053` pero nunca se escriben al XML (`FrToDt` ausente).
- Bug menor: si no se pasa `statement_id`, `MsgId` y `Stmt/Id` reciben **dos UUIDs distintos** (dos llamadas separadas a `uuid4()`), líneas 231 y 239.

#### 9.3 Pérdida de precisión y formato de datos
- **`f"{amount:.2f}"` trunca montos de token** (líneas 101, 177, 273). Un pago de `0.123456 XRP` se reporta como `0.12` — el XML contradice el monto realmente liquidado en el ledger y el almacenado en `Payment.amount`. ISO 20022 permite hasta 5 decimales según divisa; para tokens debería usarse la precisión completa.
- **`Ccy="XRP"` no es un código ISO 4217.** XRP no es una divisa ISO; un validador estricto lo rechaza. Esto merece tratamiento explícito porque es LA pregunta interesante del proyecto: el camino real es ISO 24165 (**DTI, Digital Token Identifier** — el DTI de XRP es registrable) referenciado desde supplementary data, o liquidar en divisa fiat equivalente y reportar el token como información adicional. Documentarlo convertiría una no-conformidad silenciosa en el mejor contenido educativo del módulo.
- **`format_datetime` omite la zona horaria** (línea 38). `2026-06-11T10:30:00` sin `Z` es hora local ambigua; los `ISODateTime` de ISO 20022 deben llevar offset: `strftime("%Y-%m-%dT%H:%M:%SZ")` con UTC.
- **`MsgId` = UETR** (línea 72): funciona, pero borra una distinción didáctica — `MsgId` es identificador punto-a-punto del mensaje, UETR es extremo-a-extremo de la transacción. Deberían ser valores distintos.

#### 9.4 Punto conceptual: ¿pacs.008 o pain.001?
`pacs.008` es un mensaje **entre instituciones financieras**. El flujo bancario real sería: cliente → `pain.001` (iniciación) → banco → `pacs.008` (interbancario). La plataforma salta la capa pain.001, lo cual es **defendible** si se documenta la premisa: *la plataforma actúa como agente del deudor y XRPL como sistema de liquidación interbancaria*. Hoy esa premisa está implícita; debería ser explícita en el README/docstrings porque es el corazón del modelo mental que el proyecto quiere enseñar.

### Recomendaciones ISO 20022 (en orden de impacto educativo)

1. **Validación XSD automática** — `lxml` (ya instalado) valida contra esquemas con 5 líneas. Descargar los XSD oficiales de iso20022.org a `schemas/`, validar cada mensaje al generarlo y guardar el resultado en `IsoMessage.is_schema_valid`. Es la mejora #1: convierte "afirmamos cumplir" en "demostramos cumplir", y habría detectado todos los hallazgos 9.1–9.3 automáticamente.
2. **Añadir `pacs.002` (Payment Status Report)** mapeando los códigos de resultado de XRPL a códigos de estado ISO: `tesSUCCESS → ACSC` (liquidado), `tec* → RJCT` con `StsRsnInf`. Es la pieza que falta del ciclo de vida del pago y el mapeo blockchain→ISO más ilustrativo posible. Hoy los pagos fallidos no generan ningún mensaje.
3. **Corregir los elementos obligatorios** de 9.1 y 9.2 (SttlmInf, ChrgBr, agentes, BkTxCd, estructura de `Sts`, `Acct` en camt.054).
4. **Documentar la decisión sobre `Ccy="XRP"`** (DTI vs. divisa equivalente) en el docstring del módulo y el README.
5. **camt.053 conciliable**: balance real calculado (resuelve 6.3), UETR en cada entrada, periodo `FrToDt` real, y conectarlo al "cierre de día" propuesto en 8.5.
6. **Ajustar el README**: cambiar "ISO 20022 Compliance" por "ISO 20022-aligned (simplified educational subset)" mientras 1–3 no estén hechos — la honestidad sobre el alcance es en sí misma educativa.
7. **Tests del generador**: con XSD en mano, los tests son triviales y de altísimo valor (`assert schema.validate(generated_xml)`).

### Conclusión

El planteamiento **tiene sentido y la arquitectura es educativa**: el conjunto de mensajes elegido, el UETR y el uso de supplementary data para el hash XRPL enseñan lo correcto. Lo que falta es que los artefactos generados estén a la altura de la narrativa: hoy un estudiante que tome estos XML como referencia aprendería estructuras que un validador real rechaza. Con validación XSD + pacs.002 + los elementos obligatorios, el módulo pasaría de "ilustrativo" a "técnicamente verificable", que es el estándar que un proyecto educativo de compliance debería ponerse a sí mismo.

---

## Resumen de Prioridades

| # | Hallazgo | Severidad | Esfuerzo estimado |
|---|----------|:---------:|:-----------------:|
| 7.3 | Sin validación checksum de dirección XRPL (riesgo de fondos perdidos) | 🔴 Alta | Bajo |
| 1.2 | Sin límite de intentos de login | 🔴 Alta | Medio |
| 1.3 | Validación débil del seed XRPL | 🔴 Alta | Bajo |
| 2.1 | `Float` para montos financieros | 🔴 Alta | Medio |
| 7.4 | Pagos no escriben en AuditLog | 🔴 Alta | Bajo |
| 9.1/9.2 | XML ISO no validan contra XSD oficial (elementos obligatorios faltantes) | 🔴 Alta* | Medio |
| 9.3 | Montos de token truncados a 2 decimales en XML ISO | 🔴 Alta* | Bajo |
| 1.1 | Encriptación RFC es código muerto | 🟡 Media | Medio |
| 9.x | Sin validación XSD automática ni pacs.002 | 🟡 Media | Medio |
| 2.2 | Estado `PENDING` para pagos simulados | 🟡 Media | Bajo |
| 2.3 | `ip_address` nunca populado | 🟡 Media | Bajo |
| 3.2 | Tasas de cambio hardcodeadas | 🟡 Media | Alto |
| 4.1 | Sin gestión de productores en Admin | 🟡 Media | Alto |
| 4.2 | Sin activar/desactivar usuarios | 🟡 Media | Bajo |
| 4.3 | Sin filtros en historial de pagos | 🟡 Media | Medio |
| 7.1 | Detalle de pago localizado por índice de fila | 🟡 Media | Bajo |
| 7.2 | Enumeración de usuarios en login de pagos | 🟡 Media | Bajo |
| 5.1 | Doble notificación de pago | 🟢 Baja | Bajo |
| 5.2 | Peso inicial en 0.0 | 🟢 Baja | Bajo |
| 5.3 | Sin paginación en tablas | 🟢 Baja | Medio |
| 6.1 | `datetime.utcnow()` deprecado (13 usos) | 🟢 Baja | Bajo |
| 6.2 | Sin tests | 🟢 Baja | Medio |
| 6.3 | Balance `camt.053` hardcodeado | 🟢 Baja | Bajo |
| 1.4 | `except:` desnudo | 🟢 Baja | Bajo |
| 2.4 | Colisiones en `generate_user_id` | 🟢 Baja | Bajo |
| 3.1 | `XRPLClient` instanciado por widget | 🟢 Baja | Bajo |
| 3.3 | `camt.053` implementado sin invocar | 🟢 Baja | Medio |
| 3.4 | `Jinja2` sin usar (verificado: 0 imports) | 🟢 Baja | Bajo |
| ~~4.4~~ | ~~Vista de foto de ID~~ — retirado, ya existe | — | — |

\* *"Alta" en el contexto del objetivo declarado del proyecto (demostrar compliance ISO 20022); no hay riesgo financiero directo porque los XML no se envían a ningún banco real.*

---

*Generado el 2026-06-11 — Para consultas sobre esta auditoría contactar al desarrollador del sistema.*
