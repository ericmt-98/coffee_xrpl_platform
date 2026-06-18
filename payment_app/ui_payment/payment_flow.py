"""
Payment Flow Widget
Handles weight measurement, calculation, and XRPL payment execution
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QPushButton, QMessageBox,
    QGroupBox, QComboBox, QTextEdit, QProgressDialog,
    QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.database import get_session, close_session
from core.models import Producer, User, Payment, Delivery, IsoMessage, PaymentStatus, MessageType, EscrowDetail
from core.xrpl_client import XRPLClient, convert_mxn_to_token, MOCK_EXCHANGE_RATES
from core.iso_generator import ISO20022Generator
from core.utils import format_currency, calculate_payment_total, log_audit
from datetime import datetime, timezone


class PaymentFlowWidget(QWidget):
    """Widget for processing payments to producers"""

    payment_completed = Signal(Payment)

    def __init__(self, operator: User, xrpl_seed: str = None,
                 xrpl_client=None, xaman_client=None):
        super().__init__()
        self.operator      = operator
        self.xrpl_seed     = xrpl_seed      # None when Xaman mode
        self.xaman_client  = xaman_client   # None when seed mode
        self.current_producer = None
        self.xrpl_client   = xrpl_client or XRPLClient()
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

        # Disable pay button when weight is zero or no producer is selected
        self.weight_input.valueChanged.connect(self._update_pay_button_state)

        layout.addStretch()
        self._load_daily_price()

    def create_measurement_section(self) -> QGroupBox:
        """Create measurement and calculation section"""
        group = QGroupBox("Medición y Cálculo")
        layout = QFormLayout()
        
        # Weight input
        self.weight_input = QDoubleSpinBox()
        self.weight_input.setRange(0.01, 10000.0)
        self.weight_input.setDecimals(2)
        self.weight_input.setSuffix(" kg")
        self.weight_input.setValue(0.01)
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
        self.currency_combo.currentTextChanged.connect(self._on_mode_changed)
        currency_layout.addRow("Token a Enviar:", self.currency_combo)

        # Token amount display
        self.token_amount_label = QLabel("0.00 XRP")
        self.token_amount_label.setStyleSheet("font-size: 14pt; font-weight: 600; color: #0078D4;")
        currency_layout.addRow("Cantidad en Token:", self.token_amount_label)

        self.rate_caption = QLabel("")
        self.rate_caption.setStyleSheet("font-size: 8pt; color: #605E5C;")
        currency_layout.addRow("", self.rate_caption)

        layout.addLayout(currency_layout)

        # Modo de pago: directo vs escrow
        self.mode_group = QButtonGroup(self)
        self.direct_radio = QRadioButton("Pago directo")
        self.escrow_radio = QRadioButton("Pago contra calidad (Escrow)")
        self.direct_radio.setChecked(True)
        self.mode_group.addButton(self.direct_radio)
        self.mode_group.addButton(self.escrow_radio)
        self.direct_radio.toggled.connect(self._on_mode_changed)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.direct_radio)
        mode_layout.addWidget(self.escrow_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Ventana de calidad (visible solo en modo escrow)
        escrow_options_layout = QFormLayout()
        self.quality_window_label = QLabel("Ventana de calidad:")
        self.quality_window_combo = QComboBox()
        self.quality_window_combo.addItems(["24 horas", "48 horas", "72 horas", "7 días"])
        self.quality_window_combo.setCurrentIndex(1)  # default 48h
        self.quality_window_combo.setVisible(False)
        self.quality_window_label.setVisible(False)
        escrow_options_layout.addRow(self.quality_window_label, self.quality_window_combo)
        layout.addLayout(escrow_options_layout)
        
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
    
    def _update_pay_button_state(self):
        """Disable pay button when weight is zero or negative."""
        self.pay_button.setEnabled(
            self.weight_input.value() > 0 and self.current_producer is not None
        )

    def _on_mode_changed(self):
        """Show/hide escrow options and enforce XRP-only restriction for escrow mode."""
        is_xrp = self.currency_combo.currentText().split()[0] == "XRP"

        # Escrow solo disponible para XRP
        self.escrow_radio.setEnabled(is_xrp)
        if not is_xrp:
            self.direct_radio.setChecked(True)
            self.escrow_radio.setToolTip("Escrow disponible solo para XRP")
        else:
            self.escrow_radio.setToolTip("")

        is_escrow = self.escrow_radio.isChecked()
        self.quality_window_combo.setVisible(is_escrow)
        self.quality_window_label.setVisible(is_escrow)

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
        self.weight_input.setValue(0.01)
        self.calculate_total()
        self._update_pay_button_state()
        self._load_daily_price()

    def _load_daily_price(self):
        """Load today's reference price from DB if available."""
        try:
            from core.database import get_session, close_session
            from core.models import DailyPrice
            from datetime import date
            session = get_session()
            today = datetime.now().date()
            today_dt = datetime.combine(today, datetime.min.time())
            daily = session.query(DailyPrice).filter_by(price_date=today_dt).first()
            if daily:
                self.price_input.setValue(float(daily.price_per_kg))
                # Visual indicator
                self.price_input.setToolTip(f"Precio oficial del día: ${float(daily.price_per_kg):.2f}/kg")
            else:
                self.price_input.setToolTip("Sin precio oficial configurado — usando valor por defecto")
        except Exception:
            pass
        finally:
            close_session()

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
            rate = MOCK_EXCHANGE_RATES.get(f"{currency}_MXN")
            if rate:
                self.rate_caption.setText(f"Tasa fija educativa: 1 {currency} = ${rate:.2f} MXN")
            else:
                self.rate_caption.setText("")
        except (ValueError, KeyError) as e:
            self.token_amount_label.setText(f"Error: {e}")
            self.rate_caption.setText("")
    
    def execute_payment(self):
        """Execute XRPL payment — validate + confirm in UI thread, send in background."""
        if not self.current_producer:
            QMessageBox.warning(self, "Error", "No hay productor seleccionado.")
            return

        weight = self.weight_input.value()
        if weight <= 0:
            QMessageBox.warning(self, "Error", "El peso debe ser mayor a 0.")
            return

        total_mxn = weight * self.price_input.value()
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
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        uetr = self.iso_generator.generate_uetr()
        end_to_end_id = self.iso_generator.generate_end_to_end_id()

        # Escrow branch — synchronous, has its own progress dialog
        if self.escrow_radio.isChecked():
            progress = QProgressDialog("Procesando escrow...", None, 0, 4, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.setWindowTitle("Creando Escrow")
            try:
                self._execute_escrow_payment(weight, total_mxn, token_amount, uetr, end_to_end_id, progress)
            finally:
                progress.close()
            return

        # Xaman direct payment — sign in dialog, then persist in background
        if self.xaman_client and currency == "XRP":
            self._execute_xaman_payment(
                uetr, end_to_end_id, currency, token_amount, total_mxn, weight
            )
            return

        # Legacy seed direct payment — background thread, non-blocking
        self._progress = QProgressDialog("⏳ Conectando con XRPL Testnet...", None, 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setWindowTitle("Ejecutando Pago")
        self._progress.show()

        self.pay_button.setEnabled(False)
        self.pay_button.setText("⏳ Procesando…")

        from shared_ui.workers import FunctionWorker
        self._payment_worker = FunctionWorker(
            self._do_payment,
            uetr, end_to_end_id, currency, token_amount, total_mxn,
            self.current_producer.id, self.current_producer.name,
            self.current_producer.xrpl_address,
            self.operator.id, self.operator.full_name, self.operator.xrpl_address,
            weight, self.price_input.value(),
            self.notes_input.toPlainText(),
            self.xrpl_seed,
        )
        self._payment_worker.finished_ok.connect(self._on_payment_ok)
        self._payment_worker.failed.connect(self._on_payment_failed)
        self._payment_worker.start()

    def _execute_xaman_payment(self, uetr, end_to_end_id, currency,
                               token_amount, total_mxn, weight_kg):
        """Sign an XRP payment via Xaman, then persist in background."""
        from xrpl.utils import xrp_to_drops
        from decimal import Decimal
        from payment_app.ui_payment.xaman_sign_dialog import XamanSignDialog

        # Verify balance before signing
        try:
            balance_info = self.xrpl_client.get_balance(self.operator.xrpl_address)
            available    = balance_info.get("xrp", 0)
            required     = float(token_amount) + 1.0
            if available < required:
                QMessageBox.warning(
                    self, "Saldo Insuficiente",
                    f"Saldo disponible: {available:.6f} XRP\n"
                    f"Requerido: {required:.6f} XRP (monto + reserva base)"
                )
                return
        except Exception as e:
            QMessageBox.warning(self, "Error de saldo", str(e))
            return

        # Build unsigned txjson (Xaman will fill Sequence, Fee, etc.)
        drops   = str(xrp_to_drops(Decimal(str(token_amount))))
        memo_hex = f"Coffee Payment - UETR: {uetr}".encode().hex()
        txjson  = {
            "TransactionType": "Payment",
            "Account":         self.operator.xrpl_address,
            "Destination":     self.current_producer.xrpl_address,
            "Amount":          drops,
            "Memos": [{"Memo": {"MemoData": memo_hex}}],
        }

        instruction = (
            f"Pago a {self.current_producer.name}\n"
            f"{token_amount:.6f} XRP — {format_currency(total_mxn, 'MXN')}"
        )

        self.pay_button.setEnabled(False)
        self.pay_button.setText("⏳ Esperando firma…")

        dialog = XamanSignDialog(
            xaman_client=self.xaman_client,
            txjson=txjson,
            identifier=uetr,
            instruction=instruction,
            expected_account=self.operator.xrpl_address,
            kind="payment",
            parent=self,
        )

        signed = dialog.exec() and dialog.result_data["ok"]
        self.pay_button.setEnabled(True)
        self.pay_button.setText("💰 EJECUTAR PAGO")

        if not signed:
            reason = dialog.result_data.get("reason", "cancelled")
            msgs = {
                "cancelled":    "El operador canceló la firma en Xaman.",
                "expired":      "La solicitud de firma expiró.",
                "timeout":      "Tiempo de espera agotado.",
                "wrong_account": "Wallet incorrecta en Xaman.",
            }
            QMessageBox.warning(self, "Pago no completado",
                                msgs.get(reason, "No se firmó la transacción."))
            try:
                from core.audit import log_audit
                _s = get_session()
                log_audit(_s, self.operator.id, "Pago no firmado (Xaman)",
                          f"UETR: {uetr} | Razón: {reason}")
                _s.commit()
                close_session()
            except Exception:
                pass
            return

        tx_hash = dialog.result_data["txid"]

        # Persist in background (same as legacy path, minus the XRPL send)
        self._progress = QProgressDialog("⏳ Guardando pago...", None, 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setWindowTitle("Guardando")
        self._progress.show()

        from shared_ui.workers import FunctionWorker
        self._payment_worker = FunctionWorker(
            self._persist_payment,
            uetr, end_to_end_id, currency, token_amount, total_mxn,
            self.current_producer.id, self.current_producer.name,
            self.current_producer.xrpl_address,
            self.operator.id, self.operator.full_name, self.operator.xrpl_address,
            weight_kg, self.price_input.value(),
            self.notes_input.toPlainText(),
            tx_hash,
        )
        self._payment_worker.finished_ok.connect(self._on_payment_ok)
        self._payment_worker.failed.connect(self._on_payment_failed)
        self._payment_worker.start()

    def _persist_payment(self, uetr, end_to_end_id, currency, token_amount, total_mxn,
                         producer_id, producer_name, producer_address,
                         operator_id, operator_name, operator_address,
                         weight_kg, price_per_kg, notes, tx_hash) -> dict:
        """Background: persist an already-signed payment (Xaman path)."""
        from core.database import get_session as _gs, close_session as _cs
        from core.models import Payment as _Pay, Delivery as _Del, IsoMessage as _Iso
        from core.models import PaymentStatus as _PS, MessageType as _MT
        from core.iso_generator import ISO20022Generator
        from core.audit import log_audit as _log
        from datetime import datetime, timezone

        iso_gen = ISO20022Generator()
        session = _gs()
        try:
            payment = _Pay(
                uetr=uetr, xrpl_tx_hash=tx_hash,
                amount=token_amount, currency=currency, amount_mxn=total_mxn,
                producer_id=producer_id, operator_id=operator_id,
                timestamp=datetime.now(timezone.utc),
                status=_PS.COMPLETED,
                notes=notes or None,
            )
            session.add(payment)
            session.flush()

            session.add(_Del(
                payment_id=payment.id, weight_kg=weight_kg,
                price_per_kg=price_per_kg, total_mxn=total_mxn,
                delivery_date=datetime.now(timezone.utc), notes=notes or None,
            ))

            pd = {
                "uetr": uetr, "end_to_end_id": end_to_end_id,
                "amount": token_amount, "currency": currency,
                "debtor_name": operator_name, "debtor_account": operator_address,
                "creditor_name": producer_name, "creditor_account": producer_address,
                "xrpl_tx_hash": tx_hash,
            }
            session.add(_Iso(payment_id=payment.id, message_type=_MT.PACS_008,
                             xml_content=iso_gen.generate_pacs008(pd)))
            session.add(_Iso(payment_id=payment.id, message_type=_MT.PACS_002,
                             xml_content=iso_gen.generate_pacs002(pd, "tesSUCCESS")))
            session.add(_Iso(payment_id=payment.id, message_type=_MT.CAMT_054,
                             xml_content=iso_gen.generate_camt054(pd)))
            session.commit()

            _log(session, operator_id, "Pago ejecutado (Xaman)",
                 f"UETR: {uetr} | Productor: {producer_name} | "
                 f"Monto: {token_amount} {currency} | MXN: {total_mxn}")
            session.commit()

            return {
                "payment_id": payment.id, "uetr": uetr, "tx_hash": tx_hash,
                "token_amount": token_amount, "currency": currency,
                "total_mxn": total_mxn,
                "explorer_url": f"https://testnet.xrpl.org/transactions/{tx_hash}",
            }
        finally:
            _cs()

    def _do_payment(self, uetr, end_to_end_id, currency, token_amount, total_mxn,
                    producer_id, producer_name, producer_address,
                    operator_id, operator_name, operator_address,
                    weight_kg, price_per_kg, notes, seed) -> dict:
        """Background thread: XRPL network call + DB persistence. No Qt widgets accessed."""
        from core.database import get_session as _gs, close_session as _cs
        from core.models import Payment as _Pay, Delivery as _Del, IsoMessage as _Iso
        from core.models import PaymentStatus as _PS, MessageType as _MT
        from core.iso_generator import ISO20022Generator
        from core.audit import log_audit as _log

        iso_gen = ISO20022Generator()

        if currency == "XRP":
            balance_info = self.xrpl_client.get_balance(operator_address)
            available_xrp = balance_info.get('xrp', 0)
            required = float(token_amount) + 1.0
            if available_xrp < required:
                raise Exception(
                    f"Saldo insuficiente.\n"
                    f"Disponible: {available_xrp:.6f} XRP\n"
                    f"Requerido: {required:.6f} XRP (monto + reserva base)"
                )
            tx_result = self.xrpl_client.send_xrp_payment(
                sender_seed=seed,
                destination=producer_address,
                amount_xrp=token_amount,
                memo=f"Coffee Payment - UETR: {uetr}",
            )
            if not tx_result['validated']:
                raise Exception(f"Transaction failed: {tx_result['result']}")
            tx_hash = tx_result['hash']
        else:
            tx_hash = f"SIMULATED_{currency}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        session = _gs()
        try:
            payment = _Pay(
                uetr=uetr, xrpl_tx_hash=tx_hash,
                amount=token_amount, currency=currency, amount_mxn=total_mxn,
                producer_id=producer_id, operator_id=operator_id,
                timestamp=datetime.now(timezone.utc),
                status=_PS.COMPLETED if currency == "XRP" else _PS.SIMULATED,
                notes=notes or None,
            )
            session.add(payment)
            session.flush()

            session.add(_Del(
                payment_id=payment.id, weight_kg=weight_kg,
                price_per_kg=price_per_kg, total_mxn=total_mxn,
                delivery_date=datetime.now(timezone.utc), notes=notes or None,
            ))

            pd = {
                'uetr': uetr, 'end_to_end_id': end_to_end_id,
                'amount': token_amount, 'currency': currency,
                'debtor_name': operator_name, 'debtor_account': operator_address,
                'creditor_name': producer_name, 'creditor_account': producer_address,
                'xrpl_tx_hash': tx_hash,
            }
            session.add(_Iso(payment_id=payment.id, message_type=_MT.PACS_008,
                             xml_content=iso_gen.generate_pacs008(pd)))
            session.add(_Iso(payment_id=payment.id, message_type=_MT.CAMT_054,
                             xml_content=iso_gen.generate_camt054(pd)))
            session.commit()

            _log(session, operator_id, "Pago ejecutado",
                 f"UETR: {uetr} | Productor: {producer_name} | "
                 f"Monto: {token_amount} {currency} | MXN: {total_mxn}")
            session.commit()

            explorer_url = (self.xrpl_client.get_testnet_explorer_url(tx_hash)
                            if currency == "XRP" else None)
            return {
                'payment_id': payment.id, 'uetr': uetr, 'tx_hash': tx_hash,
                'token_amount': token_amount, 'currency': currency,
                'total_mxn': total_mxn, 'explorer_url': explorer_url,
            }
        finally:
            _cs()

    def _on_payment_ok(self, result: dict):
        """UI thread: payment finished successfully."""
        self.pay_button.setEnabled(True)
        self.pay_button.setText("💰 EJECUTAR PAGO")
        if hasattr(self, '_progress'):
            self._progress.close()

        from payment_app.ui_payment.payment_result_dialog import PaymentResultDialog
        PaymentResultDialog(result, parent=self).exec()

        try:
            from sqlalchemy.orm import make_transient
            session = get_session()
            payment = session.query(Payment).filter_by(id=result['payment_id']).first()
            if payment:
                session.expunge(payment)
                make_transient(payment)
                self.payment_completed.emit(payment)
        except Exception:
            pass
        finally:
            close_session()

        self.weight_input.setValue(0.01)
        self.notes_input.clear()
        self._update_pay_button_state()

    def _on_payment_failed(self, error: str):
        """UI thread: payment failed."""
        self.pay_button.setEnabled(True)
        self.pay_button.setText("💰 EJECUTAR PAGO")
        if hasattr(self, '_progress'):
            self._progress.close()

        QMessageBox.critical(
            self, "Error en Pago",
            f"Error al ejecutar pago:\n\n{error}\n\n"
            f"Por favor, verifique:\n"
            f"- Saldo suficiente en wallet\n"
            f"- Conexión a XRPL Testnet\n"
            f"- Dirección XRPL del productor"
        )
        try:
            from core.audit import log_audit as _log
            _s = get_session()
            _log(_s, self.operator.id, "Pago fallido", f"Error: {error[:200]}")
            _s.commit()
            close_session()
        except Exception:
            pass

    def _execute_escrow_payment(self, weight, total_mxn, token_amount, uetr, end_to_end_id, progress):
        """Execute a quality-conditional escrow payment."""
        from core.security import generate_escrow_condition
        from datetime import timedelta

        # Determinar ventana de calidad
        window_map = {"24 horas": 24, "48 horas": 48, "72 horas": 72, "7 días": 168}
        window_text = self.quality_window_combo.currentText()
        hours = window_map.get(window_text, 48)
        cancel_after = datetime.now(timezone.utc) + timedelta(hours=hours)

        # Generar condición criptográfica
        progress.setLabelText("Generando condición criptográfica...")
        progress.setValue(1)
        condition_hex, fulfillment_hex = generate_escrow_condition()

        # Crear escrow en XRPL
        progress.setLabelText("Creando escrow en XRPL Testnet...")
        progress.setValue(2)
        escrow_result = self.xrpl_client.create_escrow(
            sender_seed=self.xrpl_seed,
            destination=self.current_producer.xrpl_address,
            amount_xrp=token_amount,
            condition_hex=condition_hex,
            cancel_after_dt=cancel_after,
            memo=f"Coffee Escrow - UETR: {uetr}"
        )

        if not escrow_result["validated"]:
            raise Exception(f"EscrowCreate failed: {escrow_result['result']}")

        tx_hash = escrow_result["hash"]
        offer_sequence = escrow_result["offer_sequence"]

        # Guardar en DB
        progress.setLabelText("Guardando registro...")
        progress.setValue(3)

        session = get_session()

        payment = Payment(
            uetr=uetr,
            xrpl_tx_hash=tx_hash,
            amount=token_amount,
            currency="XRP",
            amount_mxn=total_mxn,
            producer_id=self.current_producer.id,
            operator_id=self.operator.id,
            timestamp=datetime.now(timezone.utc),
            status=PaymentStatus.ESCROWED,
            notes=self.notes_input.toPlainText() or None
        )
        session.add(payment)
        session.flush()

        delivery = Delivery(
            payment_id=payment.id,
            weight_kg=weight,
            price_per_kg=self.price_input.value(),
            total_mxn=total_mxn,
            delivery_date=datetime.now(timezone.utc),
            notes=self.notes_input.toPlainText() or None
        )
        session.add(delivery)

        escrow_detail = EscrowDetail(
            payment_id=payment.id,
            offer_sequence=offer_sequence,
            condition_hex=condition_hex,
            fulfillment_hex=fulfillment_hex,
            cancel_after=cancel_after,
            create_tx_hash=tx_hash,
        )
        session.add(escrow_detail)

        # Generar mensajes ISO
        progress.setLabelText("Generando mensajes ISO 20022...")
        progress.setValue(4)

        payment_data = {
            "uetr": uetr,
            "end_to_end_id": end_to_end_id,
            "amount": token_amount,
            "currency": "XRP",
            "debtor_name": self.operator.full_name,
            "debtor_account": self.operator.xrpl_address,
            "creditor_name": self.current_producer.name,
            "creditor_account": self.current_producer.xrpl_address,
            "xrpl_tx_hash": tx_hash,
        }

        pacs008_xml = self.iso_generator.generate_pacs008(payment_data)
        session.add(IsoMessage(payment_id=payment.id, message_type=MessageType.PACS_008, xml_content=pacs008_xml))

        pacs002_pdng_xml = self.iso_generator.generate_pacs002(payment_data, xrpl_result_code="temUNKNOWN")
        session.add(IsoMessage(payment_id=payment.id, message_type=MessageType.PACS_002, xml_content=pacs002_pdng_xml))

        log_audit(session, self.operator.id, "Pago en escrow creado",
                  f"UETR: {uetr} | Productor: {self.current_producer.name} | {token_amount:.6f} XRP | "
                  f"Vence: {cancel_after.strftime('%d/%m/%Y %H:%M')} UTC")

        session.commit()

        explorer_url = self.xrpl_client.get_testnet_explorer_url(tx_hash)

        QMessageBox.information(self, "Escrow Creado",
            f"✓ Fondos bloqueados en escrow\n\n"
            f"UETR: {uetr}\n"
            f"Hash XRPL: {tx_hash}\n"
            f"Monto: {token_amount:.6f} XRP\n"
            f"Equivalente: {format_currency(total_mxn, 'MXN')}\n\n"
            f"Ventana de calidad: {window_text}\n"
            f"Vence: {cancel_after.strftime('%d/%m/%Y %H:%M')} UTC\n\n"
            f"El productor puede verificar los fondos en:\n{explorer_url}\n\n"
            f"Diríjase a la pestaña 'Escrows' para aprobar o rechazar."
        )

        self.payment_completed.emit(payment)
        self.weight_input.setValue(0.0)
        self.notes_input.clear()
