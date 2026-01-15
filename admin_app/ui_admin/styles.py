"""
Shared styles for Admin Application
Fluent-inspired design system
"""

# Color palette
COLORS = {
    'primary': '#0078D4',
    'primary_hover': '#106EBE',
    'primary_pressed': '#005A9E',
    'secondary': '#2B88D8',
    'success': '#107C10',
    'warning': '#FF8C00',
    'danger': '#D13438',
    'background': '#F3F3F3',
    'surface': '#FFFFFF',
    'surface_secondary': '#FAFAFA',
    'border': '#E1E1E1',
    'text_primary': '#201F1E',
    'text_secondary': '#605E5C',
    'text_disabled': '#A19F9D',
}

# Main stylesheet
ADMIN_STYLESHEET = f"""
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

/* Date pickers */
QDateEdit {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 8px;
    min-height: 32px;
    color: {COLORS['text_primary']};
}}

QDateEdit:focus {{
    border: 2px solid {COLORS['primary']};
    padding: 7px;
}}

QDateEdit::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid {COLORS['border']};
}}

QDateEdit::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {COLORS['text_primary']};
    margin-right: 5px;
}}


QCalendarWidget {{
    background-color: {COLORS['surface']};
    color: {COLORS['text_primary']};
}}

QCalendarWidget QToolButton {{
    background-color: {COLORS['surface']};
    color: {COLORS['text_primary']};
    border: none;
    padding: 5px;
}}

QCalendarWidget QMenu {{
    background-color: {COLORS['surface']};
    color: {COLORS['text_primary']};
}}

QCalendarWidget QSpinBox {{
    background-color: {COLORS['surface']};
    color: {COLORS['text_primary']};
}}

QCalendarWidget QAbstractItemView {{
    background-color: {COLORS['surface']};
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['primary']};
    selection-color: white;
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

/* Message boxes */
QMessageBox {{
    background-color: {COLORS['surface']};
}}

/* Status bar */
QStatusBar {{
    background-color: {COLORS['surface']};
    border-top: 1px solid {COLORS['border']};
    color: {COLORS['text_secondary']};
}}

/* Dialogs */
QDialog {{
    background-color: {COLORS['background']};
    color: {COLORS['text_primary']};
}}
"""
