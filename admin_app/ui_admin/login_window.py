"""
Login Window for Admin Application
Handles initial setup and admin authentication
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
    QWidget, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from admin_app.ui_admin.styles import ADMIN_STYLESHEET
from core.database import get_session, close_session, database_exists, init_database
from core.models import User, UserRole
from core.security import hash_password, verify_password
from shared_ui.components import add_password_toggle
from datetime import datetime, timezone


class LoginWindow(QDialog):
    """Login window for admin application"""
    
    def __init__(self):
        super().__init__()
        self.authenticated_user = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Coffee XRPL Platform - Administrador")
        self.setFixedSize(600, 650)  # Increased from 500x400
        self.setStyleSheet(ADMIN_STYLESHEET)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)  # Reduced from 20 for better fit
        layout.setContentsMargins(40, 30, 40, 30)  # Adjusted margins
        
        # Logo/Title
        title = QLabel("☕ Coffee XRPL Platform")
        title.setProperty("class", "header")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Panel de Administración")
        subtitle.setProperty("class", "subheader")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addSpacing(15)  # Reduced from 20
        
        # Check if database exists
        if not database_exists():
            self.show_setup_form(layout)
        else:
            self.show_login_form(layout)
    
    def show_setup_form(self, parent_layout: QVBoxLayout):
        """Show initial setup form"""
        info = QLabel(
            "⚠️ Base de datos no encontrada\n\n"
            "Configure el sistema creando el primer usuario administrador."
        )
        info.setAlignment(Qt.AlignCenter)
        info.setWordWrap(True)
        info.setStyleSheet("background-color: #FFF4CE; padding: 15px; border-radius: 4px;")
        parent_layout.addWidget(info)
        
        # Setup form
        form_group = QGroupBox("Configuración Inicial")
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(15)  # Add spacing between rows
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        self.setup_name_input = QLineEdit()
        self.setup_name_input.setPlaceholderText("Ej: Administrador Sistema")
        form_layout.addRow("Nombre Completo:*", self.setup_name_input)
        
        self.setup_username_input = QLineEdit()
        self.setup_username_input.setPlaceholderText("Ej: admin")
        form_layout.addRow("Usuario:*", self.setup_username_input)
        
        self.setup_password_input = QLineEdit()
        self.setup_password_input.setEchoMode(QLineEdit.Password)
        self.setup_password_input.setPlaceholderText("Mínimo 8 caracteres")
        form_layout.addRow("Contraseña:*", self.setup_password_input)
        
        self.setup_password_confirm_input = QLineEdit()
        self.setup_password_confirm_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Confirmar Contraseña:*", self.setup_password_confirm_input)
        
        form_group.setLayout(form_layout)
        parent_layout.addWidget(form_group)
        
        # Setup button
        setup_btn = QPushButton("🔧 Inicializar Sistema")
        setup_btn.clicked.connect(self.initialize_system)
        parent_layout.addWidget(setup_btn)
        
        parent_layout.addStretch()
    
    def show_login_form(self, parent_layout: QVBoxLayout):
        """Show login form"""
        info = QLabel("Ingrese sus credenciales de administrador")
        info.setAlignment(Qt.AlignCenter)
        parent_layout.addWidget(info)
        
        # Login form
        form_group = QGroupBox("Iniciar Sesión")
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuario")
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())
        form_layout.addRow("Usuario:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Contraseña")
        self.password_input.returnPressed.connect(self.login)
        pwd_toggle = add_password_toggle(self.password_input)
        pwd_row = QHBoxLayout()
        pwd_row.addWidget(self.password_input)
        pwd_row.addWidget(pwd_toggle)
        form_layout.addRow("Contraseña:", pwd_row)
        
        form_group.setLayout(form_layout)
        parent_layout.addWidget(form_group)
        
        # Login button
        login_btn = QPushButton("🔐 Iniciar Sesión")
        login_btn.clicked.connect(self.login)
        parent_layout.addWidget(login_btn)
        
        parent_layout.addStretch()
    
    def initialize_system(self):
        """Initialize the system with first admin user"""
        try:
            # Validate inputs
            name = self.setup_name_input.text().strip()
            username = self.setup_username_input.text().strip()
            password = self.setup_password_input.text()
            password_confirm = self.setup_password_confirm_input.text()
            
            if not all([name, username, password, password_confirm]):
                QMessageBox.warning(
                    self,
                    "Campos Incompletos",
                    "Por favor, complete todos los campos."
                )
                return
            
            if len(password) < 8:
                QMessageBox.warning(
                    self,
                    "Contraseña Débil",
                    "La contraseña debe tener al menos 8 caracteres."
                )
                return
            
            if password != password_confirm:
                QMessageBox.warning(
                    self,
                    "Contraseñas No Coinciden",
                    "Las contraseñas ingresadas no coinciden."
                )
                return
            
            # Initialize database
            init_database()
            
            # Create admin user
            session = get_session()
            
            admin_user = User(
                username=username,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                full_name=name,
                created_at=datetime.now(timezone.utc),
                is_active=True
            )
            
            session.add(admin_user)
            session.commit()
            
            QMessageBox.information(
                self,
                "Sistema Inicializado",
                "✓ Sistema inicializado exitosamente\n\n"
                "Puede iniciar sesión con sus credenciales."
            )
            
            
            # Close and signal success - app will restart
            self.accept()

            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al inicializar sistema:\n{str(e)}"
            )
        finally:
            close_session()
    
    def login(self):
        """Handle login with brute-force lockout protection."""
        try:
            username = self.username_input.text().strip()
            password = self.password_input.text()

            if not username or not password:
                QMessageBox.warning(
                    self,
                    "Campos Incompletos",
                    "Por favor, ingrese usuario y contraseña."
                )
                return

            session = get_session()
            user = session.query(User).filter_by(
                username=username,
                role=UserRole.ADMIN,
                is_active=True
            ).first()

            if not user:
                QMessageBox.warning(
                    self,
                    "Error de Autenticación",
                    "Usuario o contraseña incorrectos."
                )
                return

            # Check lockout
            now = datetime.now(timezone.utc)
            locked_until = user.locked_until
            if locked_until:
                # Make aware if naive (SQLite may return naive datetime)
                if locked_until.tzinfo is None:
                    locked_until = locked_until.replace(tzinfo=timezone.utc)
                if locked_until > now:
                    remaining = int((locked_until - now).total_seconds() / 60) + 1
                    QMessageBox.warning(
                        self,
                        "Cuenta Bloqueada",
                        f"Cuenta bloqueada temporalmente.\n\n"
                        f"Intente en {remaining} minuto(s)."
                    )
                    return

            if not verify_password(user.password_hash, password):
                # Increment failed counter
                user.failed_login_count = (user.failed_login_count or 0) + 1
                if user.failed_login_count >= 5:
                    from datetime import timedelta
                    user.locked_until = now + timedelta(minutes=15)
                    user.failed_login_count = 0
                    from core.models import AuditLog
                    audit = AuditLog(
                        user_id=user.id,
                        action="Cuenta bloqueada por intentos fallidos",
                        details=f"Admin: {username}",
                    )
                    session.add(audit)
                    session.commit()
                    QMessageBox.warning(
                        self,
                        "Cuenta Bloqueada",
                        "Demasiados intentos fallidos.\n\n"
                        "Cuenta bloqueada por 15 minutos."
                    )
                else:
                    session.commit()
                    QMessageBox.warning(
                        self,
                        "Error de Autenticación",
                        "Usuario o contraseña incorrectos."
                    )
                return

            # Successful login — reset counter
            user.failed_login_count = 0
            user.locked_until = None
            session.commit()

            # Detach from session so attributes remain accessible after close
            from sqlalchemy.orm import make_transient
            session.expunge(user)
            make_transient(user)

            self.authenticated_user = user
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al iniciar sesión:\n{str(e)}"
            )
        finally:
            close_session()
