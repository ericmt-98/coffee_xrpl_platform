"""
History View Widget
Display payment history and export functionality
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QGroupBox,
    QFileDialog, QHeaderView, QAbstractItemView,
    QDateEdit, QComboBox
)
from PySide6.QtCore import Qt, QDate

from PySide6.QtGui import QKeySequence, QShortcut

from core.database import get_session, close_session
from core.models import Payment, User, PaymentStatus
from core.utils import format_currency, format_datetime_display
from shared_ui.components import make_status_item, attach_empty_state
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill


class HistoryViewWidget(QWidget):
    """Widget for viewing payment history"""

    def __init__(self, operator: User):
        super().__init__()
        self.operator = operator
        self._history_offset = 0
        self.init_ui()
        self.load_history()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Historial de Pagos")
        title.setProperty("class", "subheader")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.details_btn = QPushButton("🔍 Ver Detalles")
        self.details_btn.setProperty("class", "secondary")
        self.details_btn.setEnabled(False)
        self.details_btn.clicked.connect(self._show_details_for_selected)
        header_layout.addWidget(self.details_btn)

        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.load_history)
        header_layout.addWidget(refresh_btn)

        export_btn = QPushButton("📊 Exportar a Excel")
        export_btn.clicked.connect(self.export_to_excel)
        header_layout.addWidget(export_btn)

        layout.addLayout(header_layout)

        # Filters
        self.filter_group = self.create_filters()
        layout.addWidget(self.filter_group)

        # Payment table
        self.payment_table = QTableWidget()
        self.payment_table.setColumnCount(7)
        self.payment_table.setHorizontalHeaderLabels([
            "Fecha/Hora", "Productor", "Peso (kg)",
            "Precio/kg", "Total MXN", "Token", "Estado"
        ])
        self.payment_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.payment_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.payment_table.horizontalHeader().setStretchLastSection(True)
        self.payment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.payment_table.setAlternatingRowColors(True)
        self.payment_table.setToolTip("Doble clic para ver detalles del pago")
        self.payment_table.doubleClicked.connect(self.show_payment_details)
        self.payment_table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.payment_table)
        attach_empty_state(self.payment_table, "No hay pagos para los filtros seleccionados")

        self.load_more_btn = QPushButton("Cargar más...")
        self.load_more_btn.setProperty("class", "secondary")
        self.load_more_btn.setVisible(False)
        self.load_more_btn.clicked.connect(self._load_more)
        layout.addWidget(self.load_more_btn)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-size: 10pt; color: #605E5C; padding: 10px;")
        layout.addWidget(self.summary_label)

        QShortcut(QKeySequence("F5"), self).activated.connect(self.load_history)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.export_to_excel)

    def _on_selection_changed(self):
        self.details_btn.setEnabled(bool(self.payment_table.selectedItems()))

    def _show_details_for_selected(self):
        selected = self.payment_table.selectedItems()
        if not selected:
            return
        self._show_details_for_row(selected[0].row())

    def create_filters(self) -> QGroupBox:
        group = QGroupBox("Filtros")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Desde:"))
        self.filter_date_from = QDateEdit()
        self.filter_date_from.setCalendarPopup(True)
        self.filter_date_from.setDate(QDate.currentDate().addMonths(-1))
        self.filter_date_from.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(self.filter_date_from)

        layout.addWidget(QLabel("Hasta:"))
        self.filter_date_to = QDateEdit()
        self.filter_date_to.setCalendarPopup(True)
        self.filter_date_to.setDate(QDate.currentDate())
        self.filter_date_to.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(self.filter_date_to)

        layout.addWidget(QLabel("Estado:"))
        self.filter_status = QComboBox()
        self.filter_status.addItems([
            "Todos", "Completado", "Simulado", "Pendiente", "Fallido",
            "En Escrow", "Rechazado", "Reembolsado",
        ])
        layout.addWidget(self.filter_status)

        layout.addStretch()

        apply_btn = QPushButton("Aplicar")
        apply_btn.clicked.connect(self.load_history)
        layout.addWidget(apply_btn)

        group.setLayout(layout)
        return group

    def _build_filtered_query(self, session):
        from datetime import datetime as dt

        query = session.query(Payment).filter_by(operator_id=self.operator.id)

        date_from = self.filter_date_from.date().toPython()
        date_to = self.filter_date_to.date().toPython()
        query = query.filter(
            Payment.timestamp >= dt.combine(date_from, dt.min.time()),
            Payment.timestamp <= dt.combine(date_to, dt.max.time()),
        )

        status_map = {
            "Completado":  PaymentStatus.COMPLETED,
            "Simulado":    PaymentStatus.SIMULATED,
            "Pendiente":   PaymentStatus.PENDING,
            "Fallido":     PaymentStatus.FAILED,
            "En Escrow":   PaymentStatus.ESCROWED,
            "Rechazado":   PaymentStatus.REJECTED,
            "Reembolsado": PaymentStatus.REFUNDED,
        }
        status_text = self.filter_status.currentText()
        if status_text in status_map:
            query = query.filter(Payment.status == status_map[status_text])

        return query

    def _fill_payment_row(self, row: int, payment) -> tuple:
        """Fill row cells. Returns (amount_mxn, weight_kg) for summary accumulation."""
        item = QTableWidgetItem(format_datetime_display(payment.timestamp))
        item.setData(Qt.UserRole, payment.id)
        self.payment_table.setItem(row, 0, item)
        self.payment_table.setItem(row, 1, QTableWidgetItem(payment.producer.name))

        weight_val = 0.0
        if payment.delivery:
            weight_val = float(payment.delivery.weight_kg)
            self.payment_table.setItem(row, 2, QTableWidgetItem(f"{weight_val:.2f}"))
            self.payment_table.setItem(row, 3, QTableWidgetItem(
                format_currency(float(payment.delivery.price_per_kg), "MXN")))
        else:
            self.payment_table.setItem(row, 2, QTableWidgetItem("—"))
            self.payment_table.setItem(row, 3, QTableWidgetItem("—"))

        mxn_val = 0.0
        if payment.amount_mxn:
            mxn_val = float(payment.amount_mxn)
            self.payment_table.setItem(row, 4, QTableWidgetItem(format_currency(mxn_val, "MXN")))
        else:
            self.payment_table.setItem(row, 4, QTableWidgetItem("—"))

        self.payment_table.setItem(row, 5, QTableWidgetItem(
            f"{float(payment.amount):.6f} {payment.currency}"))
        self.payment_table.setItem(row, 6, make_status_item(payment.status.value))
        return mxn_val, weight_val

    def load_history(self):
        try:
            self._history_offset = 0
            session = get_session()

            payments = self._build_filtered_query(session).order_by(
                Payment.timestamp.desc()
            ).limit(200).all()
            total_count = self._build_filtered_query(session).count()

            self.payment_table.setRowCount(len(payments))
            total_mxn = 0.0
            total_kg = 0.0
            for row, payment in enumerate(payments):
                mxn, kg = self._fill_payment_row(row, payment)
                total_mxn += mxn
                total_kg += kg

            self.summary_label.setText(
                f"Mostrando {len(payments)} de {total_count} | "
                f"Total kg: {total_kg:.2f} | Total MXN: {format_currency(total_mxn, 'MXN')}"
            )
            self.load_more_btn.setVisible(total_count > 200)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar historial:\n{str(e)}")
        finally:
            close_session()

    def _load_more(self):
        try:
            session = get_session()
            self._history_offset += 200
            more_payments = (
                self._build_filtered_query(session)
                .order_by(Payment.timestamp.desc())
                .offset(self._history_offset)
                .limit(200)
                .all()
            )
            current_rows = self.payment_table.rowCount()
            self.payment_table.setRowCount(current_rows + len(more_payments))
            total_count = self._build_filtered_query(session).count()

            for idx, payment in enumerate(more_payments):
                self._fill_payment_row(current_rows + idx, payment)

            self.load_more_btn.setVisible(self.payment_table.rowCount() < total_count)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar más pagos:\n{str(e)}")
        finally:
            close_session()

    def show_payment_details(self, index):
        """Double-click handler."""
        self._show_details_for_row(index.row())

    def _show_details_for_row(self, row: int):
        try:
            item = self.payment_table.item(row, 0)
            if not item:
                return
            payment_id = item.data(Qt.UserRole)
            if not payment_id:
                return
            session = get_session()
            payment = session.query(Payment).filter_by(id=payment_id).first()
            if not payment:
                return

            # Load all data as primitives BEFORE closing session
            from shared_ui.theme import STATUS_STYLES
            status_label = STATUS_STYLES.get(
                payment.status.value, (payment.status.value.capitalize(), '', '')
            )[0]

            data = {
                'uetr':             payment.uetr,
                'tx_hash':          payment.xrpl_tx_hash,
                'timestamp_str':    format_datetime_display(payment.timestamp),
                'status_label':     status_label,
                'producer_name':    payment.producer.name,
                'producer_address': payment.producer.xrpl_address,
                'token_amount':     float(payment.amount),
                'currency':         payment.currency,
                'notes':            payment.notes,
                'operator_name':    payment.operator.full_name if payment.operator else '—',
            }
            if payment.delivery:
                data['weight_kg']   = float(payment.delivery.weight_kg)
                data['price_per_kg'] = float(payment.delivery.price_per_kg)
                data['total_mxn']   = float(payment.delivery.total_mxn)

            data['iso_messages'] = [
                {'type': m.message_type.value, 'xml': m.xml_content}
                for m in payment.iso_messages
            ]

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar detalles:\n{str(e)}")
            return
        finally:
            close_session()

        from payment_app.ui_payment.payment_detail_dialog import PaymentDetailDialog
        PaymentDetailDialog(data, parent=self).exec()

    def export_to_excel(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Historial",
                f"historial_pagos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel Files (*.xlsx)"
            )
            if not file_path:
                return

            session = get_session()
            payments = self._build_filtered_query(session).order_by(
                Payment.timestamp.desc()
            ).all()

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Historial de Pagos"

            headers = [
                "Fecha/Hora", "UETR", "Hash XRPL", "Productor",
                "Peso (kg)", "Precio/kg", "Total MXN",
                "Token", "Cantidad Token", "Estado", "Notas"
            ]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="0078D4", end_color="0078D4", fill_type="solid")

            for row, payment in enumerate(payments, 2):
                ws.cell(row=row, column=1, value=format_datetime_display(payment.timestamp))
                ws.cell(row=row, column=2, value=payment.uetr)
                ws.cell(row=row, column=3, value=payment.xrpl_tx_hash)
                ws.cell(row=row, column=4, value=payment.producer.name)
                if payment.delivery:
                    ws.cell(row=row, column=5, value=payment.delivery.weight_kg)
                    ws.cell(row=row, column=6, value=payment.delivery.price_per_kg)
                    ws.cell(row=row, column=7, value=payment.delivery.total_mxn)
                ws.cell(row=row, column=8, value=payment.currency)
                ws.cell(row=row, column=9, value=payment.amount)
                ws.cell(row=row, column=10, value=payment.status.value)
                ws.cell(row=row, column=11, value=payment.notes or "")

            wb.save(file_path)
            from shared_ui.components import Toast
            Toast.show_message(self, "✓ Historial exportado")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar historial:\n{str(e)}")
        finally:
            close_session()
