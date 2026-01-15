"""
User Management Widget for Admin Application
Handles creation and management of App 2 (Payment) users
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QGroupBox, QDateEdit,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor

from core.database import get_session, close_session
from core.models import User, UserRole, AuditLog
from core.utils import generate_user_id
from core.security import hash_password
from datetime import datetime


class UserManagementWidget(QWidget):
    """Widget for managing payment app users"""
    
    def __init__(self, admin_user: User):
        super().__init__()
        self.admin_user = admin_user
        self.init_ui()
        self.load_users()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Header
        header = QLabel("Gestión de Usuarios - Aplicación de Pagos")
        header.setProperty("class", "subheader")
        layout.addWidget(header)
        
        # Create user form
        form_group = self.create_user_form()
        layout.addWidget(form_group)
        
        # User table
        table_group = self.create_user_table()
        layout.addWidget(table_group)
    
    def create_user_form(self) -> QGroupBox:
        """Create the user creation form"""
        group = QGroupBox("Crear Nuevo Usuario")
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        # Full name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej: Juan Pérez García")
        self.name_input.textChanged.connect(self.validate_form)
        form_layout.addRow("Nombre Completo:*", self.name_input)
        
        # Date of birth
        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDate(QDate.currentDate().addYears(-25))
        self.dob_input.setDisplayFormat("dd/MM/yyyy")
        self.dob_input.dateChanged.connect(self.validate_form)
        form_layout.addRow("Fecha de Nacimiento:*", self.dob_input)
        
        # XRPL address
        self.xrpl_input = QLineEdit()
        self.xrpl_input.setPlaceholderText("Ej: rN7n7otQDd6FczFgLdlqtyMVrn3e5PcjXd")
        self.xrpl_input.textChanged.connect(self.validate_form)
        form_layout.addRow("Dirección XRPL:*", self.xrpl_input)
        
        # Generated ID display
        self.generated_id_label = QLabel("—")
        self.generated_id_label.setStyleSheet(
            "font-weight: 600; font-size: 12pt; color: #0078D4;"
        )
        form_layout.addRow("ID Generado:", self.generated_id_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.clear_btn = QPushButton("Limpiar")
        self.clear_btn.setProperty("class", "secondary")
        self.clear_btn.clicked.connect(self.clear_form)
        button_layout.addWidget(self.clear_btn)
        
        self.submit_btn = QPushButton("✓ Crear Usuario")
        self.submit_btn.setEnabled(False)
        self.submit_btn.clicked.connect(self.create_user)
        button_layout.addWidget(self.submit_btn)
        
        form_layout.addRow("", button_layout)
        
        # Required fields note
        note = QLabel("* Campos obligatorios")
        note.setProperty("class", "caption")
        form_layout.addRow("", note)
        
        group.setLayout(form_layout)
        return group
    
    def create_user_table(self) -> QGroupBox:
        """Create the user list table"""
        group = QGroupBox("Usuarios Registrados")
        layout = QVBoxLayout()
        
        # Table
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(6)
        self.user_table.setHorizontalHeaderLabels([
            "ID Usuario", "Nombre Completo", "Fecha Nacimiento",
            "Dirección XRPL", "Fecha Creación", "Estado"
        ])
        
        # Table settings
        self.user_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.user_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.user_table.horizontalHeader().setStretchLastSection(True)
        self.user_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        layout.addWidget(self.user_table)
        
        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.load_users)
        action_layout.addWidget(refresh_btn)
        
        reset_pwd_btn = QPushButton("🔑 Resetear Contraseña")
        reset_pwd_btn.setProperty("class", "secondary")
        reset_pwd_btn.clicked.connect(self.reset_password)
        action_layout.addWidget(reset_pwd_btn)
        
        layout.addLayout(action_layout)
        
        group.setLayout(layout)
        return group
    
    def validate_form(self):
        """Validate form and enable/disable submit button"""
        name = self.name_input.text().strip()
        xrpl = self.xrpl_input.text().strip()
        
        # Check if all required fields are filled
        is_valid = (
            len(name) > 0 and
            len(xrpl) > 0 and
            xrpl.startswith('r') and
            len(xrpl) >= 25
        )
        
        self.submit_btn.setEnabled(is_valid)
        
        # Update generated ID preview
        if is_valid:
            try:
                generated_id = generate_user_id(name, xrpl)
                self.generated_id_label.setText(generated_id)
            except:
                self.generated_id_label.setText("Error")
        else:
            self.generated_id_label.setText("—")
    
    def create_user(self):
        """Create a new user"""
        try:
            name = self.name_input.text().strip()
            dob = self.dob_input.date().toPython()
            xrpl = self.xrpl_input.text().strip()
            
            # Generate user ID
            user_id = generate_user_id(name, xrpl)
            
            # Check if user ID already exists
            session = get_session()
            existing = session.query(User).filter_by(username=user_id).first()
            
            if existing:
                QMessageBox.warning(
                    self,
                    "Usuario Duplicado",
                    f"Ya existe un usuario con el ID: {user_id}\n\n"
                    "Por favor, verifique los datos ingresados."
                )
                return
            
            # Create new user
            new_user = User(
                username=user_id,
                password_hash=None,  # Will be set on first login
                role=UserRole.OPERATOR,
                full_name=name,
                date_of_birth=datetime.combine(dob, datetime.min.time()),
                xrpl_address=xrpl,
                created_at=datetime.utcnow(),
                is_active=True
            )
            
            session.add(new_user)
            
            # Log action
            log_entry = AuditLog(
                user_id=self.admin_user.id,
                action="Creación de usuario",
                details=f"Usuario creado: {user_id} ({name})",
                timestamp=datetime.utcnow()
            )
            session.add(log_entry)
            
            session.commit()
            
            # Show success message
            QMessageBox.information(
                self,
                "Usuario Creado",
                f"✓ Usuario agregado con éxito\n\n"
                f"ID de Usuario: {user_id}\n"
                f"Nombre: {name}\n\n"
                f"El usuario deberá crear su contraseña en el primer inicio de sesión."
            )
            
            # Clear form and reload table
            self.clear_form()
            self.load_users()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al crear usuario:\n{str(e)}"
            )
        finally:
            close_session()
    
    def clear_form(self):
        """Clear the form"""
        self.name_input.clear()
        self.dob_input.setDate(QDate.currentDate().addYears(-25))
        self.xrpl_input.clear()
        self.generated_id_label.setText("—")
        self.submit_btn.setEnabled(False)
    
    def load_users(self):
        """Load users into the table"""
        try:
            session = get_session()
            users = session.query(User).filter_by(role=UserRole.OPERATOR).all()
            
            self.user_table.setRowCount(len(users))
            
            for row, user in enumerate(users):
                # ID
                self.user_table.setItem(row, 0, QTableWidgetItem(user.username))
                
                # Name
                self.user_table.setItem(row, 1, QTableWidgetItem(user.full_name))
                
                # DOB
                dob_str = user.date_of_birth.strftime("%d/%m/%Y") if user.date_of_birth else "—"
                self.user_table.setItem(row, 2, QTableWidgetItem(dob_str))
                
                # XRPL
                self.user_table.setItem(row, 3, QTableWidgetItem(user.xrpl_address or "—"))
                
                # Created
                created_str = user.created_at.strftime("%d/%m/%Y %H:%M")
                self.user_table.setItem(row, 4, QTableWidgetItem(created_str))
                
                # Status
                status = "Activo" if user.is_active else "Inactivo"
                status_item = QTableWidgetItem(status)
                if user.is_active:
                    status_item.setForeground(QColor("#107C10"))
                else:
                    status_item.setForeground(QColor("#A19F9D"))
                self.user_table.setItem(row, 5, status_item)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar usuarios:\n{str(e)}")
        finally:
            close_session()
    
    def reset_password(self):
        """Reset password for selected user"""
        selected_rows = self.user_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(
                self,
                "Selección Requerida",
                "Por favor, seleccione un usuario de la tabla."
            )
            return
        
        row = selected_rows[0].row()
        user_id = self.user_table.item(row, 0).text()
        user_name = self.user_table.item(row, 1).text()
        
        reply = QMessageBox.question(
            self,
            "Confirmar Reseteo",
            f"¿Está seguro que desea resetear la contraseña de:\n\n"
            f"{user_name} ({user_id})?\n\n"
            f"El usuario deberá crear una nueva contraseña en su próximo inicio de sesión.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                session = get_session()
                user = session.query(User).filter_by(username=user_id).first()
                
                if user:
                    user.password_hash = None
                    
                    # Log action
                    log_entry = AuditLog(
                        user_id=self.admin_user.id,
                        action="Reseteo de contraseña",
                        details=f"Contraseña reseteada para: {user_id}",
                        timestamp=datetime.utcnow()
                    )
                    session.add(log_entry)
                    
                    session.commit()
                    
                    QMessageBox.information(
                        self,
                        "Contraseña Reseteada",
                        f"La contraseña de {user_name} ha sido reseteada exitosamente."
                    )
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Error al resetear contraseña:\n{str(e)}"
                )
            finally:
                close_session()
