"""
Escrow Management Widget
Handles quality approval/rejection and fund release for XRPL conditional escrows.

XRPL Rule (critical for UI design):
  - EscrowFinish (release) is valid only BEFORE CancelAfter.
  - EscrowCancel (refund) is valid only AFTER CancelAfter.
  - There is no early cancellation in XRPL — rejecting quality marks the DB record
    as REJECTED immediately, but the on-ledger refund must wait for expiry.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QGroupBox, QHeaderView, QAbstractItemView,
    QDialog, QTextEdit, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from datetime import datetime, timezone

from core.database import get_session, close_session
from core.models import Payment, EscrowDetail, IsoMessage, MessageType, PaymentStatus, User
from core.xrpl_client import XRPLClient
from core.iso_generator import ISO20022Generator
from core.utils import format_currency, format_datetime_display, log_audit


class EscrowManagementWidget(QWidget):
    """Widget for managing quality-conditional XRPL escrow payments."""

    def __init__(self, operator: User, xrpl_seed: str = None):
        super().__init__()
        self.operator      = operator
        self.xrpl_seed     = xrpl_seed   # None when Xaman mode (signing not yet supported)
        self.xrpl_client   = XRPLClient()
        self.iso_generator = ISO20022Generator()
        self.init_ui()
        self.load_escrows()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        header = QLabel("Pagos en Escrow — Pendientes de Calidad")
        header.setProperty("class", "subheader")
        layout.addWidget(header)

        info = QLabel(
            "ℹ️  Los fondos están bloqueados on-chain. Apruebe la calidad para liberar "
            "el pago al productor, o rechace para iniciar el proceso de reembolso."
        )
        info.setWordWrap(True)
        info.setStyleSheet("background-color: #E3F2FD; padding: 10px; border-radius: 4px; font-size: 9pt;")
        layout.addWidget(info)

        # Tabla
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Fecha", "Productor", "Monto XRP", "Equiv. MXN",
            "Vence (UTC)", "Tiempo restante", "Estado"
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.selectionModel().selectionChanged.connect(self._update_buttons)
        layout.addWidget(self.table)

        # Botones de acción
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.load_escrows)
        btn_layout.addWidget(refresh_btn)

        btn_layout.addStretch()

        self.approve_btn = QPushButton("✓ Aprobar Calidad y Liberar")
        self.approve_btn.setEnabled(False)
        self.approve_btn.clicked.connect(self._approve_quality)
        btn_layout.addWidget(self.approve_btn)

        self.reject_btn = QPushButton("✗ Rechazar Calidad")
        self.reject_btn.setEnabled(False)
        self.reject_btn.setStyleSheet("QPushButton { color: #D13438; }")
        self.reject_btn.clicked.connect(self._reject_quality)
        btn_layout.addWidget(self.reject_btn)

        self.refund_btn = QPushButton("↩ Ejecutar Reembolso")
        self.refund_btn.setEnabled(False)
        self.refund_btn.clicked.connect(self._execute_refund)
        btn_layout.addWidget(self.refund_btn)

        # Xaman mode — signing not yet supported for escrow (Phase X5)
        if not self.xrpl_seed:
            xaman_note = QLabel(
                "ℹ️ La gestión de escrows con Xaman estará disponible en la próxima versión. "
                "Use modo seed para operaciones de escrow."
            )
            xaman_note.setWordWrap(True)
            xaman_note.setStyleSheet(
                "background:#FFF4CE; padding:8px; border-radius:4px; font-size:9pt;"
            )
            layout.addWidget(xaman_note)
            self.approve_btn.setEnabled(False)
            self.reject_btn.setEnabled(False)
            self.refund_btn.setEnabled(False)

        layout.addLayout(btn_layout)

    def load_escrows(self):
        """Load ESCROWED and REJECTED payments into the table."""
        try:
            session = get_session()
            payments = session.query(Payment).filter(
                Payment.operator_id == self.operator.id,
                Payment.status.in_([PaymentStatus.ESCROWED, PaymentStatus.REJECTED])
            ).order_by(Payment.timestamp.desc()).all()

            self.table.setRowCount(len(payments))
            now_utc = datetime.now(timezone.utc)

            for row, payment in enumerate(payments):
                escrow = payment.escrow_detail

                # Fecha
                self.table.setItem(row, 0, QTableWidgetItem(
                    format_datetime_display(payment.timestamp, include_time=False)
                ))

                # Productor
                self.table.setItem(row, 1, QTableWidgetItem(payment.producer.name))

                # Monto XRP
                self.table.setItem(row, 2, QTableWidgetItem(f"{payment.amount:.6f} XRP"))

                # Equiv MXN
                mxn_str = format_currency(payment.amount_mxn, "MXN") if payment.amount_mxn else "—"
                self.table.setItem(row, 3, QTableWidgetItem(mxn_str))

                # Vence
                if escrow:
                    cancel_str = escrow.cancel_after.strftime("%d/%m/%Y %H:%M")
                    self.table.setItem(row, 4, QTableWidgetItem(cancel_str))

                    # Tiempo restante
                    cancel_aware = (
                        escrow.cancel_after.replace(tzinfo=timezone.utc)
                        if escrow.cancel_after.tzinfo is None
                        else escrow.cancel_after
                    )
                    diff = cancel_aware - now_utc
                    if diff.total_seconds() > 0:
                        hours = int(diff.total_seconds() // 3600)
                        mins = int((diff.total_seconds() % 3600) // 60)
                        remaining = f"en {hours}h {mins}m"
                        remaining_item = QTableWidgetItem(remaining)
                        remaining_item.setForeground(QColor("#107C10"))
                    else:
                        remaining = "Vencido"
                        remaining_item = QTableWidgetItem(remaining)
                        remaining_item.setForeground(QColor("#D13438"))
                    self.table.setItem(row, 5, remaining_item)
                else:
                    self.table.setItem(row, 4, QTableWidgetItem("—"))
                    self.table.setItem(row, 5, QTableWidgetItem("—"))

                # Estado
                status_map = {
                    PaymentStatus.ESCROWED: ("En escrow", "#0078D4"),
                    PaymentStatus.REJECTED: ("Rechazado", "#FF8C00"),
                }
                label, color = status_map.get(payment.status, (payment.status.value, "#605E5C"))
                status_item = QTableWidgetItem(label)
                status_item.setForeground(QColor(color))
                self.table.setItem(row, 6, status_item)

                # Guardar payment.id en columna 0 para recuperarlo al seleccionar
                self.table.item(row, 0).setData(Qt.UserRole, payment.id)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar escrows:\n{str(e)}")
        finally:
            close_session()

    def _get_selected_payment(self):
        """Return (payment, escrow_detail) for selected row, or (None, None)."""
        rows = self.table.selectedItems()
        if not rows:
            return None, None
        row = rows[0].row()
        payment_id = self.table.item(row, 0).data(Qt.UserRole)
        try:
            session = get_session()
            payment = session.query(Payment).filter_by(id=payment_id).first()
            escrow = payment.escrow_detail if payment else None
            if payment:
                session.expunge(payment)
            if escrow:
                session.expunge(escrow)
            return payment, escrow
        except Exception:
            return None, None
        finally:
            close_session()

    def _update_buttons(self):
        """Enable/disable action buttons based on selected row state."""
        if not self.xrpl_seed:  # Xaman mode — escrow signing not yet supported
            return
        payment, escrow = self._get_selected_payment()
        if not payment or not escrow:
            self.approve_btn.setEnabled(False)
            self.reject_btn.setEnabled(False)
            self.refund_btn.setEnabled(False)
            return

        now_utc = datetime.now(timezone.utc)
        cancel_aware = (
            escrow.cancel_after.replace(tzinfo=timezone.utc)
            if escrow.cancel_after.tzinfo is None
            else escrow.cancel_after
        )
        is_expired = now_utc >= cancel_aware

        is_escrowed = payment.status == PaymentStatus.ESCROWED
        is_rejected = payment.status == PaymentStatus.REJECTED

        self.approve_btn.setEnabled(is_escrowed and not is_expired)
        self.reject_btn.setEnabled(is_escrowed and not is_expired)
        self.refund_btn.setEnabled(is_rejected and is_expired)

        if is_rejected and not is_expired:
            self.refund_btn.setToolTip(
                f"Reembolso disponible a partir de {cancel_aware.strftime('%d/%m/%Y %H:%M')} UTC"
            )
        else:
            self.refund_btn.setToolTip("")

    def _approve_quality(self):
        """Approve quality: execute EscrowFinish and generate pacs.002 ACSC."""
        payment, escrow = self._get_selected_payment()
        if not payment or not escrow:
            return

        # Diálogo de confirmación con notas
        dialog = QDialog(self)
        dialog.setWindowTitle("Aprobar Calidad")
        dialog.setFixedSize(450, 250)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setSpacing(12)
        dlg_layout.setContentsMargins(24, 24, 24, 24)

        dlg_layout.addWidget(QLabel(
            f"Aprobando calidad para:\n{payment.producer.name if hasattr(payment, 'producer') else 'productor'}"
        ))

        dlg_layout.addWidget(QLabel("Notas de calidad (opcional):"))
        notes_input = QTextEdit()
        notes_input.setMaximumHeight(80)
        notes_input.setPlaceholderText("Ej: Muestra aprobada, SCA 84.5, acidez media...")
        dlg_layout.addWidget(notes_input)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(dialog.reject)
        confirm_btn = QPushButton("✓ Confirmar y Liberar Fondos")
        confirm_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(confirm_btn)
        dlg_layout.addLayout(btn_row)

        if dialog.exec() != QDialog.Accepted:
            return

        quality_notes = notes_input.toPlainText().strip() or None

        try:
            # Ejecutar EscrowFinish
            finish_result = self.xrpl_client.finish_escrow(
                sender_seed=self.xrpl_seed,
                owner_address=self.operator.xrpl_address,
                offer_sequence=escrow.offer_sequence,
                condition_hex=escrow.condition_hex,
                fulfillment_hex=escrow.fulfillment_hex,
            )

            if not finish_result["validated"]:
                result_code = finish_result.get("result", "desconocido")
                QMessageBox.critical(self, "Error XRPL",
                    f"EscrowFinish falló: {result_code}\n\n"
                    f"Verifique que la ventana de calidad no haya vencido y reintente.")
                return

            finish_hash = finish_result["hash"]

            # Actualizar DB
            session = get_session()
            db_payment = session.query(Payment).filter_by(id=payment.id).first()
            db_escrow = session.query(EscrowDetail).filter_by(payment_id=payment.id).first()

            db_payment.status = PaymentStatus.COMPLETED
            db_escrow.finish_tx_hash = finish_hash
            db_escrow.quality_notes = quality_notes
            db_escrow.resolved_at = datetime.now(timezone.utc)

            # Generar pacs.002 ACSC con fulfillment
            payment_data = {
                "uetr": db_payment.uetr,
                "end_to_end_id": db_payment.uetr,
                "amount": float(db_payment.amount),
                "currency": "XRP",
                "debtor_name": self.operator.full_name,
                "creditor_name": db_payment.producer.name,
                "xrpl_tx_hash": finish_hash,
                "debtor_account": self.operator.xrpl_address,
                "creditor_account": db_payment.producer.xrpl_address,
            }
            pacs002_acsc = self.iso_generator.generate_pacs002(
                payment_data, xrpl_result_code="tesSUCCESS",
                escrow_fulfillment=escrow.fulfillment_hex
            )
            session.add(IsoMessage(
                payment_id=payment.id,
                message_type=MessageType.PACS_002,
                xml_content=pacs002_acsc,
            ))

            camt054_xml = self.iso_generator.generate_camt054(payment_data)
            session.add(IsoMessage(
                payment_id=payment.id,
                message_type=MessageType.CAMT_054,
                xml_content=camt054_xml,
            ))

            log_audit(session, self.operator.id, "Escrow liberado — calidad aprobada",
                      f"UETR: {db_payment.uetr} | Hash finish: {finish_hash}")
            session.commit()

            explorer_url = self.xrpl_client.get_testnet_explorer_url(finish_hash)
            QMessageBox.information(self, "Pago Liberado",
                f"✓ Fondos liberados al productor\n\n"
                f"Hash EscrowFinish: {finish_hash}\n\n"
                f"Mensajes ISO generados:\n- pacs.002 ACSC (con fulfillment)\n- camt.054 CRDT\n\n"
                f"Ver en explorador:\n{explorer_url}"
            )
            self.load_escrows()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al liberar escrow:\n{str(e)}")
        finally:
            close_session()

    def _reject_quality(self):
        """Reject quality: mark DB as REJECTED, generate pacs.002 RJCT.
        On-ledger EscrowCancel must wait until CancelAfter (XRPL rule).
        """
        payment, escrow = self._get_selected_payment()
        if not payment or not escrow:
            return

        # Diálogo con motivo obligatorio
        dialog = QDialog(self)
        dialog.setWindowTitle("Rechazar Calidad")
        dialog.setFixedSize(450, 260)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setSpacing(12)
        dlg_layout.setContentsMargins(24, 24, 24, 24)

        dlg_layout.addWidget(QLabel(
            f"Rechazando calidad para:\n"
            f"{payment.producer.name if hasattr(payment, 'producer') else 'productor'}"
        ))

        cancel_aware = (
            escrow.cancel_after.replace(tzinfo=timezone.utc)
            if escrow.cancel_after.tzinfo is None
            else escrow.cancel_after
        )
        info = QLabel(
            f"⚠️ El reembolso on-ledger estará disponible a partir de:\n"
            f"{cancel_aware.strftime('%d/%m/%Y %H:%M')} UTC\n"
            f"(regla de XRPL: EscrowCancel solo es válido después del vencimiento)"
        )
        info.setWordWrap(True)
        info.setStyleSheet("background-color: #FFF4CE; padding: 10px; border-radius: 4px; font-size: 9pt;")
        dlg_layout.addWidget(info)

        dlg_layout.addWidget(QLabel("Motivo de rechazo (obligatorio):"))
        reason_input = QLineEdit()
        reason_input.setPlaceholderText("Ej: Muestra no cumple SCA mínimo (80+), presencia de defectos...")
        dlg_layout.addWidget(reason_input)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(dialog.reject)
        confirm_btn = QPushButton("✗ Confirmar Rechazo")
        confirm_btn.setStyleSheet("QPushButton { color: #D13438; }")
        confirm_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(confirm_btn)
        dlg_layout.addLayout(btn_row)

        if dialog.exec() != QDialog.Accepted:
            return

        reason = reason_input.text().strip()
        if not reason:
            QMessageBox.warning(self, "Motivo requerido", "Debe ingresar el motivo del rechazo.")
            return

        try:
            session = get_session()
            db_payment = session.query(Payment).filter_by(id=payment.id).first()
            db_escrow = session.query(EscrowDetail).filter_by(payment_id=payment.id).first()

            db_payment.status = PaymentStatus.REJECTED
            db_escrow.quality_notes = reason

            payment_data = {
                "uetr": db_payment.uetr,
                "end_to_end_id": db_payment.uetr,
                "amount": float(db_payment.amount),
                "currency": "XRP",
                "debtor_name": self.operator.full_name,
                "creditor_name": db_payment.producer.name,
                "xrpl_tx_hash": db_payment.xrpl_tx_hash,
                "debtor_account": self.operator.xrpl_address,
                "creditor_account": db_payment.producer.xrpl_address,
                "rejection_reason": reason,
            }
            pacs002_rjct = self.iso_generator.generate_pacs002(
                payment_data, xrpl_result_code="tecQUALITY_REJECTED"
            )
            session.add(IsoMessage(
                payment_id=payment.id,
                message_type=MessageType.PACS_002,
                xml_content=pacs002_rjct,
            ))

            log_audit(session, self.operator.id, "Escrow rechazado — calidad no aprobada",
                      f"UETR: {db_payment.uetr} | Motivo: {reason}")
            session.commit()

            QMessageBox.information(self, "Calidad Rechazada",
                f"El pago ha sido marcado como rechazado.\n\n"
                f"Mensaje pacs.002 RJCT generado con el motivo.\n\n"
                f"El reembolso on-ledger estará disponible a partir de:\n"
                f"{cancel_aware.strftime('%d/%m/%Y %H:%M')} UTC"
            )
            self.load_escrows()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al rechazar:\n{str(e)}")
        finally:
            close_session()

    def _execute_refund(self):
        """Execute EscrowCancel after window expiry to return funds to operator."""
        payment, escrow = self._get_selected_payment()
        if not payment or not escrow:
            return

        reply = QMessageBox.question(self, "Confirmar Reembolso",
            f"¿Ejecutar EscrowCancel para devolver los fondos?\n\n"
            f"Productor: {payment.producer.name if hasattr(payment, 'producer') else '—'}\n"
            f"Monto: {payment.amount:.6f} XRP",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            cancel_result = self.xrpl_client.cancel_escrow(
                sender_seed=self.xrpl_seed,
                owner_address=self.operator.xrpl_address,
                offer_sequence=escrow.offer_sequence,
            )

            if not cancel_result["validated"]:
                result_code = cancel_result.get("result", "desconocido")
                QMessageBox.critical(self, "Error XRPL",
                    f"EscrowCancel falló: {result_code}\n\n"
                    f"Verifique que la ventana de calidad haya vencido. Si el error es tecNO_PERMISSION, "
                    f"la ventana aún no ha expirado.")
                return

            cancel_hash = cancel_result["hash"]

            session = get_session()
            db_payment = session.query(Payment).filter_by(id=payment.id).first()
            db_escrow = session.query(EscrowDetail).filter_by(payment_id=payment.id).first()

            db_payment.status = PaymentStatus.REFUNDED
            db_escrow.cancel_tx_hash = cancel_hash
            db_escrow.resolved_at = datetime.now(timezone.utc)

            payment_data = {
                "uetr": db_payment.uetr,
                "end_to_end_id": db_payment.uetr,
                "amount": float(db_payment.amount),
                "currency": "XRP",
                "debtor_name": self.operator.full_name,
                "creditor_name": db_payment.producer.name,
                "xrpl_tx_hash": cancel_hash,
                "debtor_account": self.operator.xrpl_address,
                "creditor_account": db_payment.producer.xrpl_address,
            }
            camt054_dbit = self.iso_generator.generate_camt054(payment_data)
            session.add(IsoMessage(
                payment_id=payment.id,
                message_type=MessageType.CAMT_054,
                xml_content=camt054_dbit,
            ))

            log_audit(session, self.operator.id, "Escrow cancelado — fondos reembolsados",
                      f"UETR: {db_payment.uetr} | Hash cancel: {cancel_hash}")
            session.commit()

            explorer_url = self.xrpl_client.get_testnet_explorer_url(cancel_hash)
            QMessageBox.information(self, "Reembolso Ejecutado",
                f"✓ Fondos devueltos a su wallet\n\n"
                f"Hash EscrowCancel: {cancel_hash}\n\n"
                f"Ver en explorador:\n{explorer_url}"
            )
            self.load_escrows()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al ejecutar reembolso:\n{str(e)}")
        finally:
            close_session()
