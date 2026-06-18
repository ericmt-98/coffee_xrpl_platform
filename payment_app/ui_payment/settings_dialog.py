"""
Settings Dialog — configure Xaman backend connection.

Accessible from the auth screen (gear button) before login.
Stores backend_url, device_api_key and use_xaman in AppConfig (encrypted).
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QMessageBox,
)
from PySide6.QtCore import Qt

from payment_app.ui_payment.styles import PAYMENT_STYLESHEET


class SettingsDialog(QDialog):
    """Configure the Xaman backend connection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustes — Conexión Xaman")
        self.setFixedSize(500, 340)
        self.setStyleSheet(PAYMENT_STYLESHEET)
        self._build_ui()
        self._load_current()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 24, 32, 24)

        title = QLabel("⚙️ Ajustes de Conexión")
        title.setProperty("class", "subheader")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(12)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://mi-backend.railway.app")
        form.addRow("URL del Backend:", self._url_input)

        key_layout = QHBoxLayout()
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.Password)
        self._key_input.setPlaceholderText("Device API Key (emitida por el administrador)")
        key_layout.addWidget(self._key_input)
        show_btn = QPushButton("👁")
        show_btn.setProperty("class", "secondary")
        show_btn.setFixedWidth(36)
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda checked: self._key_input.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        key_layout.addWidget(show_btn)
        form.addRow("Device Key:", key_layout)

        self._xaman_check = QCheckBox("Usar Xaman para firmar transacciones")
        form.addRow("", self._xaman_check)

        layout.addLayout(form)

        info = QLabel(
            "La Device Key la emite el administrador con:\n"
            "python -m backend.issue_device_key --username <tu_usuario>"
        )
        info.setStyleSheet("color: #605E5C; font-size: 8pt;")
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_layout = QHBoxLayout()

        self._test_btn = QPushButton("🔗 Probar Conexión")
        self._test_btn.setProperty("class", "secondary")
        self._test_btn.clicked.connect(self._test_connection)
        btn_layout.addWidget(self._test_btn)

        btn_layout.addStretch()

        save_btn = QPushButton("💾 Guardar")
        save_btn.setProperty("class", "large")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _load_current(self):
        try:
            from core.config_store import get_config
            self._url_input.setText(get_config("backend_url"))
            raw_key = get_config("device_api_key")
            if raw_key:
                self._key_input.setText(raw_key)
            self._xaman_check.setChecked(get_config("use_xaman", "0") == "1")
        except Exception:
            pass

    def _test_connection(self):
        url = self._url_input.text().strip()
        key = self._key_input.text().strip()
        if not url or not key:
            QMessageBox.warning(self, "Datos incompletos",
                                "Ingrese la URL y la Device Key antes de probar.")
            return
        self._test_btn.setEnabled(False)
        self._test_btn.setText("⏳ Probando...")
        try:
            from core.xaman_client import XamanClient
            client = XamanClient(url, key)
            ok = client.ping()
            if ok:
                QMessageBox.information(self, "Conexión exitosa",
                                        "✓ El backend respondió correctamente.")
            else:
                QMessageBox.warning(self, "Sin respuesta",
                                    "El backend no respondió. Verifique la URL y la Device Key.")
        except Exception as e:
            QMessageBox.critical(self, "Error de conexión", str(e))
        finally:
            self._test_btn.setEnabled(True)
            self._test_btn.setText("🔗 Probar Conexión")

    def _save(self):
        url = self._url_input.text().strip()
        key = self._key_input.text().strip()
        use = "1" if self._xaman_check.isChecked() else "0"

        if use == "1" and (not url or not key):
            QMessageBox.warning(self, "Datos incompletos",
                                "Para usar Xaman se requieren URL y Device Key.")
            return

        try:
            from core.config_store import set_config
            if url:
                set_config("backend_url", url)
            if key:
                set_config("device_api_key", key)
            set_config("use_xaman", use)
            QMessageBox.information(self, "Guardado", "Ajustes guardados correctamente.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))
