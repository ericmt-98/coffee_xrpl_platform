# Coffee XRPL Platform - Quick Start Guide

## 🚀 Getting Started (5 Minutes)

### Prerequisites
- Python 3.10 or higher
- Windows OS
- Internet connection (for XRPL Testnet)

---

## Step 1: Install Dependencies ✅

Dependencies have been installed! If you need to reinstall:

```bash
cd coffee_xrpl_platform
pip install -r requirements.txt
```

---

## Step 2: Get Testnet XRP

1. Visit: https://xrpl.org/xrp-testnet-faucet.html
2. Click "Generate Testnet credentials"
3. **Save these values**:
   - Address (starts with 'r')
   - Secret (starts with 's')

Example:
```
Address: rN7n7otQDd6FczFgLdlqtyMVrn3e5PcjXd
Secret: sEdSKaCy2JT7JaM7v95H9SxkhP9wS2r
```

---

## Step 3: Run Admin App

```bash
python admin_app/main_admin.py
```

> **Note**: Make sure you're in the `coffee_xrpl_platform` directory when running this command.

### First Time Setup

1. **Initialize System**:
   - Name: `Admin Sistema`
   - Username: `admin`
   - Password: `admin123` (or your choice)
   - Click "Inicializar Sistema"

2. **Login**:
   - Username: `admin`
   - Password: (what you set)

3. **Create Operator**:
   - Go to "Gestión de Usuarios" tab
   - Name: `Juan Pérez`
   - Date of Birth: `01/01/1990`
   - XRPL Address: (paste your Testnet address from Step 2)
   - Click "Crear Usuario"
   - **Note the generated ID** (e.g., `JPrN7Xd`)

---

## Step 4: Run Payment App

```bash
python payment_app/main_payment.py
```

### Login (3 Steps)

**Step 1 - ID**:
- Enter the ID from Step 3 (e.g., `JPrN7Xd`)
- Click "Siguiente"

**Step 2 - Password**:
- First time: Create a password (min 8 chars)
- Click "Crear y Continuar"

**Step 3 - Wallet**:
- Enter your XRPL Secret from Step 2
- Click "Iniciar Sesión"

---

## Step 5: Make Your First Payment

### Create a Producer

1. Click "➕ Nuevo Productor"
2. Fill in:
   - Name: `Productor Café Chiapas`
   - XRPL Address: (use another Testnet address or the same one for testing)
3. Click "Guardar Productor"

### Execute Payment

1. Select the producer from the list
2. Enter weight: `10.5` kg
3. Price per kg: `50.00` MXN
4. Total will auto-calculate: `$525.00 MXN`
5. Select token: `XRP`
6. Click "EJECUTAR PAGO"
7. Confirm

### View Results

- Check "Historial" tab
- Double-click payment for details
- Export to Excel if desired

---

## 📊 What Just Happened?

1. ✅ **XRPL Transaction**: Real payment sent on Testnet
2. ✅ **ISO 20022 Messages**: pacs.008 and camt.054 generated
3. ✅ **Database Record**: Payment, delivery, and ISO messages stored
4. ✅ **Audit Trail**: All actions logged

---

## 🔍 Explore Features

### Admin App
- Create multiple operators
- View audit logs
- Export data to Excel
- Export ISO 20022 XML files

### Payment App
- Create multiple producers
- Upload producer ID images
- Try different tokens (USDC, RLUSD)
- View payment history
- Export to Excel

---

## 🛠️ Troubleshooting

### "Database not initialized"
→ Run Admin app first and complete setup

### "Seed inválido"
→ Make sure seed starts with 's' and is from XRPL Testnet faucet

### "Dirección no coincide"
→ The seed must match the XRPL address registered for the user

### "Payment failed"
→ Check:
- Testnet has XRP balance
- Internet connection active
- XRPL Testnet is online

---

## 📁 File Locations

- **Database**: `data/coffee_platform.db`
- **Encryption Key**: `data/.encryption_key`
- **Producer Images**: `data/producer_images/`
- **Exports**: (you choose location when exporting)

---

## 🎯 Next Steps

1. **Test Multiple Payments**: Create more producers and payments
2. **Review ISO Messages**: Export XML and examine structure
3. **Check Audit Logs**: See all tracked actions
4. **Explore History**: Filter and export payment data

---

## 📚 Documentation

- **Full Walkthrough**: [walkthrough.md](file:///C:/Users/eric/.gemini/antigravity/brain/d28b5b86-825f-4acd-8cd2-42f329ed9862/walkthrough.md)
- **Implementation Plan**: [implementation_plan.md](file:///C:/Users/eric/.gemini/antigravity/brain/d28b5b86-825f-4acd-8cd2-42f329ed9862/implementation_plan.md)
- **README**: [README.md](file:///c:/Users/eric/Desktop/software/coffee_xrpl_platform/README.md)

---

## ✨ Enjoy Your Coffee Payment Platform!

Questions? Check the walkthrough document for detailed technical information.
