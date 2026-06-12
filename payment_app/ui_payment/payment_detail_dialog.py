"""
Payment detail dialog — shown when the user double-clicks or clicks "Ver Detalles"
in the history view. Replaces the plain QMessageBox with copyable fields and PDF.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QApplication,
    QFileDialog, QGroupBox, QPlainTextEdit, QComboBox
)
from PySide6.QtCore import Qt

from shared_ui.components import Toast


class PaymentDetailDialog(QDialog):
    """Detail dialog for a historical payment."""

    def __init__(self, data: dict, parent=None):
        """
        data keys:
            uetr, tx_hash, timestamp_str, status_label,
            producer_name, producer_address,
            weight_kg (optional), price_per_kg (optional), total_mxn (optional),
            token_amount, currency, notes (optional),
            iso_messages: list of {'type': str, 'xml': str}
            (for PDF: operator_name)
        """
        super().__init__(parent)
        self._data = data
        self.setWindowTitle("Detalles del Pago")
        self.setMinimumWidth(560)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        # Identifiers section
        id_group = QGroupBox("Identificadores")
        id_form = QFormLayout()
        id_form.setVerticalSpacing(8)
        self._add_copyable_row(id_form, "UETR:", self._data.get('uetr', ''))
        self._add_copyable_row(id_form, "Hash XRPL:", self._data.get('tx_hash', ''))
        id_form.addRow("Fecha:", QLabel(self._data.get('timestamp_str', '—')))
        id_form.addRow("Estado:", QLabel(self._data.get('status_label', '—')))
        id_group.setLayout(id_form)
        layout.addWidget(id_group)

        # Producer section
        prod_group = QGroupBox("Productor")
        prod_form = QFormLayout()
        prod_form.setVerticalSpacing(8)
        prod_form.addRow("Nombre:", QLabel(self._data.get('producer_name', '—')))
        addr = QLineEdit(self._data.get('producer_address', ''))
        addr.setReadOnly(True)
        addr.setStyleSheet("font-family: 'Courier New'; font-size: 8pt;")
        prod_form.addRow("Dirección XRPL:", addr)
        prod_group.setLayout(prod_form)
        layout.addWidget(prod_group)

        # Delivery section (optional)
        if self._data.get('weight_kg') is not None:
            del_group = QGroupBox("Entrega")
            del_form = QFormLayout()
            del_form.setVerticalSpacing(8)
            del_form.addRow("Peso:", QLabel(f"{float(self._data['weight_kg']):.2f} kg"))
            del_form.addRow("Precio/kg:", QLabel(f"${float(self._data.get('price_per_kg', 0)):.2f} MXN"))
            mxn_lbl = QLabel(f"${float(self._data.get('total_mxn', 0)):.2f} MXN")
            mxn_lbl.setStyleSheet("font-size: 13pt; font-weight: bold; color: #107C10;")
            del_form.addRow("Total MXN:", mxn_lbl)
            del_form.addRow("Token:", QLabel(
                f"{float(self._data.get('token_amount', 0)):.6f} {self._data.get('currency', '')}"
            ))
            del_group.setLayout(del_form)
            layout.addWidget(del_group)

        # ISO messages (optional)
        iso_msgs = self._data.get('iso_messages', [])
        if iso_msgs:
            iso_group = QGroupBox(f"Mensajes ISO 20022 ({len(iso_msgs)})")
            iso_layout = QVBoxLayout()
            combo = QComboBox()
            for msg in iso_msgs:
                combo.addItem(msg['type'])
            view_btn = QPushButton("👁 Ver XML")
            view_btn.setProperty("class", "secondary")
            view_btn.clicked.connect(lambda: self._show_xml(iso_msgs[combo.currentIndex()]))
            row = QHBoxLayout()
            row.addWidget(combo)
            row.addWidget(view_btn)
            iso_layout.addLayout(row)
            iso_group.setLayout(iso_layout)
            layout.addWidget(iso_group)

        # Buttons
        btn_row = QHBoxLayout()
        pdf_btn = QPushButton("🧾 Recibo PDF")
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

    def _show_xml(self, msg: dict):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Mensaje {msg['type']}")
        dlg.resize(640, 480)
        v = QVBoxLayout(dlg)
        text = QPlainTextEdit(msg.get('xml', ''))
        text.setReadOnly(True)
        text.setFont(text.font())
        v.addWidget(text)
        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 Guardar como…")
        save_btn.setProperty("class", "secondary")

        def _save():
            fp, _ = QFileDialog.getSaveFileName(
                dlg, "Guardar XML",
                f"{msg['type']}.xml",
                "XML Files (*.xml)",
            )
            if fp:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(msg.get('xml', ''))
                Toast.show_message(dlg, "✓ Guardado")

        save_btn.clicked.connect(_save)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        close_xml = QPushButton("Cerrar")
        close_xml.clicked.connect(dlg.accept)
        btn_row.addWidget(close_xml)
        v.addLayout(btn_row)
        dlg.exec()

    def _save_pdf(self):
        uetr_short = self._data.get('uetr', 'recibo')[:8]
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
            generate_receipt_pdf(self._data, file_path)
            Toast.show_message(self, "✓ Recibo guardado")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error al generar PDF", str(e))
