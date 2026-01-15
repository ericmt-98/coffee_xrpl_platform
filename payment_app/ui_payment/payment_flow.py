"""
Payment Flow Widget
Handles weight measurement, calculation, and XRPL payment execution
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QPushButton, QMessageBox,
    QGroupBox, QComboBox, QTextEdit, QProgressDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.database import get_session, close_session
from core.models import Producer, User, Payment, Delivery, IsoMessage, PaymentStatus, MessageType
from core.xrpl_client import XRPLClient, convert_mxn_to_token
from core.iso_generator import ISO20022Generator
from core.utils import format_currency, calculate_payment_total
from datetime import datetime


class PaymentFlowWidget(QWidget):
    """Widget for processing payments to producers"""
    
    payment_completed = Signal(Payment)
    
    def __init__(self, operator: User, xrpl_seed: str):
        super().__init__()
        self.operator = operator
        self.xrpl_seed = xrpl_seed
        self.current_producer = None
        self.xrpl_client = XRPLClient()
        self.iso_generator = ISO20022Generator()
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Producer info section
        self.producer_info_group = QGroupBox("Productor Seleccionado")
        self.producer_info_layout = QVBoxLayout()
        
        no_producer_label = QLabel("No hay productor seleccionado")
        no_producer_label.setAlignment(Qt.AlignCenter)
        no_producer_label.setStyleSheet("color: #A19F9D; font-size: 11pt; padding: 20px;")
        self.producer_info_layout.addWidget(no_producer_label)
        
        self.producer_info_group.setLayout(self.producer_info_layout)
        layout.addWidget(self.producer_info_group)
        
        # Measurement section
        self.measurement_group = self.create_measurement_section()
        self.measurement_group.setEnabled(False)
        layout.addWidget(self.measurement_group)
        
        # Payment section
        self.payment_group = self.create_payment_section()
        self.payment_group.setEnabled(False)
        layout.addWidget(self.payment_group)
        
        layout.addStretch()
    
    def create_measurement_section(self) -> QGroupBox:
        """Create measurement and calculation section"""
        group = QGroupBox("Medición y Cálculo")
        layout = QFormLayout()
        
        # Weight input
        self.weight_input = QDoubleSpinBox()
        self.weight_input.setRange(0.01, 10000.0)
        self.weight_input.setDecimals(2)
        self.weight_input.setSuffix(" kg")
        self.weight_input.setValue(0.0)
        self.weight_input.valueChanged.connect(self.calculate_total)
        layout.addRow("Peso (kg):*", self.weight_input)
        
        # Price per kg
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0.01, 10000.0)
        self.price_input.setDecimals(2)
        self.price_input.setPrefix("$ ")
        self.price_input.setSuffix(" MXN")
        self.price_input.setValue(50.0)  # Default price
        self.price_input.valueChanged.connect(self.calculate_total)
        layout.addRow("Precio por kg:*", self.price_input)
        
        # Total
        self.total_label = QLabel("$ 0.00 MXN")
        self.total_label.setProperty("class", "amount")
        layout.addRow("Total a Pagar:", self.total_label)
        
        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Notas adicionales (opcional)")
        self.notes_input.setMaximumHeight(60)
        layout.addRow("Notas:", self.notes_input)
        
        group.setLayout(layout)
        return group
    
    def create_payment_section(self) -> QGroupBox:
        """Create payment execution section"""
        group = QGroupBox("Ejecutar Pago XRPL")
        layout = QVBoxLayout()
        
        # Currency selection
        currency_layout = QFormLayout()
        
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["XRP", "USDC (Simulado)", "RLUSD (Simulado)", "MXN Token (Simulado)"])
        self.currency_combo.currentTextChanged.connect(self.update_token_amount)
        currency_layout.addRow("Token a Enviar:", self.currency_combo)
        
        # Token amount display
        self.token_amount_label = QLabel("0.00 XRP")
        self.token_amount_label.setStyleSheet("font-size: 14pt; font-weight: 600; color: #0078D4;")
        currency_layout.addRow("Cantidad en Token:", self.token_amount_label)
        
        layout.addLayout(currency_layout)
        
        # Warning
        warning = QLabel(
            "⚠️ Esta transacción se ejecutará en XRPL Testnet.\n"
            "Asegúrese de tener saldo suficiente en su wallet."
        )
        warning.setStyleSheet(
            "background-color: #FFF4CE; padding: 10px; border-radius: 4px; font-size: 9pt;"
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        # Pay button
        self.pay_button = QPushButton("💰 EJECUTAR PAGO")
        self.pay_button.setProperty("class", "large success")
        self.pay_button.setMinimumHeight(60)
        self.pay_button.clicked.connect(self.execute_payment)
        layout.addWidget(self.pay_button)
        
        group.setLayout(layout)
        return group
    
    def clear_layout(self, layout):
        """Recursively clear all widgets and sub-layouts from a layout"""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                self.clear_layout(item.layout())

    def set_producer(self, producer: Producer):
        """Set the current producer for payment"""
        self.current_producer = producer
        
        # Update producer info robustly
        self.clear_layout(self.producer_info_layout)
        
        info_layout = QFormLayout()
        
        name_label = QLabel(producer.name)
        name_label.setStyleSheet("font-size: 14pt; font-weight: 600;")
        info_layout.addRow("Nombre:", name_label)
        
        address_label = QLabel(producer.xrpl_address)
        address_label.setStyleSheet("font-family: 'Courier New'; font-size: 9pt;")
        info_layout.addRow("Dirección XRPL:", address_label)
        
        self.producer_info_layout.addLayout(info_layout)
        
        # Enable payment sections
        self.measurement_group.setEnabled(True)
        self.payment_group.setEnabled(True)
        
        # Reset inputs
        self.weight_input.setValue(0.0)
        self.calculate_total()
    
    def calculate_total(self):
        """Calculate total payment amount"""
        weight = self.weight_input.value()
        price = self.price_input.value()
        total = calculate_payment_total(weight, price)
        
        self.total_label.setText(format_currency(total, "MXN"))
        self.update_token_amount()
    
    def update_token_amount(self):
        """Update token amount based on selected currency"""
        total_mxn = self.weight_input.value() * self.price_input.value()
        
        currency_text = self.currency_combo.currentText()
        currency = currency_text.split()[0]  # Get first word (XRP, USDC, etc.)
        
        try:
            token_amount = convert_mxn_to_token(total_mxn, currency)
            self.token_amount_label.setText(f"{token_amount:.6f} {currency}")
        except:
            self.token_amount_label.setText("Error en conversión")
    
    def execute_payment(self):
        """Execute XRPL payment and generate ISO messages"""
        if not self.current_producer:
            QMessageBox.warning(self, "Error", "No hay productor seleccionado.")
            return
        
        weight = self.weight_input.value()
        if weight <= 0:
            QMessageBox.warning(self, "Error", "El peso debe ser mayor a 0.")
            return
        
        # Confirm payment
        total_mxn = self.weight_input.value() * self.price_input.value()
        currency_text = self.currency_combo.currentText()
        currency = currency_text.split()[0]
        token_amount = convert_mxn_to_token(total_mxn, currency)
        
        reply = QMessageBox.question(
            self,
            "Confirmar Pago",
            f"¿Confirma el pago de:\n\n"
            f"Productor: {self.current_producer.name}\n"
            f"Peso: {weight} kg\n"
            f"Total MXN: {format_currency(total_mxn, 'MXN')}\n"
            f"Token: {token_amount:.6f} {currency}\n\n"
            f"Esta transacción se ejecutará en XRPL Testnet.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Show progress dialog
        progress = QProgressDialog("Procesando pago...", None, 0, 4, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.setWindowTitle("Ejecutando Pago")
        
        try:
            # Step 1: Generate UETR
            progress.setLabelText("Generando identificadores...")
            progress.setValue(1)
            
            uetr = self.iso_generator.generate_uetr()
            end_to_end_id = self.iso_generator.generate_end_to_end_id()
            
            # Step 2: Execute XRPL payment
            progress.setLabelText("Enviando transacción XRPL...")
            progress.setValue(2)
            
            # Only XRP is actually sent; others are simulated
            if currency == "XRP":
                tx_result = self.xrpl_client.send_xrp_payment(
                    sender_seed=self.xrpl_seed,
                    destination=self.current_producer.xrpl_address,
                    amount_xrp=token_amount,
                    memo=f"Coffee Payment - UETR: {uetr}"
                )
                
                if not tx_result['validated']:
                    raise Exception(f"Transaction failed: {tx_result['result']}")
                
                tx_hash = tx_result['hash']
            else:
                # Simulated payment for other tokens
                tx_hash = f"SIMULATED_{currency}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Step 3: Save to database
            progress.setLabelText("Guardando registro...")
            progress.setValue(3)
            
            session = get_session()
            
            # Create payment record
            payment = Payment(
                uetr=uetr,
                xrpl_tx_hash=tx_hash,
                amount=token_amount,
                currency=currency,
                amount_mxn=total_mxn,
                producer_id=self.current_producer.id,
                operator_id=self.operator.id,
                timestamp=datetime.utcnow(),
                status=PaymentStatus.COMPLETED if currency == "XRP" else PaymentStatus.PENDING,
                notes=self.notes_input.toPlainText() or None
            )
            session.add(payment)
            session.flush()  # Get payment ID
            
            # Create delivery record
            delivery = Delivery(
                payment_id=payment.id,
                weight_kg=weight,
                price_per_kg=self.price_input.value(),
                total_mxn=total_mxn,
                delivery_date=datetime.utcnow(),
                notes=self.notes_input.toPlainText() or None
            )
            session.add(delivery)
            
            # Step 4: Generate ISO 20022 messages
            progress.setLabelText("Generando mensajes ISO 20022...")
            progress.setValue(4)
            
            payment_data = {
                'uetr': uetr,
                'end_to_end_id': end_to_end_id,
                'amount': token_amount,
                'currency': currency,
                'debtor_name': self.operator.full_name,
                'debtor_account': self.operator.xrpl_address,
                'creditor_name': self.current_producer.name,
                'creditor_account': self.current_producer.xrpl_address,
                'xrpl_tx_hash': tx_hash
            }
            
            # Generate pacs.008
            pacs008_xml = self.iso_generator.generate_pacs008(payment_data)
            pacs008_msg = IsoMessage(
                payment_id=payment.id,
                message_type=MessageType.PACS_008,
                xml_content=pacs008_xml,
                created_at=datetime.utcnow()
            )
            session.add(pacs008_msg)
            
            # Generate camt.054
            camt054_xml = self.iso_generator.generate_camt054(payment_data)
            camt054_msg = IsoMessage(
                payment_id=payment.id,
                message_type=MessageType.CAMT_054,
                xml_content=camt054_xml,
                created_at=datetime.utcnow()
            )
            session.add(camt054_msg)
            
            session.commit()
            
            # Success message
            explorer_url = self.xrpl_client.get_testnet_explorer_url(tx_hash) if currency == "XRP" else None
            
            success_msg = (
                f"✓ Pago ejecutado exitosamente\n\n"
                f"UETR: {uetr}\n"
                f"Hash XRPL: {tx_hash}\n"
                f"Monto: {token_amount:.6f} {currency}\n"
                f"Equivalente: {format_currency(total_mxn, 'MXN')}\n\n"
                f"Mensajes ISO 20022 generados:\n"
                f"- pacs.008 (Credit Transfer)\n"
                f"- camt.054 (Notification)"
            )
            
            if explorer_url:
                success_msg += f"\n\nVer en Explorer:\n{explorer_url}"
            
            QMessageBox.information(self, "Pago Exitoso", success_msg)
            
            # Emit signal
            self.payment_completed.emit(payment)
            
            # Reset form
            self.weight_input.setValue(0.0)
            self.notes_input.clear()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error en Pago",
                f"Error al ejecutar pago:\n\n{str(e)}\n\n"
                f"Por favor, verifique:\n"
                f"- Saldo suficiente en wallet\n"
                f"- Conexión a XRPL Testnet\n"
                f"- Dirección XRPL del productor"
            )
        finally:
            progress.close()
            close_session()
