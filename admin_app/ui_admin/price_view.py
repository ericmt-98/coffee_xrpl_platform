"""
Daily Price Management Widget for Admin Application
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QMessageBox, QGroupBox,
    QHeaderView, QAbstractItemView, QDateEdit
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor

from core.database import get_session, close_session
from core.models import DailyPrice, AuditLog
from core.audit import log_audit
from shared_ui.components import attach_empty_state
from PySide6.QtGui import QColor, QBrush
from datetime import datetime, timezone, date


class DailyPriceWidget(QWidget):
    """Widget for managing daily reference coffee prices"""

    def __init__(self, admin_user):
        super().__init__()
        self.admin_user = admin_user
        self.init_ui()
        self.load_prices()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        header = QLabel("Precio de Referencia del Día")
        header.setProperty("class", "subheader")
        layout.addWidget(header)

        # Set price form
        form_group = QGroupBox("Establecer Precio del Día")
        form_layout = QFormLayout()

        self.price_date_input = QDateEdit()
        self.price_date_input.setCalendarPopup(True)
        self.price_date_input.setDate(QDate.currentDate())
        self.price_date_input.setDisplayFormat("dd/MM/yyyy")
        form_layout.addRow("Fecha:", self.price_date_input)

        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0.01, 99999.99)
        self.price_input.setDecimals(2)
        self.price_input.setPrefix("$ ")
        self.price_input.setSuffix(" MXN/kg")
        self.price_input.setValue(50.0)
        form_layout.addRow("Precio por kg:", self.price_input)

        save_btn = QPushButton("💾 Guardar Precio")
        save_btn.clicked.connect(self.save_price)
        form_layout.addRow("", save_btn)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Price history table
        hist_group = QGroupBox("Historial de Precios")
        hist_layout = QVBoxLayout()

        self.price_table = QTableWidget()
        self.price_table.setColumnCount(3)
        self.price_table.setHorizontalHeaderLabels(["Fecha", "Precio/kg", "Registrado por"])
        self.price_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.price_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.price_table.horizontalHeader().setStretchLastSection(True)
        self.price_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.price_table.setAlternatingRowColors(True)
        self.price_table.setSortingEnabled(True)
        hist_layout.addWidget(self.price_table)
        attach_empty_state(self.price_table, "Sin precios registrados")

        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.load_prices)
        hist_layout.addWidget(refresh_btn, alignment=Qt.AlignRight)

        hist_group.setLayout(hist_layout)
        layout.addWidget(hist_group)

        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence("F5"), self).activated.connect(self.load_prices)

    def save_price(self):
        """Save or update the daily price"""
        try:
            selected_date = self.price_date_input.date().toPython()
            price_val = self.price_input.value()

            # Convert date to datetime for storage
            price_dt = datetime.combine(selected_date, datetime.min.time())

            session = get_session()
            existing = session.query(DailyPrice).filter_by(price_date=price_dt).first()

            if existing:
                reply = QMessageBox.question(
                    self,
                    "Precio Existente",
                    f"Ya existe un precio para {selected_date.strftime('%d/%m/%Y')}.\n"
                    f"¿Desea actualizarlo?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
                existing.price_per_kg = price_val
                action = "Precio del día actualizado"
            else:
                new_price = DailyPrice(
                    price_date=price_dt,
                    price_per_kg=price_val,
                    set_by_user_id=self.admin_user.id,
                )
                session.add(new_price)
                action = "Precio del día establecido"

            log_audit(session, self.admin_user.id, action,
                      f"Fecha: {selected_date} | Precio: ${price_val:.2f}/kg")
            session.commit()

            from shared_ui.components import Toast
            Toast.show_message(
                self,
                f"✓ Precio guardado: ${price_val:.2f}/kg — {selected_date.strftime('%d/%m/%Y')}"
            )
            self.load_prices()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar precio:\n{str(e)}")
        finally:
            close_session()

    def load_prices(self):
        """Load price history into table"""
        try:
            session = get_session()
            prices = session.query(DailyPrice).order_by(DailyPrice.price_date.desc()).limit(30).all()

            today_date = date.today()
            self.price_table.setRowCount(len(prices))
            for row, price in enumerate(prices):
                date_str = price.price_date.strftime("%d/%m/%Y")
                user_name = price.set_by_user.full_name if price.set_by_user else "—"

                items = [
                    QTableWidgetItem(date_str),
                    QTableWidgetItem(f"${float(price.price_per_kg):.2f} MXN/kg"),
                    QTableWidgetItem(user_name),
                ]
                is_today = price.price_date.date() == today_date
                for col, item in enumerate(items):
                    if is_today:
                        item.setBackground(QBrush(QColor("#DFF6DD")))
                    self.price_table.setItem(row, col, item)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar precios:\n{str(e)}")
        finally:
            close_session()
