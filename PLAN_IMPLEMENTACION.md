# Plan de Implementación — Coffee XRPL Platform

**Origen:** Hallazgos de `AUDITORIA.md` (2026-06-11)
**Ejecutor previsto:** Claude (Sonnet) — este documento es autocontenido; no requiere leer la auditoría primero, pero los números de hallazgo (`7.3`, `9.1`, etc.) refieren a ella.

---

## Reglas Generales para el Ejecutor

1. **Idioma:** Toda la UI está en español. Mantener español en mensajes, labels y QMessageBox. Los docstrings y comentarios de código van en inglés (convención existente).
2. **Estilo:** Imitar el código existente — PySide6 con layouts programáticos, `get_session()`/`close_session()` en bloques try/finally, QMessageBox para errores.
3. **Alcance:** Proyecto educativo. No introducir frameworks nuevos ni capas de abstracción que el código actual no tiene. No agregar dependencias salvo las indicadas explícitamente.
4. **Verificación por fase:** Al final de cada fase, ejecutar los tests (`pytest tests/ -v`) y arrancar ambas apps para humo básico:
   - `python admin_app/main_admin.py`
   - `python payment_app/main_payment.py`
5. **Base de datos:** No hay sistema de migraciones. Los cambios de esquema (Fase 2) se aplican con script de migración manual simple O recreando la DB (es aceptable en este proyecto — documentar cuál se eligió).
6. **Commits:** Un commit por tarea o grupo lógico, mensaje en español, referenciando el número de hallazgo. Ej: `fix(7.3): validación checksum de direcciones XRPL`.
7. **Orden:** Las fases están ordenadas por dependencia y riesgo. No saltar la Fase 1.

---

## FASE 0 — Preparación

### 0.1 Crear rama de trabajo
```
git checkout -b auditoria-fase-1
```
(Una rama por fase: `auditoria-fase-2`, etc. Merge a main al completar cada fase.)

### 0.2 Crear infraestructura de tests
- Crear `tests/__init__.py` y `tests/test_core.py`.
- Tests iniciales (todos deben pasar ANTES de empezar Fase 1, sirven de línea base):
  - `calculate_payment_total(10, 50) == 500.0`
  - `generate_uetr()` retorna UUID v4 válido y dos llamadas difieren
  - `hash_password` + `verify_password` roundtrip; contraseña incorrecta retorna False
  - `generate_pacs008` y `generate_camt054` retornan XML parseable con `lxml.etree.fromstring`
  - `format_currency(1234.5, "MXN") == "$1,234.50 MXN"`
- **Criterio de aceptación:** `pytest tests/ -v` pasa en verde.

---

## FASE 1 — Correcciones Críticas (riesgo alto, esfuerzo bajo)

### 1.1 Validación criptográfica de direcciones XRPL (hallazgo 7.3) — LA MÁS IMPORTANTE
**Problema:** Solo se valida `startswith('r') and len >= 25`. Una dirección mal tecleada pasa y los fondos XRPL enviados a dirección errónea son irrecuperables.

**Cambios:**
- `core/xrpl_client.py` → reemplazar el cuerpo de `XRPLClient.validate_address`:
  ```python
  from xrpl.core.addresscodec import is_valid_classic_address

  def validate_address(self, address: str) -> bool:
      return is_valid_classic_address(address)
  ```
  Considerar moverla a función de módulo `validate_xrpl_address(address)` para usarla sin instanciar el cliente.
- `payment_app/ui_payment/producer_view.py:262` → reemplazar la validación inline por la función central.
- `admin_app/ui_admin/user_management.py:152-157` (`validate_form`) → ídem. Nota: este método corre en cada tecleo (`textChanged`); `is_valid_classic_address` es barato (decode base58 + checksum), no hay problema de rendimiento.
- **Tests:** dirección válida real de testnet pasa; la misma dirección con un carácter alterado falla; cadena vacía y `None` fallan sin lanzar excepción.

### 1.2 Validación criptográfica del seed (hallazgo 1.3)
- `core/security.py:148-160` → reemplazar `validate_xrpl_seed`:
  ```python
  def validate_xrpl_seed(seed: str) -> bool:
      from xrpl.core.addresscodec import decode_seed
      try:
          decode_seed(seed)
          return True
      except Exception:
          return False
  ```
- **Test:** seed válido de testnet pasa; `"sInvalido123"` falla.

### 1.3 Registrar pagos y eventos en AuditLog (hallazgo 7.4)
**Problema:** Solo la app admin escribe en `AuditLog`. El flujo de dinero es invisible para auditoría.

**Cambios:**
- Crear helper en `core/utils.py` o nuevo `core/audit.py`:
  ```python
  def log_audit(session, user_id, action, details=None):
      """Add an AuditLog entry to an existing session (caller commits)."""
  ```
- Registrar (dentro de las sesiones/commits ya existentes, NO abrir sesiones nuevas):
  - `payment_flow.py::execute_payment` → acción `"Pago ejecutado"`, details con UETR, productor, monto y currency. Añadir al mismo `session.commit()` del pago.
  - `payment_flow.py` en el except → acción `"Pago fallido"` con el error (sesión nueva aquí, el pago no se guardó).
  - `producer_view.py::save_new_producer` → acción `"Productor creado"`.
  - `auth_flow.py::verify_wallet` (éxito) → acción `"Inicio de sesión en aplicación de Pagos"`.
  - `payment_app dashboard.py::logout` → acción `"Cierre de sesión de Pagos"`.
- **Criterio:** Tras un pago de prueba, la vista de auditoría del admin muestra la entrada con el UETR.

### 1.4 Detalle de pago por ID, no por índice de fila (hallazgo 7.1)
- `payment_app/ui_payment/history_view.py`:
  - En `load_history`, guardar el ID: `item.setData(Qt.UserRole, payment.id)` en la celda 0.
  - En `show_payment_details`, leer `payment_id = self.payment_table.item(row, 0).data(Qt.UserRole)` y consultar `filter_by(id=payment_id)` en lugar de re-ejecutar el query completo e indexar por fila.

### 1.5 Mensaje genérico en login de pagos (hallazgo 7.2)
- `auth_flow.py:228-234` → cambiar "No se encontró un usuario con el ID: X" por mensaje genérico: `"ID de usuario o credenciales incorrectos.\n\nVerifique sus datos o contacte al administrador."` No revelar existencia del usuario.

### 1.6 Limpiezas rápidas de UX y código
- **5.1 Doble notificación:** eliminar el `QMessageBox.information` de `payment_app/ui_payment/dashboard.py::on_payment_completed` (líneas ~119-125). Conservar el de `execute_payment` que tiene el detalle completo.
- **1.4 `except:` desnudo:** `payment_flow.py:203` → `except (ValueError, KeyError):` y mostrar el error en el label.
- **5.2 Peso inicial:** en `payment_flow.py`, deshabilitar `pay_button` cuando `weight_input.value() <= 0` (conectar a `valueChanged`), en vez de depender solo de la validación al hacer clic.

### 1.7 Límite de intentos de login (hallazgo 1.2)
- `core/models.py::User` → añadir columnas:
  ```python
  failed_login_count = Column(Integer, default=0, nullable=False)
  locked_until = Column(DateTime, nullable=True)
  ```
- Lógica en ambos logins (`login_window.py::login` y `auth_flow.py::verify_password` rama de verificación):
  - Antes de verificar: si `locked_until` existe y es futuro → mensaje "Cuenta bloqueada temporalmente. Intente en N minutos." y abortar.
  - Contraseña incorrecta → incrementar contador; al llegar a 5 → `locked_until = ahora + 15 min`, registrar en AuditLog `"Cuenta bloqueada por intentos fallidos"`.
  - Contraseña correcta → resetear contador y `locked_until = None`.
- **Nota de esquema:** requiere migración (ver regla general 5). Script sugerido: `scripts/migrate_001_login_attempts.py` con `ALTER TABLE users ADD COLUMN ...` vía SQLAlchemy `text()`.

---

## FASE 2 — Modelo de Datos

### 2.1 `Numeric` para montos (hallazgo 2.1)
- `core/models.py`:
  - `Payment.amount` → `Numeric(18, 8)`; `Payment.amount_mxn` → `Numeric(15, 2)`
  - `Delivery.weight_kg` → `Numeric(10, 3)`; `price_per_kg` → `Numeric(10, 2)`; `total_mxn` → `Numeric(15, 2)`
- En el código que escribe estos campos, convertir con `Decimal(str(value))` (los QDoubleSpinBox dan float; la conversión vía str evita arrastrar el error binario).
- En código que lee y formatea, `float(...)` para display está bien.
- **Nota SQLite:** SQLite no impone NUMERIC estrictamente, pero SQLAlchemy hará la conversión Decimal en Python, que es lo que importa.
- Migración: `scripts/migrate_002_numeric.py` o recreación de DB (documentar).
- **Test:** crear un Payment con `Decimal("0.123456")`, leerlo, comprobar igualdad exacta.

### 2.2 Estado `SIMULATED` (hallazgo 2.2)
- `core/models.py::PaymentStatus` → añadir `SIMULATED = "simulated"`.
- `payment_flow.py:291` → usar `PaymentStatus.SIMULATED` para currency != "XRP".
- `history_view.py` → color para el estado simulado (gris `#605E5C`) y mostrar "Simulado".

### 2.3 `datetime.utcnow()` deprecado (hallazgo 6.1)
- Reemplazar las **13 ocurrencias** en 6 archivos (`admin_app/ui_admin/dashboard.py`, `login_window.py`, `user_management.py` ×3, `core/iso_generator.py` ×3, `payment_app/ui_payment/payment_flow.py` ×4, `producer_view.py`) por `datetime.now(timezone.utc)` con el import correspondiente.
- También los `default=datetime.utcnow` en `core/models.py` → `default=lambda: datetime.now(timezone.utc)`.

### 2.4 `ip_address` en AuditLog (hallazgo 2.3)
- **Decisión: eliminarlo.** Es una app de escritorio local; la IP no aporta. Quitar la columna del modelo, la columna "IP" de `audit_view.py` (tabla y export Excel).

### 2.5 Colisiones de `generate_user_id` (hallazgo 2.4)
- `admin_app/ui_admin/user_management.py::create_user` → si el ID existe, en lugar de rechazar, probar sufijos `-2`, `-3`... hasta 9; informar el ID final en el mensaje de éxito.

---

## FASE 3 — ISO 20022 (sección 9 de la auditoría)

> Objetivo de la fase: que los mensajes generados **validen contra los XSD oficiales** y que el ciclo de vida del pago esté completo con pacs.002.

### 3.1 Descargar esquemas XSD oficiales
- Crear directorio `schemas/`.
- Descargar de iso20022.org (catálogo de mensajes) los XSD de: `pacs.008.001.08`, `pacs.002.001.10`, `camt.054.001.08`, `camt.053.001.08`. URLs del catálogo: `https://www.iso20022.org/iso-20022-message-definitions`.
- **Si no hay acceso a internet en el entorno de ejecución:** crear `schemas/README.md` con las URLs exactas e instrucciones de descarga manual, y hacer que la validación y sus tests se omitan limpiamente (skip) cuando los XSD no estén presentes.

### 3.2 Función de validación XSD
- Nuevo método en `core/iso_generator.py`:
  ```python
  SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas")

  def validate_against_schema(self, xml_string: str, message_type: str) -> tuple[bool, list[str]]:
      """Validate XML against official XSD. Returns (is_valid, error_list).
      If the XSD file is missing, returns (True, ["schema not available - validation skipped"]).
      """
  ```
  Implementar con `etree.XMLSchema(etree.parse(xsd_path))` y `schema.validate()` + `schema.error_log`.
- Integrar en `payment_flow.py`: tras generar cada XML, validar; si no valida, **no abortar el pago** (ya está liquidado en XRPL) pero registrar en AuditLog `"Mensaje ISO no válido contra esquema"` con los errores.

### 3.3 Corregir pacs.008 (hallazgo 9.1)
En `generate_pacs008`, añadir en el orden correcto del esquema (el orden de elementos en ISO 20022 es estricto — validar contra XSD tras cada cambio):
- `GrpHdr/SttlmInf/SttlmMtd` = `CLRG`, con comentario docstring: XRPL actúa como sistema de compensación.
- `CdtTrfTxInf/IntrBkSttlmDt` = fecha UTC del pago (`YYYY-MM-DD`).
- `CdtTrfTxInf/ChrgBr` = `DEBT` (el fee XRPL lo paga el emisor).
- `DbtrAgt` y `CdtrAgt` con `FinInstnId/Othr/Id` = `"XRPL"` (no hay BIC; usar identificador propietario, que el esquema permite vía `Othr`).
- `MsgId` distinto del UETR: usar `f"MSG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"`.

### 3.4 Corregir camt.054 (hallazgo 9.2)
- `Sts` como tipo complejo: `<Sts><Cd>BOOK</Cd></Sts>`.
- Añadir `Ntfctn/Acct/Id/Othr/Id` = dirección XRPL del **productor** (la notificación es del abono al beneficiario). Documentar en el docstring que esta es la notificación CRDT del acreedor.
- Añadir `Ntry/BkTxCd/Prtry/Cd` = `"XRPL-PMT"` (código propietario, permitido por esquema).
- Añadir `Ntry/BookgDt/DtTm` y `Ntry/ValDt/DtTm` con la fecha del pago.

### 3.5 Corregir camt.053 (hallazgos 9.2, 6.3)
- Mismas correcciones de `Sts` y `BkTxCd` que camt.054.
- `Stmt/FrToDt/FrDtTm` y `ToDtTm` desde los parámetros `from_date`/`to_date` (hoy se ignoran).
- **Balance real:** recibir `opening_balance` y calcular `closing = opening + sum(transactions)`. Generar DOS elementos `Bal`: `OPBD` (apertura) y `CLBD` (cierre). Eliminar el `"0.00"` hardcodeado.
- Cada `Ntry` debe incluir `NtryDtls/TxDtls/Refs/UETR` y `EndToEndId` del pago correspondiente (hace el estado de cuenta conciliable con los pacs.008).
- Bug del doble UUID (líneas 231/239): generar `statement_id` una sola vez al inicio y reutilizarlo.

### 3.6 Precisión y formato (hallazgo 9.3)
- Reemplazar TODOS los `f"{amount:.2f}"` por formateo con precisión completa usando `Decimal`: normalizar sin ceros finales innecesarios pero sin truncar (`Decimal(str(amount)).normalize()`, cuidando notación científica — usar helper `format_iso_amount(amount) -> str`).
- `format_datetime` → añadir `Z`: `dt.strftime("%Y-%m-%dT%H:%M:%SZ")` asegurando que dt sea UTC.
- **Divisa XRP:** mantener `Ccy="XRP"` pero documentar en el docstring del módulo la limitación y la ruta real (ISO 24165 DTI). Añadir el DTI como dato adicional en `SplmtryData` junto al hash: `<DigitalTokenId>` con comentario.

### 3.7 Nuevo: generador pacs.002 (Payment Status Report)
- `core/models.py::MessageType` → añadir `PACS_002 = "pacs.002"`.
- Nuevo método `generate_pacs002(self, payment_data, xrpl_result_code: str) -> str`:
  - Mapeo de códigos XRPL → ISO:
    - `tesSUCCESS` → `TxSts = ACSC` (AcceptedSettlementCompleted)
    - `tec*` (cualquier código que empiece con "tec") → `TxSts = RJCT` + `StsRsnInf/Rsn/Prtry` = código XRPL literal
    - otro/desconocido → `PDNG`
  - Estructura mínima: `FIToFIPmtStsRpt` con `GrpHdr`, `TxInfAndSts` (`OrgnlEndToEndId`, `OrgnlUETR`, `TxSts`, `StsRsnInf` si RJCT).
- Integrar en `payment_flow.py::execute_payment`:
  - Pago XRP exitoso → generar pacs.002 ACSC junto a los otros mensajes.
  - Pago XRP fallido (en el except, si hubo respuesta de XRPL con código) → guardar Payment con `status=FAILED` + pacs.002 RJCT. *(Hoy los pagos fallidos no se guardan en absoluto — decidir guardar el intento fallido es parte de esta tarea.)*
- Actualizar el mensaje de éxito de la UI para listar también pacs.002.

### 3.8 README honesto (recomendación 9.6)
- `README.md` → cambiar "ISO 20022 Compliance" por "ISO 20022-aligned messaging (educational subset, schema-validated)". Actualizar la lista de mensajes para incluir pacs.002. Añadir párrafo de la premisa conceptual (9.4): la plataforma actúa como agente del deudor; XRPL es el sistema de liquidación; se omite la capa pain.001 deliberadamente.

### 3.9 Tests de la fase
- Con XSD presentes: `assert generator.validate_against_schema(xml, "pacs.008")[0]` para los 4 tipos de mensaje con datos de ejemplo.
- Sin XSD: tests se omiten con `pytest.mark.skipif`.
- Test del mapeo pacs.002: `tesSUCCESS→ACSC`, `tecUNFUNDED_PAYMENT→RJCT`, `"???"→PDNG`.
- Test de `format_iso_amount`: `0.123456` → `"0.123456"`, `100` → `"100"`, sin notación científica.

---

## FASE 4 — Funciones de Crecimiento (sección 8 de la auditoría)

Implementar en este orden. Cada una es independiente; entregar de una en una.

### 4.1 Saldo de wallet visible + verificación previa (8.3) — esfuerzo bajo
- `payment_app/ui_payment/dashboard.py::create_header` → label `"💧 Saldo: X.XX XRP"` usando `XRPLClient.get_balance(operator.xrpl_address)` (ya existe, no se usa). Botón 🔄 para refrescar. Cargar en background o con cursor de espera (la llamada es de red).
- `payment_flow.py::execute_payment` → antes de enviar pago XRP: obtener saldo; si `saldo < monto + 1.0` (reserva base + margen de fee) → QMessageBox de error con saldo actual y monto requerido, abortar sin enviar.
- Refrescar el label de saldo tras cada pago exitoso.

### 4.2 Activar/desactivar usuarios (hallazgo 4.2) — esfuerzo bajo
- `admin_app/ui_admin/user_management.py` → botón `"🚫 Activar/Desactivar"` junto a "Resetear Contraseña": toma el usuario seleccionado, invierte `is_active`, registra en AuditLog, recarga tabla. Confirmación previa con QMessageBox.question.

### 4.3 Recibo de pago en PDF con QR (8.1) — esfuerzo medio
- Dependencias nuevas: `reportlab>=4.0.0` y `qrcode>=7.4.0` → añadir a `requirements.txt`.
- Nuevo módulo `core/receipt_generator.py`:
  ```python
  def generate_receipt_pdf(payment, delivery, producer, operator, output_path: str) -> str:
      """A5 receipt: header, producer/operator names, weight, price/kg, total MXN,
      token amount+currency, UETR, XRPL hash, timestamp, QR code pointing to
      testnet explorer URL. Returns output_path."""
  ```
  QR: `qrcode.make(explorer_url)` → imagen temporal → insertar con reportlab.
  Para pagos simulados, el QR apunta a nada: omitir QR y marcar "PAGO SIMULADO" en el recibo.
- Integración:
  - `payment_flow.py` → tras pago exitoso, botón/pregunta "¿Generar recibo PDF?" → QFileDialog.getSaveFileName, default `recibo_{uetr[:8]}.pdf`.
  - `history_view.py::show_payment_details` → reemplazar el QMessageBox de texto por un QDialog con los detalles y botón "🖨 Generar Recibo".
- **Test:** generar un recibo con datos dummy a tmp_path y verificar que el archivo existe y pesa > 1 KB.

### 4.4 Precio de referencia del día (8.2) — esfuerzo medio
- `core/models.py` → nueva tabla:
  ```python
  class DailyPrice(Base):
      __tablename__ = "daily_prices"
      id, price_date (Date, unique), price_per_kg (Numeric(10,2)),
      set_by_user_id (FK users.id), created_at
  ```
- Admin app → nuevo tab "💲 Precio del Día": form con fecha (default hoy) + precio, tabla de histórico de precios. Registrar en AuditLog.
- Payment app → `payment_flow.py`: al iniciar, cargar el precio de hoy de la DB; si existe, `price_input.setValue(precio)` y label "Precio oficial del día". Si el operador lo modifica manualmente, exigir nota obligatoria (validar `notes_input` no vacío al ejecutar) y registrar en AuditLog `"Pago con precio fuera de referencia"` incluyendo precio oficial vs. usado. Si no hay precio del día, comportamiento actual (default 50) con label "Sin precio oficial configurado".

### 4.5 Cierre de día con camt.053 (8.5) — depende de Fase 3
- Admin app, tab Auditoría → botón "📑 Generar Estado de Cuenta (camt.053)":
  - Diálogo: rango de fechas (default: hoy), cuenta del operador (combo con operadores).
  - Query de pagos del periodo del operador → `generate_camt053` con balance real (apertura = consulta de saldo XRPL actual menos suma del periodo, o 0 documentado) y UETR por entrada.
  - Guardar en `IsoMessage` (payment_id nullable: **requiere hacer `IsoMessage.payment_id` nullable en el modelo** — un statement no pertenece a un solo pago) y ofrecer exportar el XML.
- Registrar en AuditLog.

### 4.6 Perfil del productor con totales (8.4) — esfuerzo bajo-medio
- `producer_view.py::show_producer_details` → añadir bloque "Historial" con queries de agregación: nº de entregas, total kg, total MXN pagado, fecha del último pago. (`func.count`, `func.sum` sobre Payment/Delivery filtrado por producer_id, status != FAILED).

### 4.7 Respaldo automático de DB (8.8) — esfuerzo bajo
- `core/database.py` → función `backup_database()`: copia `coffee_platform.db` a `data/backups/coffee_platform_{YYYYMMDD_HHMMSS}.db` usando la API de backup de sqlite3 (`sqlite3.Connection.backup`, segura con DB en uso); conservar las últimas 10 copias, borrar las más antiguas.
- Llamar desde `admin_app dashboard.py::closeEvent`.

### 4.8 Filtros en historial de pagos (hallazgo 4.3) — esfuerzo medio
- `history_view.py` → barra de filtros sobre la tabla: QDateEdit desde/hasta (default: último mes), combo de productor (poblado de la DB, opción "Todos"), combo de estado ("Todos", Completado, Simulado, Fallido). Aplicar en el query de `load_history`. El export Excel respeta los filtros activos.

### 4.9 Dashboard de métricas en Admin (8.6) — esfuerzo medio
- Nuevo tab "📈 Resumen" en admin app (`admin_app/ui_admin/metrics_view.py`):
  - Cards de texto: total pagado MXN del mes, kg acopiados del mes, nº de pagos, nº de productores activos.
  - Tabla "Top 5 productores por kg" del mes.
  - Si se quiere gráfica: `QtCharts` (incluido en PySide6, sin dependencia nueva) con barras de kg por semana. Opcional — las cards y tabla son el entregable mínimo.

### 4.10 Gestión de productores en Admin (hallazgo 4.1) — esfuerzo alto, última
- Nuevo tab "🌱 Productores" en admin: tabla de todos los productores (activos e inactivos), botones editar (nombre, contacto — NO la dirección XRPL si ya tiene pagos), activar/desactivar, y captura de RFC usando la encriptación existente (`encrypt_data` + `get_or_create_encryption_key`) — esto resuelve también el hallazgo 1.1 (código muerto).
- Junto con esto, mover la clave de encriptación a variable de entorno `COFFEE_ENCRYPTION_KEY` con fallback al archivo (hallazgo 1.1b).

---

## FASE 5 — Calidad y Cierre

### 5.1 Paginación de tablas (hallazgo 5.3)
- En `audit_view.py` y `history_view.py`: `.limit(200)` + botón "Cargar más" que incrementa offset. Mostrar "Mostrando X de Y" usando un `count()` previo.

### 5.2 `XRPLClient` compartido (hallazgo 3.1)
- Crear instancia única en `main_payment.py`, pasarla a `PaymentDashboard` → `PaymentFlowWidget`. Eliminar instanciaciones locales (incluida la de `auth_flow.py::verify_wallet`).

### 5.3 Limpieza de dependencias (hallazgo 3.4)
- Quitar `Jinja2` de `requirements.txt` (0 imports verificados). Verificar si `python-dotenv` y `Pillow` se usan; quitar los que no (Pillow puede pasar a usarse en 4.3 con qrcode — verificar antes de quitar).

### 5.4 Suite de tests final
- Objetivo mínimo: tests verdes para `core/utils.py`, `core/security.py`, `core/iso_generator.py` (incl. validación XSD y pacs.002), `core/receipt_generator.py`, y validación de direcciones/seeds.
- `pytest tests/ -v` como comando de verificación final de todo el plan.

### 5.5 Actualizar documentación
- `README.md`: nuevas funciones (recibos, precio del día, métricas, pacs.002, validación XSD).
- `QUICKSTART.md`: nuevas dependencias y pasos de migración de DB si aplican.
- `AUDITORIA.md`: marcar hallazgos resueltos con ✅ y fecha.

---

## Resumen de Secuencia

| Fase | Contenido | Hallazgos que resuelve | Riesgo |
|------|-----------|------------------------|--------|
| 0 | Rama + tests base | 6.2 (parcial) | — |
| 1 | Validación XRPL, auditoría de pagos, login seguro, UX | 7.3, 1.3, 7.4, 7.1, 7.2, 5.1, 1.4, 5.2, 1.2 | Bajo |
| 2 | Numeric, SIMULATED, datetime, ip_address, IDs | 2.1, 2.2, 6.1, 2.3, 2.4 | Medio (migración) |
| 3 | ISO 20022: XSD, obligatorios, precisión, pacs.002 | 9.1, 9.2, 9.3, 9.4, 6.3, 3.3 (parcial) | Medio |
| 4 | Crecimiento: saldo, recibos PDF, precio del día, cierre camt.053, perfil, backup, filtros, métricas, productores en admin | 8.1–8.8, 4.1, 4.2, 4.3, 1.1 | Medio |
| 5 | Paginación, cliente compartido, deps, tests, docs | 5.3, 3.1, 3.4, 6.2 | Bajo |

**No incluido deliberadamente** (decisión pendiente del dueño del producto): tasas de cambio en vivo (3.2 — requiere elegir proveedor de precios y manejo de API keys) y cola de pagos offline (8.7 — requiere rediseño del flujo de estados; planificar por separado si se aprueba).
