"""
Shared UI components for Coffee XRPL Platform.
"""
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTableWidget, QWidget
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation
from PySide6.QtGui import QColor, QBrush

from shared_ui.theme import STATUS_STYLES


# ---------------------------------------------------------------------------
# make_status_item
# ---------------------------------------------------------------------------

def make_status_item(status_value: str) -> "QTableWidgetItem":
    """Return a styled QTableWidgetItem for a payment status string."""
    from PySide6.QtWidgets import QTableWidgetItem
    label, text_color, bg_color = STATUS_STYLES.get(
        status_value,
        (status_value.capitalize(), "#605E5C", "#F3F2F1"),
    )
    item = QTableWidgetItem(label)
    item.setForeground(QBrush(QColor(text_color)))
    item.setBackground(QBrush(QColor(bg_color)))
    item.setTextAlignment(Qt.AlignCenter)
    return item


# ---------------------------------------------------------------------------
# KpiCard
# ---------------------------------------------------------------------------

class KpiCard(QGroupBox):
    """Metric card widget with a large coloured value label."""

    def __init__(self, title: str, initial_value: str = "—",
                 color: str = "#0078D4", parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        self._label = QLabel(initial_value)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(
            f"font-size: 20pt; font-weight: bold; color: {color}; padding: 10px;"
        )
        layout.addWidget(self._label)

    def set_value(self, value: str) -> None:
        self._label.setText(value)


# ---------------------------------------------------------------------------
# EmptyStateOverlay
# ---------------------------------------------------------------------------

class EmptyStateOverlay(QLabel):
    """
    Transparent overlay shown on top of a QTableWidget when it has no rows.
    Attach via attach_empty_state(table, text) or instantiate directly.
    """

    def __init__(self, table: QTableWidget,
                 text: str = "Sin datos para los filtros seleccionados"):
        super().__init__(text, table)
        self._table = table
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "color: #A19F9D; font-size: 12pt; background: transparent;"
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        # Auto-update on model changes
        model = table.model()
        model.rowsInserted.connect(self._sync)
        model.rowsRemoved.connect(self._sync)
        model.modelReset.connect(self._sync)
        table.installEventFilter(self)
        self._sync()

    def _sync(self):
        visible = self._table.rowCount() == 0
        self.setVisible(visible)
        if visible:
            self.setGeometry(0, 0, self._table.width(), self._table.height())

    def eventFilter(self, obj, event):
        if obj is self._table and event.type() == event.Type.Resize:
            if self.isVisible():
                self.setGeometry(0, 0, self._table.width(), self._table.height())
        return False


def attach_empty_state(table: QTableWidget,
                       text: str = "Sin datos para los filtros seleccionados"
                       ) -> EmptyStateOverlay:
    """Attach and return an EmptyStateOverlay to a QTableWidget."""
    return EmptyStateOverlay(table, text)


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------

class Toast(QLabel):
    """Non-modal floating notification shown at the bottom-centre of parent."""

    @staticmethod
    def show_message(parent: QWidget, text: str, duration_ms: int = 3000) -> "Toast":
        toast = Toast(text, parent)
        toast._start(duration_ms)
        return toast

    def __init__(self, text: str, parent: QWidget):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background-color: rgba(32,31,30,210); color: white; "
            "border-radius: 8px; padding: 10px 24px; font-size: 10pt;"
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.adjustSize()
        tw = max(self.width() + 40, 200)
        th = self.height() + 12
        self.setFixedSize(tw, th)
        pw, ph = parent.width(), parent.height()
        self.move((pw - tw) // 2, ph - th - 40)
        self.raise_()
        self.show()

    def _start(self, duration_ms: int):
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)

        def _fade():
            self._anim = QPropertyAnimation(self._effect, b"opacity")
            self._anim.setDuration(400)
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            self._anim.finished.connect(self.deleteLater)
            self._anim.start()

        QTimer.singleShot(duration_ms, _fade)


# ---------------------------------------------------------------------------
# StepIndicator
# ---------------------------------------------------------------------------

class StepIndicator(QWidget):
    """Horizontal step progress bar for multi-step dialogs."""

    def __init__(self, steps: list, parent=None):
        super().__init__(parent)
        self._steps = steps
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)
        self._labels: list[QLabel] = []
        for i, step_label in enumerate(steps):
            if i > 0:
                sep = QLabel("  ──  ")
                sep.setStyleSheet("color: #C8C6C4; font-size: 8pt;")
                layout.addWidget(sep)
            lbl = QLabel(f"{i + 1}. {step_label}")
            lbl.setAlignment(Qt.AlignCenter)
            self._labels.append(lbl)
            layout.addWidget(lbl)
        self.set_current(0)

    def set_current(self, index: int) -> None:
        for i, lbl in enumerate(self._labels):
            if i < index:
                lbl.setStyleSheet(
                    "background-color: #DFF6DD; color: #107C10; "
                    "border-radius: 12px; padding: 4px 12px; font-weight: 600;"
                )
            elif i == index:
                lbl.setStyleSheet(
                    "background-color: #0078D4; color: white; "
                    "border-radius: 12px; padding: 4px 12px; font-weight: 600;"
                )
            else:
                lbl.setStyleSheet(
                    "background-color: #F3F2F1; color: #A19F9D; "
                    "border-radius: 12px; padding: 4px 12px;"
                )


# ---------------------------------------------------------------------------
# add_password_toggle
# ---------------------------------------------------------------------------

def add_password_toggle(line_edit: QLineEdit) -> QPushButton:
    """
    Return a checkable QPushButton that toggles a QLineEdit's echo mode.
    Place the button next to the line_edit in the parent's layout.
    """
    btn = QPushButton("👁")
    btn.setProperty("class", "secondary")
    btn.setCheckable(True)
    btn.setFixedWidth(40)
    btn.setToolTip("Mostrar/ocultar contraseña")

    def _toggle(checked: bool):
        line_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        btn.setText("🙈" if checked else "👁")

    btn.toggled.connect(_toggle)
    return btn
