# PLAN_FRONTEND.md — Mejoras visuales y de UX

> **Audiencia:** agentes Sonnet ejecutores. Cada fase es autocontenida e indica archivos, cambios y criterios de aceptación.
> **Regla global:** los 18 tests de `tests/test_core.py` deben seguir pasando tras cada fase (`python -m pytest tests/ -q`). Verificar sintaxis con `python -m py_compile <archivos>` antes de dar por terminada una fase.
> **Contexto:** PySide6 6.10, dos apps (admin_app y payment_app) que comparten paleta vía `admin_app/ui_admin/styles.py` (COLORS). `core/models.py` ya incluye estados de escrow (`ESCROWED`, `REJECTED`, `REFUNDED`) que el frontend aún NO maneja.

---

## Diagnóstico (resumen de la revisión)

| # | Hallazgo | Severidad |
|---|----------|-----------|
| D1 | **Bug timezone en precio del día**: `price_view.py` guarda la fecha local (`QDate.currentDate()`), pero `payment_flow._load_daily_price()` consulta con `datetime.now(timezone.utc).date()`. En México (UTC-6), a partir de las ~18:00 hora local la fecha UTC ya es "mañana" y el precio del día deja de encontrarse. | Alta (bug funcional) |
| D2 | Estados nuevos (`escrowed`, `rejected`, `refunded`) caen al color naranja genérico en historial; no existen en el combo de filtros; lógica de color duplicada en 3 lugares (`load_history`, `_load_more`, `user_management`). | Alta |
| D3 | Llamadas de red XRPL (`get_balance`, `send_xrp_payment`) corren en el hilo principal → la ventana se congela varios segundos durante un pago real. El `QProgressDialog` no anima. | Alta |
| D4 | Todo feedback usa `QMessageBox` modal, incluso éxitos rutinarios (precio guardado, export OK). Interrumpe el flujo. | Media |
| D5 | Resultado de pago y detalles de pago se muestran como texto plano en `QMessageBox`: el hash/UETR no se puede copiar cómodamente, el link al explorer no es clicable. | Media |
| D6 | Tablas sin filas alternadas, sin ordenamiento por columna, sin estados vacíos ("no hay datos"). Doble-clic para detalles de pago es indescubrible. | Media |
| D7 | Login de pagos (3 pasos) no tiene indicador visual de progreso; login admin no tiene "mostrar contraseña" ni `returnPressed` en el campo usuario. | Media |
| D8 | Dashboard de métricas sin gráfica; las tarjetas KPI son el único elemento. PySide6 incluye `QtCharts` (sin dependencias nuevas). | Baja |
| D9 | No hay recibo imprimible del pago (estaba como 4.3 en el plan original y nunca se hizo). Qt permite PDF sin dependencias (`QTextDocument` + `QPrinter`). | Baja |
| D10 | Sin íconos de ventana, tooltips escasos, sin atajos de teclado (F5 actualizar, etc.). El indicador "🟢" del status bar de pagos nunca cambia aunque XRPL esté caído. | Baja |

---

## Arquitectura: módulo compartido nuevo

Crear el paquete **`shared_ui/`** en la raíz del proyecto (junto a `core/`):

```
shared_ui/
  __init__.py
  theme.py        # re-exporta COLORS y añade STATUS_STYLES
  components.py   # Toast, KpiCard, EmptyState, make_status_item()
  workers.py      # FunctionWorker (QThread genérico)
```

Ambas apps ya hacen imports cruzados (`payment_app` importa de `admin_app.ui_admin.styles`), así que un paquete raíz compartido es una mejora, no una excepción.

---

## FASE F1 — Sistema de diseño compartido (PRIMERO, bloquea a las demás)

### F1.1 `shared_ui/theme.py`

```python
from admin_app.ui_admin.styles import COLORS

# Único mapa de estados de pago: etiqueta ES, color de texto, color de fondo (pill)
STATUS_STYLES = {
    "completed": ("Completado",  "#107C10", "#DFF6DD"),
    "failed":    ("Fallido",     "#D13438", "#FDE7E9"),
    "simulated": ("Simulado",    "#605E5C", "#F3F2F1"),
    "pending":   ("Pendiente",   "#CA5010", "#FFF4CE"),
    "escrowed":  ("En Escrow",   "#0078D4", "#DEECF9"),
    "rejected":  ("Rechazado",   "#A4262C", "#FDE7E9"),
    "refunded":  ("Reembolsado", "#8764B8", "#F0EBF9"),
}
```

### F1.2 `shared_ui/components.py`

1. **`make_status_item(status_value: str) -> QTableWidgetItem`** — devuelve un item con texto en español, `setForeground` y `setBackground` según `STATUS_STYLES` (fallback gris si no existe). Sustituye los 3 bloques if/elif duplicados.
2. **`Toast`** — `QLabel` flotante no modal sobre el widget padre: fondo oscuro semitransparente, esquinas redondeadas, se posiciona abajo-centro, desaparece a los 3 s con `QTimer` + fade (`QGraphicsOpacityEffect` + `QPropertyAnimation`). API: `Toast.show_message(parent, "✓ Precio guardado")`.
3. **`KpiCard`** — extraer la lógica `_make_card`/`_get_card_label` de `metrics_view.py` a una clase con método `set_value(str)`. Sin `findChild` frágil.
4. **`EmptyStateOverlay`** — label centrado gris ("Sin datos para los filtros seleccionados") que se muestra encima de una `QTableWidget` cuando `rowCount() == 0`. Helper: `attach_empty_state(table, text)`.

### F1.3 `shared_ui/workers.py`

```python
class FunctionWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)
    # run() ejecuta self._fn(*args) y emite la señal correspondiente
```
Guardar referencia del worker en el widget padre para evitar garbage collection prematura. Documentarlo en docstring.

**Aceptación F1:** paquete importable (`python -c "from shared_ui.components import Toast, make_status_item"`), tests pasan.

---

## FASE F2 — Correcciones funcionales de UX (depende de F1)

### F2.1 Bug de timezone del precio del día (D1) — PRIORITARIO
En `payment_app/ui_payment/payment_flow.py`, método `_load_daily_price`:
- Cambiar `today = datetime.now(timezone.utc).date()` por `today = datetime.now().date()` (fecha **local**, igual que la guarda el admin).
- Mismo criterio en cualquier otra comparación de "hoy" contra `DailyPrice.price_date`.

### F2.2 Estados completos (D2)
- `payment_app/ui_payment/history_view.py`: reemplazar los dos bloques de coloreado (en `load_history` y `_load_more`) por `make_status_item(payment.status.value)`. Extraer el llenado de una fila a un método `_fill_payment_row(row, payment)` usado por ambos (elimina ~40 líneas duplicadas).
- Combo de filtro de estado: añadir `"En Escrow"`, `"Rechazado"`, `"Reembolsado"` y mapearlos en `_build_filtered_query` a `PaymentStatus.ESCROWED/REJECTED/REFUNDED`.
- `admin_app/ui_admin/user_management.py`: usar colores de `STATUS_STYLES` para Activo/Inactivo (o dejar como está si se prefiere; mínimo: quitar el `except:` desnudo de `validate_form` → `except Exception`).

### F2.3 Tablas (D6)
Para `history_view.payment_table`, `audit_view.audit_table`, `user_management.user_table`, `price_view.price_table`, `metrics_view.top_table`:
- `table.setAlternatingRowColors(True)` + en ambos stylesheets: `QTableWidget { alternate-background-color: #FAFAFA; }`.
- `setSortingEnabled(True)` **solo** en tablas sin paginación (`user_table`, `price_table`, `top_table`). En las paginadas el orden lo da el query — no activar (rompería "Cargar más").
- Adjuntar `EmptyStateOverlay` a las 5 tablas con textos apropiados.

### F2.4 Detalles de pago descubribles
En `history_view`: botón "🔍 Ver Detalles" junto a Exportar (habilitado al seleccionar fila) que llama a la misma ruta que el doble-clic. Añadir tooltip a la tabla: "Doble clic para ver detalles".

**Aceptación F2:** `py_compile` limpio en los 5 archivos de vistas; tests pasan; precio del día se encuentra usando fecha local.

---

## FASE F3 — Red sin congelar la UI (depende de F1; paralelizable con F2 salvo `payment_flow.py`/`dashboard.py` de pagos)

### F3.1 Saldo en segundo plano
`payment_app/ui_payment/dashboard.py` → `refresh_balance`:
- Mostrar `"💧 Saldo: ⏳"` inmediatamente, lanzar `FunctionWorker(self._xrpl_client.get_balance, self.operator.xrpl_address)`.
- `finished_ok` → actualizar label; `failed` → `"💧 Saldo: sin conexión"`.
- Quitar `setOverrideCursor` (ya no aplica).
- **Indicador de conexión (D10):** en `update_status`, usar 🟢 cuando el último refresh de saldo fue exitoso y 🔴 con "Sin conexión a XRPL Testnet" cuando falló.

### F3.2 Pago en segundo plano
`payment_app/ui_payment/payment_flow.py` → `execute_payment`:
- Extraer la lógica de envío + persistencia (pasos 2–4 actuales) a un método `_do_payment(...)` que reciba primitivos (uetr, seed, address, montos) y devuelva el dict de resultado. **La sesión de DB se abre y cierra dentro de `_do_payment`** (las sesiones SQLAlchemy no se comparten entre hilos).
- Ejecutarlo en `FunctionWorker`; mientras corre: `pay_button.setEnabled(False)` con texto "⏳ Procesando…"; el `QProgressDialog` pasa a rango indeterminado (`setRange(0,0)`).
- `finished_ok` → diálogo de éxito (ver F4.1), emitir `payment_completed`, resetear formulario. `failed` → mensaje de error actual + audit log de fallo.
- La verificación previa de saldo (pre-flight) también va dentro del worker.
- **Importante:** ningún `QMessageBox` ni acceso a widgets dentro del worker; toda la UI en los slots de las señales.

**Aceptación F3:** durante un pago simulado la ventana sigue respondiendo (se puede mover); botón deshabilitado durante el proceso; tests pasan.

---

## FASE F4 — Diálogos y feedback (depende de F1 y F3.2)

### F4.1 Diálogo de pago exitoso (D5)
Nuevo `payment_app/ui_payment/payment_result_dialog.py` — `QDialog` que reemplaza el `QMessageBox` de éxito:
- Encabezado "✓ Pago Exitoso" en verde + monto grande (clase `amount`).
- Filas UETR y Hash: `QLineEdit` readonly (seleccionable) + botón "📋" que copia con `QApplication.clipboard().setText(...)` y muestra `Toast` "Copiado".
- Si hay `explorer_url`: botón "🌐 Ver en Explorer" → `QDesktopServices.openUrl(QUrl(url))`.
- Botón "🧾 Guardar Recibo PDF" (ver F4.3).
- Listado de mensajes ISO generados.

### F4.2 Diálogo de detalles de pago
Nuevo `payment_app/ui_payment/payment_detail_dialog.py`, usado por `history_view.show_payment_details` en lugar del `QMessageBox`:
- Secciones en `QFormLayout` (Identificadores / Productor / Entrega / Estado).
- UETR y hash copiables (mismo patrón F4.1).
- Si `payment.iso_messages`: combo con los tipos + botón "Ver XML" que abre un `QDialog` con `QPlainTextEdit` readonly (fuente monoespaciada) + botón "Guardar como…".
- Botón "🧾 Recibo PDF".
- **Nota:** cargar todos los datos a primitivos/strings ANTES de cerrar la sesión de DB (evitar `DetachedInstanceError`).

### F4.3 Recibo PDF sin dependencias nuevas (D9 — aporte nuevo)
Nuevo `core/receipt.py`:
```python
def generate_receipt_pdf(payment_data: dict, file_path: str) -> None:
    # Construye HTML (plantilla f-string: logo ☕, folio UETR, fecha, productor,
    # peso, precio/kg, total MXN, token enviado, hash, leyenda Testnet educativa)
    # doc = QTextDocument(); doc.setHtml(html)
    # printer = QPrinter(); printer.setOutputFormat(QPrinter.PdfFormat)
    # printer.setOutputFileName(file_path); doc.print_(printer)
```
Imports: `from PySide6.QtGui import QTextDocument` y `from PySide6.QtPrintSupport import QPrinter`. Botones en F4.1 y F4.2 abren `QFileDialog.getSaveFileName` con nombre por defecto `recibo_{uetr[:8]}.pdf`.

### F4.4 Toasts para éxitos rutinarios (D4)
Reemplazar `QMessageBox.information` por `Toast.show_message(self, ...)` SOLO en: precio guardado (`price_view`), exportaciones exitosas (`audit_view` ×3, `history_view`), contraseña actualizada (`dashboard` admin). **Conservar** los modales de error, las confirmaciones (`question`) y el resultado de pago (que ahora es F4.1).

**Aceptación F4:** pago exitoso muestra el diálogo nuevo con copia y PDF funcionales; exportar genera toast; tests pasan.

---

## FASE F5 — Autenticación (independiente; paralelizable con F2–F4)

### F5.1 Stepper visual en app de pagos (D7)
En `auth_flow.py`, sobre el `QStackedWidget`: fila con 3 indicadores `("1 ID", "2 Contraseña", "3 Wallet")`. El paso activo en círculo/pill azul primario, los completados en verde, los futuros en gris. Implementar como widget `StepIndicator` en `shared_ui/components.py` con método `set_current(index)`; conectarlo a `stack.currentChanged`.

### F5.2 Login admin (D7)
`login_window.py`:
- `returnPressed` del campo usuario → foco a contraseña.
- Botón-ojo "👁" para mostrar/ocultar contraseña (reutilizar el patrón `toggle_seed_visibility` de `auth_flow`; extraer a helper en `shared_ui/components.py`: `add_password_toggle(line_edit)` que devuelve un botón checkable).
- En el formulario de setup inicial, aplicar el mismo toggle a ambos campos.

### F5.3 Foco y orden de tabulación
- Al abrir cada paso/ventana de login: `setFocus()` al primer campo (ya existe en pasos 2–3 de pagos; añadir en paso 1 y en login admin).
- `setTabOrder` explícito en el formulario de crear usuario (admin) y en el de nuevo productor.

**Aceptación F5:** flujo de pagos navegable solo con teclado (Enter avanza); stepper refleja el paso actual.

---

## FASE F6 — Métricas con gráfica (independiente; tocar solo `metrics_view.py`)

### F6.1 Gráfica de pagos por día (D8)
En `admin_app/ui_admin/metrics_view.py`, bajo las tarjetas KPI:
- `from PySide6.QtCharts import QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis` — envolver el import en `try/except ImportError` y, si falla, omitir la gráfica silenciosamente (no romper el dashboard).
- Query: suma de `amount_mxn` agrupada por día (`func.date(Payment.timestamp)`) del mes en curso, estados COMPLETED+SIMULATED.
- Barras azul primario `#0078D4`, sin leyenda, `QChart.ChartThemeLight`, antialiasing, altura máx. 260 px. Eje X: día del mes; eje Y: MXN.
- Refrescar dentro de `refresh_metrics`.

### F6.2 Refactor a KpiCard
Sustituir `_make_card`/`_get_card_label` por `shared_ui.components.KpiCard` (F1.2).

### F6.3 Contexto extra
- Caption bajo el título: "Datos del 1 al {hoy} de {mes}".
- En `price_view.load_prices`: si la fila corresponde a hoy, pintar fondo `#DFF6DD` en las 3 celdas (precio vigente visible de un vistazo).

**Aceptación F6:** dashboard admin muestra gráfica con datos del mes (o se omite limpiamente si QtCharts no está); tests pasan.

---

## FASE F7 — Pulido final (última; toca muchos archivos, NO paralelizar con otras)

1. **Íconos de ventana:** `core/utils.py` (o `shared_ui/theme.py`): helper `make_app_icon(emoji)` que pinta el emoji en un `QPixmap` 64×64 transparente y devuelve `QIcon`. Aplicar `app.setWindowIcon(...)` en ambos `main_*.py` (☕).
2. **Atajos:** `QShortcut(QKeySequence("F5"), widget)` → refrescar en historial, auditoría, métricas, precios; `Ctrl+E` → exportar Excel en historial y auditoría.
3. **Tooltips faltantes:** botones de solo ícono (🔄 saldo), campos de seed/contraseña, botón "Cierre de Día" (explicar qué genera).
4. **Microcopy:** revisar que todos los títulos/labels usen español consistente (p. ej. el combo de moneda "MXN Token (Simulado)") y que los placeholder de direcciones XRPL usen una dirección de ejemplo válida.
5. **Mostrar tasa de conversión** en `payment_flow`: caption bajo `token_amount_label` con la tasa usada por `convert_mxn_to_token` (leerla de `core/xrpl_client.py`), p. ej. "Tasa fija educativa: 1 XRP = $X MXN".
6. **README:** sección breve "Interfaz" con las novedades (recibo PDF, gráfica, toasts).

---

## Orden de ejecución y paralelización

```
F1 (secuencial, primero)
├── F2 ─┐
├── F3 ─┤  paralelizables entre sí, con cuidado:
├── F5 ─┤  • F2 y F3 comparten payment_app/ → si van en paralelo,
└── F6 ─┘    F2 NO toca payment_flow.py/dashboard.py (los toca F3)
F4 (tras F3)
F7 (al final, solo)
```

Asignación sugerida para agentes en paralelo (ronda 1): **Agente A** = F2 (sin payment_flow/dashboard de pagos) + F5; **Agente B** = F3; **Agente C** = F6. Ronda 2: F4. Ronda 3: F7 + lo de F2 que dependía de payment_flow.

## Verificación final
1. `python -m pytest tests/ -q` → 18 passed.
2. `python -m py_compile` sobre todos los archivos tocados.
3. Lanzar ambas apps y validar manualmente con el usuario: login admin (`admin`/`admin123456`), pago simulado completo, recibo PDF, gráfica de métricas.
4. Commit por fase con prefijo `feat(frontend-FX):`.
