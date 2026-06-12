"""
Metrics Dashboard Widget for Admin Application
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt

from core.database import get_session, close_session
from core.models import Payment, Delivery, Producer, PaymentStatus
from core.utils import format_currency
from shared_ui.components import KpiCard, attach_empty_state
from datetime import datetime, timezone
from sqlalchemy import func

try:
    from PySide6.QtCharts import (
        QChart, QChartView, QBarSeries, QBarSet,
        QBarCategoryAxis, QValueAxis,
    )
    _CHARTS_AVAILABLE = True
except ImportError:
    _CHARTS_AVAILABLE = False


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

        # KPI cards (using shared KpiCard component)
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(15)

        self.card_total_mxn = KpiCard("Total Pagado", "$0.00 MXN", "#0078D4")
        self.cards_layout.addWidget(self.card_total_mxn, 0, 0)

        self.card_kg = KpiCard("Kg Acopiados", "0.00 kg", "#107C10")
        self.cards_layout.addWidget(self.card_kg, 0, 1)

        self.card_payments = KpiCard("Pagos Realizados", "0", "#8764B8")
        self.cards_layout.addWidget(self.card_payments, 0, 2)

        self.card_producers = KpiCard("Productores Activos", "0", "#D83B01")
        self.cards_layout.addWidget(self.card_producers, 0, 3)

        layout.addLayout(self.cards_layout)

        # Bar chart: payments by day (requires QtCharts)
        if _CHARTS_AVAILABLE:
            chart_group = QGroupBox("Pagos por Día (mes actual)")
            chart_group_layout = QVBoxLayout()
            self._chart_view = QChartView()
            self._chart_view.setMaximumHeight(260)
            self._chart_view.setRenderHint(self._chart_view.renderHints())
            chart_group_layout.addWidget(self._chart_view)
            chart_group.setLayout(chart_group_layout)
            layout.addWidget(chart_group)
            self._chart_view_ref = self._chart_view
        else:
            self._chart_view_ref = None

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
        self.top_table.setAlternatingRowColors(True)
        self.top_table.setSortingEnabled(True)
        top_layout.addWidget(self.top_table)
        attach_empty_state(self.top_table, "Sin datos de productores este mes")

        top_group.setLayout(top_layout)
        layout.addWidget(top_group)

        layout.addStretch()

        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence("F5"), self).activated.connect(self.refresh_metrics)

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
            self.card_total_mxn.set_value(format_currency(float(total_mxn_result), "MXN"))
            self.card_kg.set_value(f"{float(total_kg_result):.2f} kg")
            self.card_payments.set_value(str(payment_count))
            self.card_producers.set_value(str(active_producers))

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

            # Bar chart: MXN by day this month
            if _CHARTS_AVAILABLE and self._chart_view_ref is not None:
                daily_rows = session.query(
                    func.date(Payment.timestamp).label("day"),
                    func.sum(Payment.amount_mxn).label("total"),
                ).filter(
                    Payment.timestamp >= month_start,
                    Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.SIMULATED]),
                ).group_by(func.date(Payment.timestamp)).order_by(
                    func.date(Payment.timestamp)
                ).all()

                bar_set = QBarSet("MXN")
                bar_set.setColor("#0078D4")  # type: ignore[attr-defined]
                categories = []
                for d in daily_rows:
                    day_label = str(d.day)[-2:].lstrip("0") or "1"
                    categories.append(day_label)
                    bar_set.append(float(d.total or 0))  # type: ignore[attr-defined]

                series = QBarSeries()
                series.append(bar_set)

                chart = QChart()
                chart.addSeries(series)
                chart.setTheme(QChart.ChartThemeLight)
                chart.legend().setVisible(False)
                chart.setAnimationOptions(QChart.NoAnimation)

                axis_x = QBarCategoryAxis()
                axis_x.append(categories)
                chart.addAxis(axis_x, Qt.AlignBottom)
                series.attachAxis(axis_x)

                axis_y = QValueAxis()
                axis_y.setLabelFormat("$%.0f")
                chart.addAxis(axis_y, Qt.AlignLeft)
                series.attachAxis(axis_y)

                self._chart_view_ref.setChart(chart)

        except Exception as e:
            # Metrics failure must not crash the app
            import traceback
            traceback.print_exc()
        finally:
            close_session()
