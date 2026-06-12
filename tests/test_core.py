"""
Baseline tests for Coffee XRPL Platform core modules.
All tests must pass before starting Phase 1 implementation.
"""

import uuid
import pytest
from decimal import Decimal
from lxml import etree


# ── utils ─────────────────────────────────────────────────────────────────────

def test_calculate_payment_total():
    from core.utils import calculate_payment_total
    assert calculate_payment_total(10, 50) == 500.0
    assert calculate_payment_total(0.5, 100) == 50.0


def test_format_currency_mxn():
    from core.utils import format_currency
    assert format_currency(1234.5, "MXN") == "$1,234.50 MXN"
    assert format_currency(0, "MXN") == "$0.00 MXN"


# ── security ──────────────────────────────────────────────────────────────────

def test_hash_verify_password_roundtrip():
    from core.security import hash_password, verify_password
    h = hash_password("mi_contrasena_segura")
    assert verify_password(h, "mi_contrasena_segura") is True
    assert verify_password(h, "contrasena_incorrecta") is False


def test_validate_xrpl_seed_valid():
    from core.security import validate_xrpl_seed
    # Seed generated with xrpl.wallet.Wallet.create()
    assert validate_xrpl_seed("sEdTfvbi28RYrXsm5v9onsua7UhcQrj") is True


def test_validate_xrpl_seed_invalid():
    from core.security import validate_xrpl_seed
    assert validate_xrpl_seed("sInvalido123") is False
    assert validate_xrpl_seed("") is False
    assert validate_xrpl_seed("not_a_seed_at_all") is False


# ── xrpl address validation ───────────────────────────────────────────────────

def test_validate_address_valid():
    from core.xrpl_client import validate_xrpl_address
    # Address generated with xrpl.wallet.Wallet.create()
    assert validate_xrpl_address("rKsq2QsB4erZ9QvixAhg9f8TZPqB2bwJvc") is True


def test_validate_address_invalid():
    from core.xrpl_client import validate_xrpl_address
    # Last char altered — invalid checksum
    assert validate_xrpl_address("rKsq2QsB4erZ9QvixAhg9f8TZPqB2bwJvX") is False
    assert validate_xrpl_address("") is False
    assert validate_xrpl_address(None) is False
    assert validate_xrpl_address("notanaddress") is False


# ── iso_generator ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_payment_data():
    return {
        "uetr": str(uuid.uuid4()),
        "end_to_end_id": "E2E20240101120000ABCD1234",
        "amount": 10.5,
        "currency": "XRP",
        "debtor_name": "Operador Test",
        "debtor_account": "r9cZA1mLK5R5Am25ArfXFmqgNwjZgnfk3",
        "creditor_name": "Productor Test",
        "creditor_account": "rN7n7otQDd6FczFgLdlqtyMVrn3e5PcjXd",
        "xrpl_tx_hash": "ABC123DEF456",
    }


def test_generate_uetr_is_uuid4():
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    u1 = gen.generate_uetr()
    u2 = gen.generate_uetr()
    # Valid UUID v4
    parsed = uuid.UUID(u1, version=4)
    assert str(parsed) == u1
    # Two calls differ
    assert u1 != u2


def test_generate_pacs008_parseable(sample_payment_data):
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    xml_str = gen.generate_pacs008(sample_payment_data)
    # Must be parseable without exception
    root = etree.fromstring(xml_str.encode("utf-8"))
    assert root is not None


def test_generate_camt054_parseable(sample_payment_data):
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    xml_str = gen.generate_camt054(sample_payment_data)
    root = etree.fromstring(xml_str.encode("utf-8"))
    assert root is not None


# ── iso_generator phase 3 ─────────────────────────────────────────────────────

def test_format_iso_amount():
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    assert gen.format_iso_amount(0.123456) == "0.123456"
    assert gen.format_iso_amount(100) == "100"
    assert gen.format_iso_amount(10.5) == "10.5"
    # No scientific notation
    assert "E" not in gen.format_iso_amount(0.000001)
    assert "e" not in gen.format_iso_amount(0.000001)


def test_generate_pacs002_acsc(sample_payment_data):
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    xml_str = gen.generate_pacs002(sample_payment_data, "tesSUCCESS")
    root = etree.fromstring(xml_str.encode("utf-8"))
    assert root is not None
    ns = "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"
    tx_sts = root.find(f".//{{{ns}}}TxSts")
    assert tx_sts is not None and tx_sts.text == "ACSC"


def test_generate_pacs002_rjct(sample_payment_data):
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    xml_str = gen.generate_pacs002(sample_payment_data, "tecUNFUNDED_PAYMENT")
    root = etree.fromstring(xml_str.encode("utf-8"))
    ns = "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"
    tx_sts = root.find(f".//{{{ns}}}TxSts")
    assert tx_sts is not None and tx_sts.text == "RJCT"
    prtry = root.find(f".//{{{ns}}}Prtry")
    assert prtry is not None and prtry.text == "tecUNFUNDED_PAYMENT"


def test_generate_pacs002_pdng(sample_payment_data):
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    xml_str = gen.generate_pacs002(sample_payment_data, "???")
    root = etree.fromstring(xml_str.encode("utf-8"))
    ns = "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"
    tx_sts = root.find(f".//{{{ns}}}TxSts")
    assert tx_sts is not None and tx_sts.text == "PDNG"


# ── daily price model ─────────────────────────────────────────────────────────

def test_daily_price_model_importable():
    """DailyPrice model must exist and have correct fields"""
    from core.models import DailyPrice
    from sqlalchemy import inspect
    mapper = inspect(DailyPrice)
    col_names = {c.key for c in mapper.column_attrs}
    assert "price_date" in col_names
    assert "price_per_kg" in col_names
    assert "set_by_user_id" in col_names


# ── camt.053 ──────────────────────────────────────────────────────────────────

def test_generate_camt053_parseable(sample_payment_data):
    """generate_camt053 must produce well-formed XML"""
    from core.iso_generator import ISO20022Generator
    from datetime import datetime, timezone
    gen = ISO20022Generator()

    # Minimal mock payment-like dict approach — camt.053 accepts a list of
    # objects with .uetr, .amount, .currency, .timestamp, .producer.xrpl_address
    # Use the generator with real-looking statement data
    statement_data = {
        "statement_id": "STMT-20240101-TEST01",
        "account_id": "rKsq2QsB4erZ9QvixAhg9f8TZPqB2bwJvc",
        "account_name": "Test Operator",
        "opening_balance": 100.0,
        "from_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "to_date": datetime(2024, 1, 2, tzinfo=timezone.utc),
    }
    # generate_camt053 with empty payment list must still produce valid XML
    xml_str = gen.generate_camt053([], statement_data)
    from lxml import etree
    root = etree.fromstring(xml_str.encode("utf-8"))
    assert root is not None


# ── pacs.002 message type ─────────────────────────────────────────────────────

def test_message_type_enum_has_pacs002():
    from core.models import MessageType
    assert hasattr(MessageType, "PACS_002")
    assert MessageType.PACS_002.value == "pacs.002"


def test_payment_status_has_simulated():
    from core.models import PaymentStatus
    assert hasattr(PaymentStatus, "SIMULATED")
    assert PaymentStatus.SIMULATED.value == "simulated"
