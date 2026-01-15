"""
Audit View Widget for Admin Application
Displays audit logs and provides export functionality
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QGroupBox,
    QFileDialog, QHeaderView, QAbstractItemView,
    QDateEdit, QComboBox
)
from PySide6.QtCore import Qt, QDate

from core.database import get_session, close_session
from core.models import AuditLog, User, Payment, IsoMessage
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill
import os


class AuditViewWidget(QWidget):
    """Widget for viewing audit logs and exporting data"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_audit_logs()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Header
        header = QLabel("Auditoría y Exportación de Datos")
        header.setProperty("class", "subheader")
        layout.addWidget(header)
        
        # Filters
        filter_group = self.create_filters()
        layout.addWidget(filter_group)
        
        # Audit log table
        log_group = self.create_audit_table()
        layout.addWidget(log_group)
        
        # Export section
        export_group = self.create_export_section()
        layout.addWidget(export_group)
    
    def create_filters(self) -> QGroupBox:
        """Create filter controls"""
        group = QGroupBox("Filtros")
        layout = QHBoxLayout()
        
        # Date from
        layout.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(self.date_from)
        
        # Date to
        layout.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(self.date_to)
        
        layout.addStretch()
        
        # Apply filter button
        apply_btn = QPushButton("Aplicar Filtros")
        apply_btn.clicked.connect(self.load_audit_logs)
        layout.addWidget(apply_btn)
        
        group.setLayout(layout)
        return group
    
    def create_audit_table(self) -> QGroupBox:
        """Create the audit log table"""
        group = QGroupBox("Registro de Auditoría")
        layout = QVBoxLayout()
        
        # Table
        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(5)
        self.audit_table.setHorizontalHeaderLabels([
            "Fecha/Hora", "Usuario", "Acción", "Detalles", "IP"
        ])
        
        # Table settings
        self.audit_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.audit_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.audit_table.horizontalHeader().setStretchLastSection(True)
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        layout.addWidget(self.audit_table)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.load_audit_logs)
        layout.addWidget(refresh_btn, alignment=Qt.AlignRight)
        
        group.setLayout(layout)
        return group
    
    def create_export_section(self) -> QGroupBox:
        """Create export controls"""
        group = QGroupBox("Exportar Datos")
        layout = QHBoxLayout()
        
        # Export buttons
        export_audit_btn = QPushButton("📊 Exportar Auditoría a Excel")
        export_audit_btn.clicked.connect(self.export_audit_to_excel)
        layout.addWidget(export_audit_btn)
        
        export_payments_btn = QPushButton("💰 Exportar Pagos a Excel")
        export_payments_btn.clicked.connect(self.export_payments_to_excel)
        layout.addWidget(export_payments_btn)
        
        export_iso_btn = QPushButton("📄 Exportar Mensajes ISO 20022")
        export_iso_btn.clicked.connect(self.export_iso_messages)
        layout.addWidget(export_iso_btn)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def load_audit_logs(self):
        """Load audit logs into the table"""
        try:
            session = get_session()
            
            # Get date range
            date_from = self.date_from.date().toPython()
            date_to = self.date_to.date().toPython()
            
            # Convert to datetime
            datetime_from = datetime.combine(date_from, datetime.min.time())
            datetime_to = datetime.combine(date_to, datetime.max.time())
            
            # Query logs
            logs = session.query(AuditLog).filter(
                AuditLog.timestamp >= datetime_from,
                AuditLog.timestamp <= datetime_to
            ).order_by(AuditLog.timestamp.desc()).all()
            
            self.audit_table.setRowCount(len(logs))
            
            for row, log in enumerate(logs):
                # Timestamp
                timestamp_str = log.timestamp.strftime("%d/%m/%Y %H:%M:%S")
                self.audit_table.setItem(row, 0, QTableWidgetItem(timestamp_str))
                
                # User
                user_name = log.user.full_name if log.user else "Sistema"
                self.audit_table.setItem(row, 1, QTableWidgetItem(user_name))
                
                # Action
                self.audit_table.setItem(row, 2, QTableWidgetItem(log.action))
                
                # Details
                details = log.details or "—"
                self.audit_table.setItem(row, 3, QTableWidgetItem(details))
                
                # IP
                ip = log.ip_address or "—"
                self.audit_table.setItem(row, 4, QTableWidgetItem(ip))
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al cargar registros de auditoría:\n{str(e)}"
            )
        finally:
            close_session()
    
    def export_audit_to_excel(self):
        """Export audit logs to Excel"""
        try:
            # Get save location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Auditoría",
                f"auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel Files (*.xlsx)"
            )
            
            if not file_path:
                return
            
            # Get data
            session = get_session()
            logs = session.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
            
            # Create workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Auditoría"
            
            # Headers
            headers = ["Fecha/Hora", "Usuario", "Acción", "Detalles", "IP"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="0078D4", end_color="0078D4", fill_type="solid")
            
            # Data
            for row, log in enumerate(logs, 2):
                ws.cell(row=row, column=1, value=log.timestamp.strftime("%d/%m/%Y %H:%M:%S"))
                ws.cell(row=row, column=2, value=log.user.full_name if log.user else "Sistema")
                ws.cell(row=row, column=3, value=log.action)
                ws.cell(row=row, column=4, value=log.details or "")
                ws.cell(row=row, column=5, value=log.ip_address or "")
            
            # Save
            wb.save(file_path)
            
            QMessageBox.information(
                self,
                "Exportación Exitosa",
                f"Auditoría exportada exitosamente a:\n{file_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al exportar auditoría:\n{str(e)}"
            )
        finally:
            close_session()
    
    def export_payments_to_excel(self):
        """Export payments to Excel"""
        try:
            # Get save location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Pagos",
                f"pagos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel Files (*.xlsx)"
            )
            
            if not file_path:
                return
            
            # Get data
            session = get_session()
            payments = session.query(Payment).order_by(Payment.timestamp.desc()).all()
            
            # Create workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Pagos"
            
            # Headers
            headers = [
                "UETR", "Hash XRPL", "Fecha/Hora", "Productor",
                "Operador", "Monto", "Moneda", "Monto MXN", "Estado"
            ]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="0078D4", end_color="0078D4", fill_type="solid")
            
            # Data
            for row, payment in enumerate(payments, 2):
                ws.cell(row=row, column=1, value=payment.uetr)
                ws.cell(row=row, column=2, value=payment.xrpl_tx_hash)
                ws.cell(row=row, column=3, value=payment.timestamp.strftime("%d/%m/%Y %H:%M:%S"))
                ws.cell(row=row, column=4, value=payment.producer.name)
                ws.cell(row=row, column=5, value=payment.operator.full_name)
                ws.cell(row=row, column=6, value=payment.amount)
                ws.cell(row=row, column=7, value=payment.currency)
                ws.cell(row=row, column=8, value=payment.amount_mxn or 0)
                ws.cell(row=row, column=9, value=payment.status.value)
            
            # Save
            wb.save(file_path)
            
            QMessageBox.information(
                self,
                "Exportación Exitosa",
                f"Pagos exportados exitosamente a:\n{file_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al exportar pagos:\n{str(e)}"
            )
        finally:
            close_session()
    
    def export_iso_messages(self):
        """Export ISO 20022 messages to XML files"""
        try:
            # Get save directory
            dir_path = QFileDialog.getExistingDirectory(
                self,
                "Seleccionar Carpeta para Mensajes ISO"
            )
            
            if not dir_path:
                return
            
            # Get data
            session = get_session()
            messages = session.query(IsoMessage).all()
            
            if not messages:
                QMessageBox.information(
                    self,
                    "Sin Datos",
                    "No hay mensajes ISO 20022 para exportar."
                )
                return
            
            # Export each message
            for msg in messages:
                filename = f"{msg.message_type.value}_{msg.payment.uetr}.xml"
                file_path = os.path.join(dir_path, filename)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(msg.xml_content)
            
            QMessageBox.information(
                self,
                "Exportación Exitosa",
                f"{len(messages)} mensajes ISO 20022 exportados exitosamente a:\n{dir_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al exportar mensajes ISO:\n{str(e)}"
            )
        finally:
            close_session()
