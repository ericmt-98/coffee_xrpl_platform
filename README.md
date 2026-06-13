# ☕ Coffee XRPL Platform

Plataforma de escritorio para la gestión de pagos a productores de café, construida sobre el **XRP Ledger**. Combina liquidación blockchain con mensajería financiera **ISO 20022** y una interfaz de escritorio completa en PySide6.

> Proyecto educativo/profesional. Configurado sobre XRPL Testnet.

---

## Aplicaciones

El sistema se compone de dos apps independientes que comparten el mismo núcleo (`core/`) y componentes UI (`shared_ui/`):

### App de Pagos (`payment_app`)
Usada por el operador en campo para registrar entregas y ejecutar pagos a productores.

- Autenticación de 3 pasos con indicador de progreso (ID → Contraseña → Wallet)
- Dashboard con saldo de wallet XRPL en tiempo real (consulta no bloqueante)
- Flujo de pago: selección de productor → entrega en kg → tipo de token (XRP / USDC / RLUSD) → liquidación
- Soporte para pagos directos y pagos en escrow con confirmación manual
- Historial con filtros por estado, detalles completos, visor XML ISO 20022 y exportación a PDF
- Perfil de productor con totales históricos

### App Administrativa (`admin_app`)
Usada por el administrador de la cooperativa para supervisión y operación diaria.

- Gestión de usuarios (alta, bloqueo, roles)
- Precio de referencia del día (MXN/kg) con historial de 30 días
- Métricas del mes: total MXN, kg acopiados, pagos, productores activos — con gráfica de barras por día
- Log de auditoría completo con exportación CSV
- Cierre de día: genera camt.053 (estado de cuenta) para el período

---

## Características técnicas

### Seguridad
- Contraseñas con **Argon2id** (resistente a GPU/ASIC)
- Bloqueo automático tras 5 intentos fallidos (15 minutos)
- Validación de dirección XRPL con checksum Base58
- Log de auditoría inmutable para toda acción relevante

### Mensajería ISO 20022
Genera mensajes con namespaces correctos (no xmlns genérico):

| Mensaje | Uso |
|---------|-----|
| `pacs.008` | Instrucción de transferencia de crédito |
| `pacs.002` | Reporte de estado del pago (ACSC / RJCT / PDNG) |
| `camt.054` | Notificación de débito/crédito |
| `camt.053` | Estado de cuenta (cierre de día) |

### XRPL
- Pagos directos XRP / tokens (USDC, RLUSD)
- Pagos en escrow con condición HTLC (SHA-256 preimage)
- Consultas de saldo y estado via `xrpl-py` en hilo separado (no bloquea UI)
- Cada transacción queda referenciada por su hash en ledger + UETR

### UI / UX
- Tema consistente con paleta Microsoft Fluent (colores, tipografía)
- Notificaciones toast no intrusivas, estados vacíos en todas las tablas
- Atajos de teclado: `F5` = actualizar, `Ctrl+E` = exportar
- Generación de recibos PDF sin dependencias externas (QTextDocument + QPrinter)
- Operaciones de red en `QThread` via `FunctionWorker` — la UI nunca se congela

---

## Estructura del proyecto

```
coffee_xrpl_platform/
├── core/                      # Lógica compartida
│   ├── models.py              # ORM: Usuario, Productor, Entrega, Pago, AuditLog, DailyPrice
│   ├── database.py            # Sesiones SQLAlchemy
│   ├── security.py            # Argon2, lockout, validación XRPL
│   ├── xrpl_client.py         # Cliente XRPL (pagos, escrow, saldo)
│   ├── iso_generator.py       # Generador ISO 20022 (pacs/camt)
│   ├── receipt.py             # PDF de recibo (QTextDocument)
│   ├── audit.py               # Helper log_audit
│   └── utils.py               # Utilidades y tipos compartidos
│
├── shared_ui/                 # Componentes UI reutilizables
│   ├── theme.py               # STATUS_STYLES, make_app_icon
│   ├── components.py          # Toast, KpiCard, EmptyStateOverlay, StepIndicator, FunctionWorker
│   └── workers.py             # FunctionWorker (QThread)
│
├── admin_app/                 # Aplicación administrativa
│   └── ui_admin/
│       ├── login_window.py
│       ├── dashboard.py
│       ├── user_management.py
│       ├── price_view.py      # Precio de referencia diario
│       ├── metrics_view.py    # KPIs + gráfica QtCharts
│       └── audit_view.py      # Log de auditoría + cierre de día
│
├── payment_app/               # Aplicación de pagos
│   └── ui_payment/
│       ├── auth_flow.py       # Autenticación 3 pasos
│       ├── dashboard.py       # Saldo en tiempo real
│       ├── payment_flow.py    # Flujo completo de pago
│       ├── history_view.py    # Historial con filtros
│       ├── payment_result_dialog.py
│       ├── payment_detail_dialog.py
│       └── producer_view.py
│
├── tests/
│   └── test_core.py           # 32 tests (seguridad, ISO, utils, modelos)
│
└── scripts/
    ├── migrate_001_login_attempts.py
    ├── migrate_002_numeric.py
    └── migrate_003_daily_price.py
```

---

## Stack tecnológico

| Componente | Tecnología |
|------------|------------|
| Lenguaje | Python 3.11+ |
| UI | PySide6 6.x (Qt for Python) |
| Gráficas | PySide6.QtCharts |
| Base de datos | SQLite + SQLAlchemy 2.x |
| Blockchain | xrpl-py (XRPL Testnet) |
| Seguridad | argon2-cffi |
| XML / ISO 20022 | lxml |
| Tests | pytest |

---

## Instalación y ejecución

```bash
# Crear entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# Instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos (primera vez)
python -c "from core.database import init_db; init_db()"

# Si la DB ya existe (migraciones)
python scripts/migrate_001_login_attempts.py
python scripts/migrate_003_daily_price.py

# Ejecutar app de pagos
python -m payment_app.main_payment

# Ejecutar app administrativa
python -m admin_app.main_admin

# Correr tests
pytest tests/ -v
```

---

## Estado del proyecto

- 32 tests pasando
- Mensajería ISO 20022 con namespaces validados
- Seguridad auditada (Argon2, lockout, validación de direcciones)
- UI completamente no bloqueante para operaciones XRPL
- Escrow HTLC en desarrollo activo
