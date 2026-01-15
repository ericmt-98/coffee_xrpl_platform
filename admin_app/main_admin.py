"""
Main entry point for Admin Application
"""

import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMessageBox
from admin_app.ui_admin.login_window import LoginWindow
from admin_app.ui_admin.dashboard import AdminDashboard


def main():
    """Main function"""
    app = QApplication(sys.argv)
    app.setApplicationName("Coffee XRPL Platform - Admin")
    
    # Show login window
    login_window = LoginWindow()
    
    if login_window.exec() == LoginWindow.Accepted:
        # Login successful, show dashboard
        if login_window.authenticated_user:
            dashboard = AdminDashboard(login_window.authenticated_user)
            dashboard.show()
            sys.exit(app.exec())
        else:
            QMessageBox.critical(
                None,
                "Error",
                "Error de autenticación. Por favor, intente nuevamente."
            )
            sys.exit(1)
    else:
        # Login cancelled
        sys.exit(0)


if __name__ == "__main__":
    main()
