"""
Shared styles for Payment Application
Fluent-inspired design system (matching Admin app)
"""

# Reuse the same color palette and base styles from admin app
from admin_app.ui_admin.styles import COLORS

# Payment app stylesheet (same as admin with minor tweaks)
PAYMENT_STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS['background']};
}}

QWidget {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
    color: {COLORS['text_primary']};
}}

/* Buttons */
QPushButton {{
    background-color: {COLORS['primary']};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: {COLORS['primary_hover']};
}}

QPushButton:pressed {{
    background-color: {COLORS['primary_pressed']};
}}

QPushButton:disabled {{
    background-color: {COLORS['border']};
    color: {COLORS['text_disabled']};
}}

QPushButton.secondary {{
    background-color: {COLORS['surface']};
    color: {COLORS['primary']};
    border: 1px solid {COLORS['border']};
}}

QPushButton.secondary:hover {{
    background-color: {COLORS['surface_secondary']};
    border-color: {COLORS['primary']};
}}

QPushButton.danger {{
    background-color: {COLORS['danger']};
}}

QPushButton.success {{
    background-color: {COLORS['success']};
}}

QPushButton.large {{
    min-height: 48px;
    font-size: 12pt;
}}

/* Input fields */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 8px;
    min-height: 32px;
}}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 2px solid {COLORS['primary']};
    padding: 7px;
}}

QLineEdit:disabled, QTextEdit:disabled {{
    background-color: {COLORS['surface_secondary']};
    color: {COLORS['text_disabled']};
}}

/* Labels */
QLabel {{
    color: {COLORS['text_primary']};
}}

QLabel.header {{
    font-size: 24pt;
    font-weight: 600;
    color: {COLORS['text_primary']};
}}

QLabel.subheader {{
    font-size: 14pt;
    font-weight: 600;
    color: {COLORS['text_secondary']};
}}

QLabel.caption {{
    font-size: 9pt;
    color: {COLORS['text_secondary']};
}}

QLabel.amount {{
    font-size: 32pt;
    font-weight: 700;
    color: {COLORS['success']};
}}

/* Tables */
QTableWidget {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    gridline-color: {COLORS['border']};
}}

QTableWidget::item {{
    padding: 8px;
}}

QTableWidget::item:selected {{
    background-color: {COLORS['primary']};
    color: white;
}}

QHeaderView::section {{
    background-color: {COLORS['surface_secondary']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 8px;
    font-weight: 600;
}}

/* Group boxes */
QGroupBox {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
    color: {COLORS['text_primary']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {COLORS['text_primary']};
}}

/* Tabs */
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    background-color: {COLORS['surface']};
}}

QTabBar::tab {{
    background-color: {COLORS['surface_secondary']};
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 8px 16px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {COLORS['surface']};
    border-bottom: 2px solid {COLORS['primary']};
}}

QTabBar::tab:hover {{
    background-color: {COLORS['surface']};
}}

/* Scroll bars */
QScrollBar:vertical {{
    background-color: {COLORS['surface_secondary']};
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border']};
    border-radius: 6px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['text_disabled']};
}}

/* Status bar */
QStatusBar {{
    background-color: {COLORS['surface']};
    border-top: 1px solid {COLORS['border']};
    color: {COLORS['text_secondary']};
}}

/* List widgets */
QListWidget {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
}}

QListWidget::item {{
    padding: 12px;
    border-bottom: 1px solid {COLORS['border']};
}}

QListWidget::item:selected {{
    background-color: {COLORS['primary']};
    color: white;
}}

QListWidget::item:hover {{
    background-color: {COLORS['surface_secondary']};
}}

/* Dialogs */
QDialog {{
    background-color: {COLORS['background']};
    color: {COLORS['text_primary']};
}}
"""
