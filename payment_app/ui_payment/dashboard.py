"""
Main Dashboard for Payment Application
"""

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QMessageBox,
    QStatusBar
)
from PySide6.QtCore import Qt

from payment_app.ui_payment.styles import PAYMENT_STYLESHEET
from payment_app.ui_payment.producer_view import ProducerManagementWidget
from payment_app.ui_payment.payment_flow import PaymentFlowWidget
from payment_app.ui_payment.history_view import HistoryViewWidget
from payment_app.ui_payment.escrow_view import EscrowManagementWidget
from core.models import User
from core.xrpl_client import XRPLClient


class PaymentDashboard(QMainWindow):
    """Main dashboard window for Payment application"""
    
    def __init__(self, operator: User, xrpl_seed: str, xrpl_client=None):
        super().__init__()
        self.operator = operator
        self.xrpl_seed = xrpl_seed  # Stored in RAM only
        self._xrpl_client = xrpl_client or XRPLClient()
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        self._xrpl_ok = True  # tracks last balance refresh result for status indicator
        self.setWindowTitle("Coffee XRPL Platform - Sistema de Pagos")
        self.setMinimumSize(1400, 900)
        
        # Apply stylesheet
        self.setStyleSheet(PAYMENT_STYLESHEET)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Header
        header_layout = self.create_header()
        main_layout.addLayout(header_layout)
        
        # Content layout (two columns)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # Left column: Producer management
        self.producer_widget = ProducerManagementWidget()
        self.producer_widget.producer_selected.connect(self.on_producer_selected)
        content_layout.addWidget(self.producer_widget, 2)
        
        # Right column: Tabs for payment and history
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        
        # Payment tab
        self.payment_widget = PaymentFlowWidget(self.operator, self.xrpl_seed, xrpl_client=self._xrpl_client)
        self.payment_widget.payment_completed.connect(self.on_payment_completed)
        self.tabs.addTab(self.payment_widget, "💰 Realizar Pago")
        
        # History tab
        self.history_widget = HistoryViewWidget(self.operator)
        self.tabs.addTab(self.history_widget, "📋 Historial")

        # Escrows tab
        self.escrow_widget = EscrowManagementWidget(self.operator, self.xrpl_seed)
        self.tabs.addTab(self.escrow_widget, "⏳ Escrows")

        right_layout.addWidget(self.tabs)
        content_layout.addWidget(right_widget, 3)
        
        main_layout.addLayout(content_layout)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("Listo")

        # Load initial balance (best-effort, non-blocking via cursor)
        try:
            self.refresh_balance()
        except Exception:
            pass
    
    def create_header(self) -> QHBoxLayout:
        """Create the header section"""
        layout = QHBoxLayout()
        
        # Title
        title = QLabel("☕ Sistema de Pagos a Productores")
        title.setProperty("class", "header")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # User info
        user_label = QLabel(f"👤 {self.operator.full_name}")
        user_label.setStyleSheet("font-size: 11pt; font-weight: 600;")
        layout.addWidget(user_label)

        # Balance label
        self.balance_label = QLabel("💧 Saldo: --")
        self.balance_label.setStyleSheet("font-size: 10pt; color: #0078D4;")
        layout.addWidget(self.balance_label)

        # Refresh balance button
        refresh_balance_btn = QPushButton("🔄")
        refresh_balance_btn.setProperty("class", "secondary")
        refresh_balance_btn.setFixedWidth(40)
        refresh_balance_btn.setToolTip("Actualizar saldo")
        refresh_balance_btn.clicked.connect(self.refresh_balance)
        layout.addWidget(refresh_balance_btn)

        # Logout button
        logout_btn = QPushButton("Cerrar Sesión")
        logout_btn.setProperty("class", "secondary")
        logout_btn.clicked.connect(self.logout)
        layout.addWidget(logout_btn)
        
        return layout
    
    def refresh_balance(self):
        """Fetch and display XRP balance in a background thread (non-blocking)."""
        if not self.operator.xrpl_address:
            return
        self.balance_label.setText("💧 Saldo: ⏳")
        from shared_ui.workers import FunctionWorker
        self._balance_worker = FunctionWorker(
            self._xrpl_client.get_balance,
            self.operator.xrpl_address,
        )
        self._balance_worker.finished_ok.connect(self._on_balance_ok)
        self._balance_worker.failed.connect(self._on_balance_fail)
        self._balance_worker.start()

    def _on_balance_ok(self, balance_info: dict):
        xrp = balance_info.get('xrp', 0)
        self.balance_label.setText(f"💧 Saldo: {xrp:.6f} XRP")
        self._xrpl_ok = True
        self.update_status("Listo")

    def _on_balance_fail(self, _error: str):
        self.balance_label.setText("💧 Saldo: sin conexión")
        self._xrpl_ok = False
        self.update_status("Sin conexión a XRPL Testnet")

    def on_producer_selected(self, producer):
        """Handle producer selection"""
        self.payment_widget.set_producer(producer)
        self.tabs.setCurrentIndex(0)  # Switch to payment tab
        self.update_status(f"Productor seleccionado: {producer.name}")
    
    def on_payment_completed(self, payment):
        """Handle payment completion"""
        self.history_widget.load_history()
        self.escrow_widget.load_escrows()
        self.update_status(f"Pago completado - UETR: {payment.uetr}")
        self.refresh_balance()
    
    def update_status(self, message: str):
        icon = "🟢" if getattr(self, '_xrpl_ok', True) else "🔴"
        self.status_bar.showMessage(f"{icon} {message}")
    
    def logout(self):
        """Handle logout"""
        reply = QMessageBox.question(
            self,
            "Confirmar Cierre de Sesión",
            "¿Está seguro que desea cerrar sesión?\n\n"
            "Su clave privada XRPL será eliminada de la memoria.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from core.database import get_session, close_session
                from core.audit import log_audit
                audit_session = get_session()
                try:
                    log_audit(audit_session, self.operator.id, "Cierre de sesión de Pagos",
                              f"Usuario: {self.operator.username}")
                    audit_session.commit()
                finally:
                    close_session()
            except Exception:
                pass

            # Clear sensitive data
            self.xrpl_seed = None
            self.close()
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Clear sensitive data from memory
        self.xrpl_seed = None
        event.accept()
