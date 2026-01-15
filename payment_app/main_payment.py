"""
Main entry point for Payment Application
"""

import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMessageBox
from payment_app.ui_payment.auth_flow import AuthFlowDialog
from payment_app.ui_payment.dashboard import PaymentDashboard
from core.database import database_exists


def main():
    """Main function"""
    app = QApplication(sys.argv)
    app.setApplicationName("Coffee XRPL Platform - Payments")
    
    # Check if database exists
    if not database_exists():
        QMessageBox.critical(
            None,
            "Error",
            "La base de datos no ha sido inicializada.\n\n"
            "Por favor, ejecute la aplicación de Administrador primero\n"
            "para inicializar el sistema."
        )
        sys.exit(1)
    
    # Show authentication flow
    auth_dialog = AuthFlowDialog()
    
    if auth_dialog.exec() == AuthFlowDialog.Accepted:
        # Authentication successful, show dashboard
        if auth_dialog.authenticated_user and auth_dialog.xrpl_seed:
            dashboard = PaymentDashboard(
                auth_dialog.authenticated_user,
                auth_dialog.xrpl_seed
            )
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
        # Authentication cancelled
        sys.exit(0)


if __name__ == "__main__":
    main()
