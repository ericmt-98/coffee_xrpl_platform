# ☕ Coffee XRPL Platform

> **Nota**: Este software ha sido desarrollado con fines educativos y de demostración sobre el uso de la red XRPL.

The **Coffee XRPL Platform** is an educational project designed as a financial bridge to synchronize the speed and efficiency of the **XRP Ledger** with global banking standards. It serves as a comprehensive middleware solution for demonstrating how to generate, track, and audit cross-border payments while maintaining compliance through **ISO 20022** XML messaging.

---

## 🏗️ Technical Architecture

The platform is built on three core pillars that ensure security, transparency, and financial compliance:

### 🐍 Python & Core Architecture
- **Modular Design**: Separation between core logic and specialized applications (`admin_app/` and `payment_app/`).
- **Modern UI**: Powered by **PySide6**, providing a high-performance Qt-based experience.
- **Data Integrity**: Uses **SQLAlchemy** for reliable persistence and **Argon2** for state-of-the-art security.

### ⛓️ XRPL Integration
- **Real-time Settlement**: Leverages `xrpl-py` for instant payment submission and ledger verification.
- **Token Management**: Integrated logic for handling exchange rates between MXN and assets like XRP, USDC, and RLUSD.
- **Transparency**: Every transaction is cryptographically linked to its hash on the ledger for full auditability.

### 🏦 Financial Compliance
- **ISO 20022 Compliance**: Automates the generation of banking standard messages like `pacs.008` (Credit Transfer), `camt.054` (Notifications), and `camt.053` (Statements).
- **Financial Bridge**: Consolidates decentralized transaction hashes into structured XML documents ready for traditional banking ingestion.
- **UETR Tracking**: Implements Unique End-to-end Transaction References for global payment traceability.

---

## 🚀 Key Features

- **Multi-App Ecosystem**: Dedicated interfaces for Administrative oversight and Payment execution.
- **Standards Integration**: Automatic conversion of XRPL events into `pacs.008` and `camt.054` standards.
- **Integrated Security**: Encrypted session handling and secure credential management.
- **Real-time Monitoring**: Instant balance checks and transaction history directly from the XRPL.

## 🛠️ Tech Stack

- **Core**: Python 3.9+
- **GUI**: PySide6 (Qt for Python)
- **Blockchain**: XRPL Ledger (via `xrpl-py`)
- **Database**: SQLite (via SQLAlchemy)
- **Messaging**: lxml & Jinja2 (for ISO 20022 XML generation)

---

## 🏃 Quick Start

Refer to the [QUICKSTART.md](./QUICKSTART.md) file for detailed installation and setup instructions.

---

*Note: This platform is currently in a testing/educational phase and is configured for the XRPL Testnet.*
