"""
Payment result dialog — shown after a successful direct payment.
Replaces the plain QMessageBox with copyable UETR/hash, explorer link, and PDF receipt.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QApplication, QFileDialog
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from shared_ui.components import Toast


class PaymentResultDialog(QDialog):
    """Success dialog shown after a payment completes."""

    def __init__(self, result: dict, parent=None):
        """
        result keys: uetr, tx_hash, token_amount, currency,
                     total_mxn, explorer_url (optional),
                     producer_name, operator_name,
                     weight_kg, price_per_kg, timestamp (optional)
        """
        super().__init__(parent)
        self._result = result
        self.setWindowTitle("Pago Exitoso")
        self.setMinimumWidth(540)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(30, 30, 30, 30)

        # Success header
        header = QLabel("✓ Pago Exitoso")
        header.setStyleSheet("font-size: 18pt; font-weight: bold; color: #107C10;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Amount
        amount_lbl = QLabel(
            f"{self._result.get('token_amount', 0):.6f} {self._result.get('currency', '')}"
        )
        amount_lbl.setStyleSheet(
            "font-size: 22pt; font-weight: bold; color: #0078D4; padding: 6px;"
        )
        amount_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(amount_lbl)

        equiv_lbl = QLabel(f"≈ ${self._result.get('total_mxn', 0):.2f} MXN")
        equiv_lbl.setAlignment(Qt.AlignCenter)
        equiv_lbl.setStyleSheet("font-size: 11pt; color: #605E5C;")
        layout.addWidget(equiv_lbl)

        # Copyable identifiers
        form = QFormLayout()
        form.setVerticalSpacing(10)
        self._add_copyable_row(form, "UETR:", self._result.get('uetr', ''))
        self._add_copyable_row(form, "Hash XRPL:", self._result.get('tx_hash', ''))
        layout.addLayout(form)

        # ISO note
        iso_lbl = QLabel(
            "Mensajes ISO 20022 generados:\n"
            "  • pacs.008 (Credit Transfer)\n"
            "  • camt.054 (Debit Notification)"
        )
        iso_lbl.setStyleSheet(
            "font-size: 9pt; color: #605E5C; background: #F3F2F1; "
            "padding: 10px; border-radius: 4px;"
        )
        layout.addWidget(iso_lbl)

        # Action buttons
        btn_row = QHBoxLayout()

        if self._result.get('explorer_url'):
            exp_btn = QPushButton("🌐 Ver en Explorer")
            exp_btn.setProperty("class", "secondary")
            exp_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(self._result['explorer_url']))
            )
            btn_row.addWidget(exp_btn)

        pdf_btn = QPushButton("🧾 Guardar Recibo PDF")
        pdf_btn.setProperty("class", "secondary")
        pdf_btn.clicked.connect(self._save_pdf)
        btn_row.addWidget(pdf_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _add_copyable_row(self, form: QFormLayout, label: str, value: str):
        row = QHBoxLayout()
        edit = QLineEdit(value)
        edit.setReadOnly(True)
        edit.setStyleSheet("font-family: 'Courier New'; font-size: 8pt;")
        copy_btn = QPushButton("📋")
        copy_btn.setFixedWidth(36)
        copy_btn.setProperty("class", "secondary")
        copy_btn.setToolTip("Copiar al portapapeles")

        def _copy(v=value):
            QApplication.clipboard().setText(v)
            Toast.show_message(self, "✓ Copiado")

        copy_btn.clicked.connect(_copy)
        row.addWidget(edit)
        row.addWidget(copy_btn)
        form.addRow(label, row)

    def _save_pdf(self):
        uetr_short = self._result.get('uetr', 'recibo')[:8]
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Recibo PDF",
            f"recibo_{uetr_short}.pdf",
            "PDF Files (*.pdf)",
        )
        if not file_path:
            return
        try:
            from core.receipt import generate_receipt_pdf
            generate_receipt_pdf(self._result, file_path)
            Toast.show_message(self, "✓ Recibo guardado")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error al generar PDF", str(e))
