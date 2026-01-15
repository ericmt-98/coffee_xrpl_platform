"""
Main Dashboard for Admin Application
"""

import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QMessageBox,
    QStatusBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from admin_app.ui_admin.styles import ADMIN_STYLESHEET
from admin_app.ui_admin.user_management import UserManagementWidget
from admin_app.ui_admin.audit_view import AuditViewWidget
from core.database import get_session, close_session
from core.models import User, UserRole, AuditLog
from datetime import datetime


class AdminDashboard(QMainWindow):
    """Main dashboard window for Admin application"""
    
    def __init__(self, admin_user: User):
        super().__init__()
        self.admin_user = admin_user
        self.init_ui()
        self.log_action("Inicio de sesión en aplicación Admin")
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Coffee XRPL Platform - Administrador")
        self.setMinimumSize(1200, 800)
        
        # Apply stylesheet
        self.setStyleSheet(ADMIN_STYLESHEET)
        
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
        
        # Tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Add tabs
        self.user_management_tab = UserManagementWidget(self.admin_user)
        self.tabs.addTab(self.user_management_tab, "👥 Gestión de Usuarios")
        
        self.audit_tab = AuditViewWidget()
        self.tabs.addTab(self.audit_tab, "📋 Auditoría y Exportación")
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"Conectado como: {self.admin_user.full_name}")
    
    def create_header(self) -> QHBoxLayout:
        """Create the header section"""
        layout = QHBoxLayout()
        
        # Title
        title = QLabel("Panel de Administración")
        title.setProperty("class", "header")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # User info
        user_label = QLabel(f"👤 {self.admin_user.full_name}")
        user_label.setStyleSheet("font-size: 11pt; font-weight: 600;")
        layout.addWidget(user_label)
        
        # Change Password button
        change_pwd_btn = QPushButton("🔑 Cambiar Contraseña")
        change_pwd_btn.setProperty("class", "secondary")
        change_pwd_btn.clicked.connect(self.change_password)
        layout.addWidget(change_pwd_btn)
        
        # Logout button
        logout_btn = QPushButton("Cerrar Sesión")
        logout_btn.setProperty("class", "secondary")
        logout_btn.clicked.connect(self.logout)
        layout.addWidget(logout_btn)
        
        return layout
    
    def log_action(self, action: str, details: str = None):
        """Log an admin action to the audit log"""
        try:
            session = get_session()
            log_entry = AuditLog(
                user_id=self.admin_user.id,
                action=action,
                details=details,
                timestamp=datetime.utcnow()
            )
            session.add(log_entry)
            session.commit()
        except Exception as e:
            print(f"Error logging action: {e}")
        finally:
            close_session()
    
    def change_password(self):
        """Handle password change"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel
        from core.security import hash_password, verify_password
        
        # Create password change dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Cambiar Contraseña")
        dialog.setFixedSize(450, 300)
        dialog.setStyleSheet(ADMIN_STYLESHEET)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("Cambiar Contraseña de Administrador")
        title.setProperty("class", "subheader")
        layout.addWidget(title)
        
        # Form
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(12)
        
        current_pwd = QLineEdit()
        current_pwd.setEchoMode(QLineEdit.Password)
        current_pwd.setPlaceholderText("Contraseña actual")
        form_layout.addRow("Contraseña Actual:*", current_pwd)
        
        new_pwd = QLineEdit()
        new_pwd.setEchoMode(QLineEdit.Password)
        new_pwd.setPlaceholderText("Mínimo 8 caracteres")
        form_layout.addRow("Nueva Contraseña:*", new_pwd)
        
        confirm_pwd = QLineEdit()
        confirm_pwd.setEchoMode(QLineEdit.Password)
        confirm_pwd.setPlaceholderText("Repita la nueva contraseña")
        form_layout.addRow("Confirmar Nueva:*", confirm_pwd)
        
        layout.addLayout(form_layout)
        
        # Buttons
        from PySide6.QtWidgets import QHBoxLayout
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        btn_layout.addStretch()
        
        save_btn = QPushButton("💾 Guardar Nueva Contraseña")
        save_btn.clicked.connect(lambda: self.save_new_password(
            dialog, current_pwd.text(), new_pwd.text(), confirm_pwd.text()
        ))
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def save_new_password(self, dialog, current, new, confirm):
        """Save the new password"""
        from core.security import hash_password, verify_password
        
        # Validate inputs
        if not all([current, new, confirm]):
            QMessageBox.warning(dialog, "Campos Incompletos", "Por favor, complete todos los campos.")
            return
        
        if len(new) < 8:
            QMessageBox.warning(dialog, "Contraseña Débil", "La nueva contraseña debe tener al menos 8 caracteres.")
            return
        
        if new != confirm:
            QMessageBox.warning(dialog, "Contraseñas No Coinciden", "La nueva contraseña y la confirmación no coinciden.")
            return
        
        # Verify current password
        if not verify_password(self.admin_user.password_hash, current):
            QMessageBox.warning(dialog, "Contraseña Incorrecta", "La contraseña actual es incorrecta.")
            return
        
        # Update password
        try:
            session = get_session()
            user = session.query(User).filter_by(id=self.admin_user.id).first()
            user.password_hash = hash_password(new)
            session.commit()
            
            # Update local reference
            self.admin_user.password_hash = user.password_hash
            
            # Log action
            self.log_action("Cambio de contraseña")
            
            QMessageBox.information(
                dialog,
                "Contraseña Actualizada",
                "✓ Su contraseña ha sido actualizada exitosamente."
            )
            
            dialog.accept()
            
        except Exception as e:
            QMessageBox.critical(dialog, "Error", f"Error al cambiar contraseña:\n{str(e)}")
        finally:
            close_session()
    
    def logout(self):
        """Handle logout"""
        reply = QMessageBox.question(
            self,
            "Confirmar Cierre de Sesión",
            "¿Está seguro que desea cerrar sesión?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.log_action("Cierre de sesión")
            self.close()
    
    def closeEvent(self, event):
        """Handle window close event"""
        close_session()
        event.accept()
