"""
Shared theme values: re-exports COLORS, STATUS_STYLES, and the app icon helper.
"""
from admin_app.ui_admin.styles import COLORS  # noqa: F401


def make_app_icon(emoji: str = "☕"):
    """Create a QIcon from an emoji character (64×64 transparent pixmap)."""
    from PySide6.QtGui import QPixmap, QPainter, QFont, QIcon
    from PySide6.QtCore import Qt
    px = QPixmap(64, 64)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    font = QFont()
    font.setPixelSize(48)
    painter.setFont(font)
    painter.drawText(px.rect(), Qt.AlignCenter, emoji)
    painter.end()
    return QIcon(px)

# Single source of truth for payment status display:
# { status_value: (label_es, text_color, bg_color) }
STATUS_STYLES: dict[str, tuple[str, str, str]] = {
    "completed": ("Completado",  "#107C10", "#DFF6DD"),
    "failed":    ("Fallido",     "#D13438", "#FDE7E9"),
    "simulated": ("Simulado",    "#605E5C", "#F3F2F1"),
    "pending":   ("Pendiente",   "#CA5010", "#FFF4CE"),
    "escrowed":  ("En Escrow",   "#0078D4", "#DEECF9"),
    "rejected":  ("Rechazado",   "#A4262C", "#FDE7E9"),
    "refunded":  ("Reembolsado", "#8764B8", "#F0EBF9"),
}
