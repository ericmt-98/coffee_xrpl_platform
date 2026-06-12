"""
Metrics Dashboard Widget for Admin Application
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.database import get_session, close_session
from core.models import Payment, Delivery, Producer, PaymentStatus
from core.utils import format_currency
from datetime import datetime, timezone
from sqlalchemy import func


class MetricsWidget(QWidget):
    """Admin metrics dashboard — monthly summary and top producers"""

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.refresh_metrics()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Header
        header_row = QHBoxLayout()
        header = QLabel("Resumen del Mes")
        header.setProperty("class", "subheader")
        header_row.addWidget(header)
        header_row.addStretch()

        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.refresh_metrics)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # KPI cards
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(15)

        self.card_total_mxn = self._make_card("Total Pagado", "$0.00 MXN", "#0078D4")
        self.cards_layout.addWidget(self.card_total_mxn, 0, 0)

        self.card_kg = self._make_card("Kg Acopiados", "0.00 kg", "#107C10")
        self.cards_layout.addWidget(self.card_kg, 0, 1)

        self.card_payments = self._make_card("Pagos Realizados", "0", "#8764B8")
        self.cards_layout.addWidget(self.card_payments, 0, 2)

        self.card_producers = self._make_card("Productores Activos", "0", "#D83B01")
        self.cards_layout.addWidget(self.card_producers, 0, 3)

        layout.addLayout(self.cards_layout)

        # Top 5 producers
        top_group = QGroupBox("Top 5 Productores del Mes (por kg)")
        top_layout = QVBoxLayout()

        self.top_table = QTableWidget()
        self.top_table.setColumnCount(4)
        self.top_table.setHorizontalHeaderLabels(["Productor", "Kg", "Pagos", "Total MXN"])
        self.top_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.top_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.top_table.horizontalHeader().setStretchLastSection(True)
        self.top_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.top_table.setMaximumHeight(220)
        top_layout.addWidget(self.top_table)

        top_group.setLayout(top_layout)
        layout.addWidget(top_group)

        layout.addStretch()

    def _make_card(self, title: str, value: str, color: str) -> QGroupBox:
        """Create a KPI card widget"""
        card = QGroupBox(title)
        card_layout = QVBoxLayout()
        val_label = QLabel(value)
        val_label.setAlignment(Qt.AlignCenter)
        val_label.setStyleSheet(
            f"font-size: 20pt; font-weight: bold; color: {color}; padding: 10px;"
        )
        val_label.setObjectName("kpi_value")
        card_layout.addWidget(val_label)
        card.setLayout(card_layout)
        return card

    def _get_card_label(self, card: QGroupBox) -> QLabel:
        return card.findChild(QLabel, "kpi_value")

    def refresh_metrics(self):
        """Load current month metrics from DB"""
        try:
            session = get_session()
            now = datetime.now(timezone.utc)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Total MXN paid this month (COMPLETED + SIMULATED)
            total_mxn_result = session.query(
                func.sum(Payment.amount_mxn)
            ).filter(
                Payment.timestamp >= month_start,
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.SIMULATED])
            ).scalar() or 0

            # Total kg this month
            total_kg_result = session.query(
                func.sum(Delivery.weight_kg)
            ).join(Payment).filter(
                Payment.timestamp >= month_start,
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.SIMULATED])
            ).scalar() or 0

            # Payment count this month
            payment_count = session.query(func.count(Payment.id)).filter(
                Payment.timestamp >= month_start,
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.SIMULATED])
            ).scalar() or 0

            # Active producers count
            active_producers = session.query(func.count(Producer.id)).filter(
                Producer.is_active == True
            ).scalar() or 0

            # Update cards
            self._get_card_label(self.card_total_mxn).setText(
                format_currency(float(total_mxn_result), "MXN")
            )
            self._get_card_label(self.card_kg).setText(f"{float(total_kg_result):.2f} kg")
            self._get_card_label(self.card_payments).setText(str(payment_count))
            self._get_card_label(self.card_producers).setText(str(active_producers))

            # Top 5 producers by kg
            top_producers = session.query(
                Producer.name,
                func.sum(Delivery.weight_kg).label("total_kg"),
                func.count(Payment.id).label("pay_count"),
                func.sum(Payment.amount_mxn).label("total_mxn"),
            ).join(Payment, Payment.producer_id == Producer.id)\
             .join(Delivery, Delivery.payment_id == Payment.id)\
             .filter(
                Payment.timestamp >= month_start,
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.SIMULATED])
            ).group_by(Producer.id)\
             .order_by(func.sum(Delivery.weight_kg).desc())\
             .limit(5).all()

            self.top_table.setRowCount(len(top_producers))
            for row, prod in enumerate(top_producers):
                self.top_table.setItem(row, 0, QTableWidgetItem(prod.name))
                self.top_table.setItem(row, 1, QTableWidgetItem(f"{float(prod.total_kg):.2f}"))
                self.top_table.setItem(row, 2, QTableWidgetItem(str(prod.pay_count)))
                self.top_table.setItem(row, 3, QTableWidgetItem(
                    format_currency(float(prod.total_mxn or 0), "MXN")
                ))

        except Exception as e:
            # Metrics failure must not crash the app
            import traceback
            traceback.print_exc()
        finally:
            close_session()
