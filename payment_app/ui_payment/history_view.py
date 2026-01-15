"""
History View Widget
Display payment history and export functionality
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QGroupBox,
    QFileDialog, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from core.database import get_session, close_session
from core.models import Payment, User
from core.utils import format_currency, format_datetime_display
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill


class HistoryViewWidget(QWidget):
    """Widget for viewing payment history"""
    
    def __init__(self, operator: User):
        super().__init__()
        self.operator = operator
        self.init_ui()
        self.load_history()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Historial de Pagos")
        title.setProperty("class", "subheader")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.load_history)
        header_layout.addWidget(refresh_btn)
        
        # Export button
        export_btn = QPushButton("📊 Exportar a Excel")
        export_btn.clicked.connect(self.export_to_excel)
        header_layout.addWidget(export_btn)
        
        layout.addLayout(header_layout)
        
        # Payment table
        self.payment_table = QTableWidget()
        self.payment_table.setColumnCount(7)
        self.payment_table.setHorizontalHeaderLabels([
            "Fecha/Hora", "Productor", "Peso (kg)",
            "Precio/kg", "Total MXN", "Token", "Estado"
        ])
        
        # Table settings
        self.payment_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.payment_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.payment_table.horizontalHeader().setStretchLastSection(True)
        self.payment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.payment_table.doubleClicked.connect(self.show_payment_details)
        
        layout.addWidget(self.payment_table)
        
        # Summary
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-size: 10pt; color: #605E5C; padding: 10px;")
        layout.addWidget(self.summary_label)
    
    def load_history(self):
        """Load payment history"""
        try:
            session = get_session()
            
            # Get payments for this operator
            payments = session.query(Payment).filter_by(
                operator_id=self.operator.id
            ).order_by(Payment.timestamp.desc()).all()
            
            self.payment_table.setRowCount(len(payments))
            
            total_mxn = 0.0
            total_kg = 0.0
            
            for row, payment in enumerate(payments):
                # Timestamp
                timestamp_str = format_datetime_display(payment.timestamp)
                self.payment_table.setItem(row, 0, QTableWidgetItem(timestamp_str))
                
                # Producer
                self.payment_table.setItem(row, 1, QTableWidgetItem(payment.producer.name))
                
                # Weight
                if payment.delivery:
                    weight_str = f"{payment.delivery.weight_kg:.2f}"
                    self.payment_table.setItem(row, 2, QTableWidgetItem(weight_str))
                    total_kg += payment.delivery.weight_kg
                    
                    # Price per kg
                    price_str = format_currency(payment.delivery.price_per_kg, "MXN")
                    self.payment_table.setItem(row, 3, QTableWidgetItem(price_str))
                else:
                    self.payment_table.setItem(row, 2, QTableWidgetItem("—"))
                    self.payment_table.setItem(row, 3, QTableWidgetItem("—"))
                
                # Total MXN
                if payment.amount_mxn:
                    total_str = format_currency(payment.amount_mxn, "MXN")
                    self.payment_table.setItem(row, 4, QTableWidgetItem(total_str))
                    total_mxn += payment.amount_mxn
                else:
                    self.payment_table.setItem(row, 4, QTableWidgetItem("—"))
                
                # Token
                token_str = f"{payment.amount:.6f} {payment.currency}"
                self.payment_table.setItem(row, 5, QTableWidgetItem(token_str))
                
                # Status
                status_str = payment.status.value.capitalize()
                status_item = QTableWidgetItem(status_str)
                
                if payment.status.value == "completed":
                    status_item.setForeground(QColor("#107C10"))
                elif payment.status.value == "failed":
                    status_item.setForeground(QColor("#D13438"))
                else:
                    status_item.setForeground(QColor("#FF8C00"))
                
                self.payment_table.setItem(row, 6, status_item)
            
            # Update summary
            self.summary_label.setText(
                f"Total de pagos: {len(payments)} | "
                f"Total kg: {total_kg:.2f} | "
                f"Total MXN: {format_currency(total_mxn, 'MXN')}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al cargar historial:\n{str(e)}"
            )
        finally:
            close_session()
    
    def show_payment_details(self, index):
        """Show detailed payment information"""
        try:
            row = index.row()
            session = get_session()
            
            payments = session.query(Payment).filter_by(
                operator_id=self.operator.id
            ).order_by(Payment.timestamp.desc()).all()
            
            if row < len(payments):
                payment = payments[row]
                
                details = (
                    f"Detalles del Pago\n"
                    f"{'=' * 50}\n\n"
                    f"UETR: {payment.uetr}\n"
                    f"Hash XRPL: {payment.xrpl_tx_hash}\n"
                    f"Fecha: {format_datetime_display(payment.timestamp)}\n\n"
                    f"Productor: {payment.producer.name}\n"
                    f"Dirección XRPL: {payment.producer.xrpl_address}\n\n"
                )
                
                if payment.delivery:
                    details += (
                        f"Peso: {payment.delivery.weight_kg:.2f} kg\n"
                        f"Precio/kg: {format_currency(payment.delivery.price_per_kg, 'MXN')}\n"
                        f"Total MXN: {format_currency(payment.delivery.total_mxn, 'MXN')}\n\n"
                    )
                
                details += (
                    f"Token: {payment.amount:.6f} {payment.currency}\n"
                    f"Estado: {payment.status.value.capitalize()}\n"
                )
                
                if payment.notes:
                    details += f"\nNotas: {payment.notes}\n"
                
                # Add ISO messages info
                if payment.iso_messages:
                    details += f"\nMensajes ISO 20022: {len(payment.iso_messages)}\n"
                    for msg in payment.iso_messages:
                        details += f"- {msg.message_type.value}\n"
                
                QMessageBox.information(self, "Detalles del Pago", details)
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al mostrar detalles:\n{str(e)}"
            )
        finally:
            close_session()
    
    def export_to_excel(self):
        """Export payment history to Excel"""
        try:
            # Get save location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Historial",
                f"historial_pagos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel Files (*.xlsx)"
            )
            
            if not file_path:
                return
            
            # Get data
            session = get_session()
            payments = session.query(Payment).filter_by(
                operator_id=self.operator.id
            ).order_by(Payment.timestamp.desc()).all()
            
            # Create workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Historial de Pagos"
            
            # Headers
            headers = [
                "Fecha/Hora", "UETR", "Hash XRPL", "Productor",
                "Peso (kg)", "Precio/kg", "Total MXN",
                "Token", "Cantidad Token", "Estado", "Notas"
            ]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="0078D4", end_color="0078D4", fill_type="solid")
            
            # Data
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
            
            # Save
            wb.save(file_path)
            
            QMessageBox.information(
                self,
                "Exportación Exitosa",
                f"Historial exportado exitosamente a:\n{file_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al exportar historial:\n{str(e)}"
            )
        finally:
            close_session()
