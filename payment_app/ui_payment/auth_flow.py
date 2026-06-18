"""
Authentication Flow for Payment Application
Three-step process: ID -> Password -> Wallet
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
    QWidget, QStackedWidget, QGroupBox
)
from PySide6.QtCore import Qt

from payment_app.ui_payment.styles import PAYMENT_STYLESHEET
from core.database import get_session, close_session
from core.models import User, UserRole
from core.security import hash_password, verify_password, validate_xrpl_seed
from core.xrpl_client import XRPLClient
from shared_ui.components import StepIndicator


class AuthFlowDialog(QDialog):
    """Three-step authentication dialog for payment app"""

    def __init__(self):
        super().__init__()
        self.authenticated_user = None
        self.xrpl_seed   = None   # Stored in RAM only (legacy path)
        self.xaman_client = None  # Set when Xaman path succeeds

        # State stored after ID verification to avoid detached session issues
        self.user_db_id = None
        self.user_xrpl_address = None
        self.user_password_hash = None
        self.username = None

        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Coffee XRPL Platform - Pagos")
        self.setFixedSize(600, 620)
        self.setStyleSheet(PAYMENT_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        # Top bar: title + settings gear
        top_bar = QHBoxLayout()

        title_col = QVBoxLayout()
        title = QLabel("☕ Coffee XRPL Platform")
        title.setProperty("class", "header")
        title.setAlignment(Qt.AlignCenter)
        title_col.addWidget(title)
        subtitle = QLabel("Sistema de Pagos a Productores")
        subtitle.setProperty("class", "subheader")
        subtitle.setAlignment(Qt.AlignCenter)
        title_col.addWidget(subtitle)
        top_bar.addLayout(title_col, 1)

        settings_btn = QPushButton("⚙️")
        settings_btn.setToolTip("Ajustes de conexión Xaman")
        settings_btn.setProperty("class", "secondary")
        settings_btn.setFixedSize(36, 36)
        settings_btn.clicked.connect(self._open_settings)
        top_bar.addWidget(settings_btn, 0, Qt.AlignTop)

        layout.addLayout(top_bar)
        layout.addSpacing(10)

        # Step progress indicator
        self.step_indicator = StepIndicator(["ID", "Contraseña", "Wallet"])
        layout.addWidget(self.step_indicator)

        layout.addSpacing(10)

        # Stacked widget for different steps
        self.stack = QStackedWidget()
        self.stack.currentChanged.connect(self.step_indicator.set_current)
        layout.addWidget(self.stack)
        
        # Step 1: ID verification
        self.step1_widget = self.create_step1()
        self.stack.addWidget(self.step1_widget)
        
        # Step 2: Password (create or verify)
        self.step2_widget = self.create_step2()
        self.stack.addWidget(self.step2_widget)
        
        # Step 3: Wallet seed
        self.step3_widget = self.create_step3()
        self.stack.addWidget(self.step3_widget)
        
        layout.addStretch()
    
    def create_step1(self) -> QWidget:
        """Create Step 1: ID verification"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("Paso 1 de 3: Verificación de ID")
        info.setProperty("class", "subheader")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        
        form_group = QGroupBox("Ingrese su ID de Usuario")
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(15)
        
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Ej: JPrN7Xd")
        self.id_input.returnPressed.connect(self.verify_id)
        form_layout.addRow("ID de Usuario:", self.id_input)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        next_btn = QPushButton("Siguiente →")
        next_btn.setProperty("class", "large")
        next_btn.clicked.connect(self.verify_id)
        btn_layout.addWidget(next_btn)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def create_step2(self) -> QWidget:
        """Create Step 2: Password creation/verification"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.step2_info = QLabel("Paso 2 de 3: Contraseña")
        self.step2_info.setProperty("class", "subheader")
        self.step2_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.step2_info)
        
        # Form for password
        self.password_form_group = QGroupBox()
        self.password_form_layout = QFormLayout()
        
        self.password_form_group.setLayout(self.password_form_layout)
        layout.addWidget(self.password_form_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        back_btn = QPushButton("← Atrás")
        back_btn.setProperty("class", "secondary")
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        btn_layout.addWidget(back_btn)
        
        btn_layout.addStretch()
        
        self.step2_next_btn = QPushButton("Siguiente →")
        self.step2_next_btn.setProperty("class", "large")
        self.step2_next_btn.clicked.connect(self.verify_password)
        btn_layout.addWidget(self.step2_next_btn)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def create_step3(self) -> QWidget:
        """Create Step 3: Wallet seed"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("Paso 3 de 3: Wallet XRPL")
        info.setProperty("class", "subheader")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        
        form_group = QGroupBox("Ingrese su Clave Privada XRPL")
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(15)
        
        warning = QLabel(
            "⚠️ Su clave privada solo se almacenará en memoria RAM\n"
            "y se eliminará al cerrar sesión."
        )
        warning.setStyleSheet(
            "background-color: #FFF4CE; padding: 10px; border-radius: 4px; font-size: 9pt;"
        )
        warning.setWordWrap(True)
        form_layout.addRow(warning)
        
        self.seed_input = QLineEdit()
        self.seed_input.setEchoMode(QLineEdit.Password)
        self.seed_input.setPlaceholderText("sXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        self.seed_input.returnPressed.connect(self.verify_wallet)
        form_layout.addRow("Seed (Clave Privada):", self.seed_input)
        
        # Show seed checkbox
        self.show_seed_checkbox = QPushButton("👁 Mostrar")
        self.show_seed_checkbox.setProperty("class", "secondary")
        self.show_seed_checkbox.setCheckable(True)
        self.show_seed_checkbox.toggled.connect(self.toggle_seed_visibility)
        form_layout.addRow("", self.show_seed_checkbox)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        back_btn = QPushButton("← Atrás")
        back_btn.setProperty("class", "secondary")
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        btn_layout.addWidget(back_btn)
        
        btn_layout.addStretch()
        
        login_btn = QPushButton("🔐 Iniciar Sesión")
        login_btn.setProperty("class", "large")
        login_btn.clicked.connect(self.verify_wallet)
        btn_layout.addWidget(login_btn)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def verify_id(self):
        """Verify user ID (Step 1)"""
        try:
            user_id = self.id_input.text().strip()
            
            if not user_id:
                QMessageBox.warning(
                    self,
                    "Campo Vacío",
                    "Por favor, ingrese su ID de usuario."
                )
                return
            
            # Check if user exists
            session = get_session()
            user = session.query(User).filter_by(
                username=user_id,
                role=UserRole.OPERATOR,
                is_active=True
            ).first()
            
            if not user:
                QMessageBox.warning(
                    self,
                    "Credenciales Incorrectas",
                    "ID de usuario o credenciales incorrectos.\n\n"
                    "Verifique sus datos o contacte al administrador."
                )
                return
            
            # User found, store essential data as primitives
            self.user_db_id = user.id
            self.user_xrpl_address = user.xrpl_address
            self.user_password_hash = user.password_hash
            self.username = user.username
            
            self.setup_step2()
            self.stack.setCurrentIndex(1)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al verificar ID:\n{str(e)}"
            )
        finally:
            close_session()
    
    def setup_step2(self):
        """Setup Step 2 based on whether user has password"""
        # Clear previous inputs
        while self.password_form_layout.count():
            item = self.password_form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Freshly create password inputs to avoid deleted reference issues
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.verify_password)
        
        self.password_confirm_input = QLineEdit()
        self.password_confirm_input.setEchoMode(QLineEdit.Password)
        self.password_confirm_input.returnPressed.connect(self.verify_password)
        
        if self.user_password_hash is None:
            # First login - create password
            self.password_form_group.setTitle("Crear Contraseña")
            self.step2_info.setText("Paso 2 de 3: Crear Contraseña")
            
            info = QLabel(
                "Es su primer inicio de sesión.\n"
                "Por favor, cree una contraseña segura."
            )
            info.setWordWrap(True)
            info.setAlignment(Qt.AlignCenter)
            info.setStyleSheet(
                "background-color: #E3F2FD; padding: 15px; border-radius: 4px; "
                "color: #0D47A1; font-weight: 500;"
            )
            info.setMinimumHeight(60)
            self.password_form_layout.addRow(info)
            
            # Add vertical spacing between info and fields
            self.password_form_layout.setVerticalSpacing(15)

            
            self.password_input.clear()
            self.password_input.setPlaceholderText("Mínimo 8 caracteres")
            self.password_form_layout.addRow("Nueva Contraseña:", self.password_input)
            
            self.password_confirm_input.clear()
            self.password_confirm_input.setPlaceholderText("Repita la contraseña")
            self.password_form_layout.addRow("Confirmar Contraseña:", self.password_confirm_input)
            
            self.step2_next_btn.setText("Crear y Continuar →")
        else:
            # Existing user - verify password
            self.password_form_group.setTitle("Verificar Contraseña")
            self.step2_info.setText("Paso 2 de 3: Contraseña")
            
            self.password_input.clear()
            self.password_input.setPlaceholderText("Ingrese su contraseña")
            self.password_form_layout.addRow("Contraseña:", self.password_input)
            
            self.step2_next_btn.setText("Siguiente →")
        
        self.password_input.setFocus()
    
    def verify_password(self):
        """Verify or create password (Step 2)"""
        try:
            if self.user_password_hash is None:
                # Create new password
                password = self.password_input.text()
                password_confirm = self.password_confirm_input.text()
                
                if not password or not password_confirm:
                    QMessageBox.warning(
                        self,
                        "Campos Incompletos",
                        "Por favor, complete ambos campos de contraseña."
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
                
                # Save password
                session = get_session()
                try:
                    user = session.query(User).filter_by(id=self.user_db_id).first()
                    if user:
                        user.password_hash = hash_password(password)
                        session.commit()
                        # Update local state
                        self.user_password_hash = user.password_hash
                finally:
                    close_session()
                
                # Proceed to step 3
                self._goto_step3()

            else:
                # Verify existing password
                password = self.password_input.text()

                if not password:
                    QMessageBox.warning(
                        self,
                        "Campo Vacío",
                        "Por favor, ingrese su contraseña."
                    )
                    return

                if not verify_password(self.user_password_hash, password):
                    QMessageBox.warning(
                        self,
                        "Contraseña Incorrecta",
                        "La contraseña ingresada es incorrecta."
                    )
                    return

                # Proceed to step 3
                self._goto_step3()
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al procesar contraseña:\n{str(e)}"
            )
    
    def verify_wallet(self):
        """Verify XRPL wallet seed (Step 3)"""
        try:
            seed = self.seed_input.text().strip()
            
            if not seed:
                QMessageBox.warning(
                    self,
                    "Campo Vacío",
                    "Por favor, ingrese su seed XRPL."
                )
                return
            
            # Validate seed format
            if not validate_xrpl_seed(seed):
                QMessageBox.warning(
                    self,
                    "Seed Inválido",
                    "El formato del seed XRPL no es válido."
                )
                return
            
            # Try to create wallet from seed
            try:
                xrpl_client = XRPLClient()
                wallet = xrpl_client.get_wallet_from_seed(seed)
                
                # Verify it matches the user's registered address
                if wallet.address != self.user_xrpl_address:
                    QMessageBox.warning(
                        self,
                        "Dirección No Coincide",
                        f"La dirección XRPL de este seed no coincide con la registrada.\n\n"
                        f"Esperada: {self.user_xrpl_address}\n"
                        f"Recibida: {wallet.address}"
                    )
                    return
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Seed Inválido",
                    f"No se pudo crear wallet desde el seed:\n{str(e)}"
                )
                return
            
            self.xrpl_seed    = seed   # Store in RAM only
            self.xaman_client = None   # legacy path — no Xaman client
            self._complete_login()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al verificar wallet:\n{str(e)}"
            )
    
    def toggle_seed_visibility(self, checked):
        """Toggle seed visibility"""
        if checked:
            self.seed_input.setEchoMode(QLineEdit.Normal)
            self.show_seed_checkbox.setText("🙈 Ocultar")
        else:
            self.seed_input.setEchoMode(QLineEdit.Password)
            self.show_seed_checkbox.setText("👁 Mostrar")

    # ── Xaman / Settings helpers ──────────────────────────────────────────────

    def _open_settings(self):
        from payment_app.ui_payment.settings_dialog import SettingsDialog
        SettingsDialog(self).exec()

    def _goto_step3(self):
        """Transition to step 3: Xaman Sign In or legacy seed input."""
        from core.config_store import is_xaman_enabled
        if is_xaman_enabled():
            self._xaman_signin()
        else:
            self.stack.setCurrentIndex(2)
            self.seed_input.setFocus()

    def _xaman_signin(self):
        """Authenticate operator via Xaman Sign In instead of seed input."""
        from core.xaman_client import XamanClient
        from core.config_store import get_config
        from payment_app.ui_payment.xaman_sign_dialog import XamanSignDialog

        client = XamanClient.from_config()
        if client is None:
            QMessageBox.warning(
                self,
                "Xaman no configurado",
                "No se encontraron ajustes de conexión.\n\n"
                "Use el botón ⚙️ para configurar la URL del backend y la Device Key."
            )
            return

        dialog = XamanSignDialog(
            xaman_client=client,
            txjson={"TransactionType": "SignIn"},
            identifier=f"signin-{self.username}",
            instruction=f"Conectar wallet de {self.username} a Coffee XRPL Platform",
            expected_account=self.user_xrpl_address or "",
            kind="signin",
            parent=self,
        )

        if dialog.exec() and dialog.result_data["ok"]:
            # Authentication successful via Xaman
            self.xaman_client = client
            self.xrpl_seed    = None  # no seed in Xaman mode
            self._complete_login()
        else:
            reason = dialog.result_data.get("reason", "cancelled")
            msgs = {
                "cancelled":    "El inicio de sesión fue cancelado en Xaman.",
                "expired":      "La solicitud expiró. Intente nuevamente.",
                "timeout":      "Tiempo de espera agotado. Intente nuevamente.",
                "wrong_account": "La wallet conectada no coincide con la registrada.",
                "backend_error": "Error de conexión con el backend.",
            }
            QMessageBox.warning(self, "No autenticado",
                                msgs.get(reason, "No se completó el inicio de sesión."))

    def _complete_login(self):
        """Shared finalisation after successful step 3 (seed or Xaman)."""
        session = get_session()
        try:
            self.authenticated_user = session.query(User).filter_by(
                id=self.user_db_id
            ).first()
            if self.authenticated_user:
                session.expunge(self.authenticated_user)
                from sqlalchemy.orm import make_transient
                make_transient(self.authenticated_user)
        finally:
            close_session()

        try:
            from core.audit import log_audit
            audit_session = get_session()
            try:
                method = "Xaman" if self.xaman_client else "Seed"
                log_audit(audit_session, self.user_db_id,
                          "Inicio de sesión en Pagos",
                          f"Usuario: {self.username} | Método: {method}")
                audit_session.commit()
            finally:
                close_session()
        except Exception:
            pass

        self.accept()

    def closeEvent(self, event):
        """Handle window close - clear sensitive data"""
        self.xrpl_seed    = None
        self.xaman_client = None
        event.accept()
