"""
Main Dashboard for Payment Application
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QMessageBox,
    QStatusBar
)
from PySide6.QtCore import Qt

from payment_app.ui_payment.styles import PAYMENT_STYLESHEET
from payment_app.ui_payment.producer_view import ProducerManagementWidget
from payment_app.ui_payment.payment_flow import PaymentFlowWidget
from payment_app.ui_payment.history_view import HistoryViewWidget
from core.models import User


class PaymentDashboard(QMainWindow):
    """Main dashboard window for Payment application"""
    
    def __init__(self, operator: User, xrpl_seed: str):
        super().__init__()
        self.operator = operator
        self.xrpl_seed = xrpl_seed  # Stored in RAM only
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
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
        self.payment_widget = PaymentFlowWidget(self.operator, self.xrpl_seed)
        self.payment_widget.payment_completed.connect(self.on_payment_completed)
        self.tabs.addTab(self.payment_widget, "💰 Realizar Pago")
        
        # History tab
        self.history_widget = HistoryViewWidget(self.operator)
        self.tabs.addTab(self.history_widget, "📋 Historial")
        
        right_layout.addWidget(self.tabs)
        content_layout.addWidget(right_widget, 3)
        
        main_layout.addLayout(content_layout)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("Listo")
    
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
        
        # Logout button
        logout_btn = QPushButton("Cerrar Sesión")
        logout_btn.setProperty("class", "secondary")
        logout_btn.clicked.connect(self.logout)
        layout.addWidget(logout_btn)
        
        return layout
    
    def on_producer_selected(self, producer):
        """Handle producer selection"""
        self.payment_widget.set_producer(producer)
        self.tabs.setCurrentIndex(0)  # Switch to payment tab
        self.update_status(f"Productor seleccionado: {producer.name}")
    
    def on_payment_completed(self, payment):
        """Handle payment completion"""
        self.history_widget.load_history()
        self.update_status(f"Pago completado - UETR: {payment.uetr}")
        
        # Show success notification
        QMessageBox.information(
            self,
            "Pago Registrado",
            f"El pago ha sido registrado exitosamente.\n\n"
            f"Puede ver los detalles en el historial."
        )
    
    def update_status(self, message: str):
        """Update status bar message"""
        self.status_bar.showMessage(f"🟢 {message}")
    
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
            # Clear sensitive data
            self.xrpl_seed = None
            self.close()
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Clear sensitive data from memory
        self.xrpl_seed = None
        event.accept()
