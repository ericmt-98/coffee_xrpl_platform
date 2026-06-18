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


# ── extended pacs.002 (generate_pacs002 v2) ───────────────────────────────────

def test_generate_uetr_unique():
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    assert gen.generate_uetr() != gen.generate_uetr()


def test_calculate_payment_total_zero():
    from core.utils import calculate_payment_total
    assert calculate_payment_total(0, 50) == 0.0


def test_format_currency_xrp():
    from core.utils import format_currency
    result = format_currency(0.123456, "XRP")
    assert "0.123456" in result and "XRP" in result


def test_truncate_text():
    from core.utils import truncate_text
    assert truncate_text("hello", 10) == "hello"
    assert truncate_text("hello world long text", 10) == "hello w..."
    assert len(truncate_text("a" * 100, 20)) == 20


def test_password_wrong():
    from core.security import hash_password, verify_password
    hashed = hash_password("correct")
    assert verify_password(hashed, "wrong") is False


def test_generate_escrow_condition_structure():
    """Condition must be 39 bytes, fulfillment 34 bytes, and SHA-256 must verify."""
    import hashlib
    from core.security import generate_escrow_condition
    condition_hex, fulfillment_hex = generate_escrow_condition()

    condition_bytes = bytes.fromhex(condition_hex)
    fulfillment_bytes = bytes.fromhex(fulfillment_hex)

    assert len(condition_bytes) == 39, f"Expected 39, got {len(condition_bytes)}"
    # Fulfillment DER: A0(1) + 22(1) + 8020(2) + 32-byte preimage = 36 bytes total
    assert len(fulfillment_bytes) == 36, f"Expected 36, got {len(fulfillment_bytes)}"

    # Verify DER headers
    assert condition_bytes[:4] == bytes.fromhex("A0258020")
    assert condition_bytes[-3:] == bytes.fromhex("810120")
    assert fulfillment_bytes[:4] == bytes.fromhex("A0228020")

    # Verify SHA-256 linkage: sha256(preimage) must match condition's hash field
    preimage = fulfillment_bytes[4:]          # 32 bytes after 4-byte DER header
    condition_hash = condition_bytes[4:36]    # bytes 4..35 = sha256 digest
    assert hashlib.sha256(preimage).digest() == condition_hash


def test_generate_escrow_condition_unique():
    from core.security import generate_escrow_condition
    c1, f1 = generate_escrow_condition()
    c2, f2 = generate_escrow_condition()
    assert c1 != c2
    assert f1 != f2


def test_pacs002_acsc_no_escrow(sample_payment_data):
    """ACSC status without escrow: TxSts=ACSC, no EscrowFulfillment element."""
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    xml = gen.generate_pacs002(sample_payment_data, xrpl_result_code="tesSUCCESS")
    root = etree.fromstring(xml.encode())
    ns = {"ns": "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"}
    tx_sts = root.find(".//ns:TxSts", ns)
    assert tx_sts is not None and tx_sts.text == "ACSC"
    ff_el = root.find(".//ns:EscrowFulfillment", ns)
    assert ff_el is None


def test_pacs002_rjct_has_reason(sample_payment_data):
    """RJCT status includes both proprietary code and rejection_reason."""
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    data = dict(sample_payment_data)
    data["rejection_reason"] = "Muestra de café no cumple SCA 80+"
    xml = gen.generate_pacs002(data, xrpl_result_code="tecUNFUNDED_PAYMENT")
    root = etree.fromstring(xml.encode())
    ns = {"ns": "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"}
    tx_sts = root.find(".//ns:TxSts", ns)
    assert tx_sts is not None and tx_sts.text == "RJCT"
    addtl_inf = root.find(".//ns:AddtlInf", ns)
    assert addtl_inf is not None and "SCA" in addtl_inf.text


def test_pacs002_pdng_for_unknown_code(sample_payment_data):
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    xml = gen.generate_pacs002(sample_payment_data, xrpl_result_code="temUNKNOWN")
    root = etree.fromstring(xml.encode())
    ns = {"ns": "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"}
    tx_sts = root.find(".//ns:TxSts", ns)
    assert tx_sts is not None and tx_sts.text == "PDNG"


def test_pacs002_acsc_with_escrow_fulfillment(sample_payment_data):
    """ACSC + escrow: EscrowFulfillment element present with correct hex value."""
    from core.iso_generator import ISO20022Generator
    from core.security import generate_escrow_condition
    gen = ISO20022Generator()
    _, fulfillment_hex = generate_escrow_condition()
    xml = gen.generate_pacs002(
        sample_payment_data,
        xrpl_result_code="tesSUCCESS",
        escrow_fulfillment=fulfillment_hex,
    )
    root = etree.fromstring(xml.encode())
    ns = {"ns": "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"}
    ff_el = root.find(".//ns:EscrowFulfillment", ns)
    assert ff_el is not None and ff_el.text == fulfillment_hex


def test_pacs002_orgnl_grp_inf_present(sample_payment_data):
    """OrgnlGrpInf block must be present with uetr as OrgnlMsgId."""
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    xml = gen.generate_pacs002(sample_payment_data, xrpl_result_code="tesSUCCESS")
    root = etree.fromstring(xml.encode())
    ns = {"ns": "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"}
    orig_msg_id = root.find(".//ns:OrgnlGrpInf/ns:OrgnlMsgId", ns)
    assert orig_msg_id is not None
    assert orig_msg_id.text == sample_payment_data["uetr"]
    orig_msg_nm = root.find(".//ns:OrgnlGrpInf/ns:OrgnlMsgNmId", ns)
    assert orig_msg_nm is not None and orig_msg_nm.text == "pacs.008.001.08"


def test_pacs002_splmtry_data_xrpl_hash(sample_payment_data):
    """SplmtryData/Envlp/XRPLTxHash must contain the tx hash from payment_data."""
    from core.iso_generator import ISO20022Generator
    gen = ISO20022Generator()
    xml = gen.generate_pacs002(sample_payment_data, xrpl_result_code="tesSUCCESS")
    root = etree.fromstring(xml.encode())
    ns = {"ns": "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"}
    xrpl_hash = root.find(".//ns:XRPLTxHash", ns)
    assert xrpl_hash is not None
    assert xrpl_hash.text == sample_payment_data["xrpl_tx_hash"]


def test_pacs002_escrow_not_embedded_for_rjct(sample_payment_data):
    """Escrow fulfillment must NOT appear in the XML when status is RJCT."""
    from core.iso_generator import ISO20022Generator
    from core.security import generate_escrow_condition
    gen = ISO20022Generator()
    _, fulfillment_hex = generate_escrow_condition()
    xml = gen.generate_pacs002(
        sample_payment_data,
        xrpl_result_code="tecNO_DST",
        escrow_fulfillment=fulfillment_hex,
    )
    root = etree.fromstring(xml.encode())
    ns = {"ns": "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"}
    ff_el = root.find(".//ns:EscrowFulfillment", ns)
    assert ff_el is None


# ── Xaman: resolve_status (pure function, no network) ────────────────────────

def test_resolve_status_signed_ok():
    from payment_app.ui_payment.xaman_sign_dialog import resolve_status
    status = {"resolved": True, "signed": True, "cancelled": False, "expired": False,
              "txid": "ABCD1234", "account": "rTestAddr", "issued_user_token": "tok"}
    result = resolve_status(status, "rTestAddr")
    assert result["ok"] is True
    assert result["txid"] == "ABCD1234"
    assert result["reason"] == "signed"


def test_resolve_status_wrong_account():
    from payment_app.ui_payment.xaman_sign_dialog import resolve_status
    status = {"resolved": True, "signed": True, "cancelled": False, "expired": False,
              "txid": "ABCD1234", "account": "rOtherAddr", "issued_user_token": None}
    result = resolve_status(status, "rExpectedAddr")
    assert result["ok"] is False
    assert result["reason"] == "wrong_account"


def test_resolve_status_cancelled():
    from payment_app.ui_payment.xaman_sign_dialog import resolve_status
    status = {"resolved": True, "signed": False, "cancelled": True, "expired": False,
              "txid": None, "account": None, "issued_user_token": None}
    result = resolve_status(status, "rSomeAddr")
    assert result["ok"] is False
    assert result["reason"] == "cancelled"


def test_resolve_status_expired():
    from payment_app.ui_payment.xaman_sign_dialog import resolve_status
    status = {"resolved": True, "signed": False, "cancelled": False, "expired": True,
              "txid": None, "account": None, "issued_user_token": None}
    result = resolve_status(status, "rSomeAddr")
    assert result["ok"] is False
    assert result["reason"] == "expired"


def test_resolve_status_not_resolved():
    from payment_app.ui_payment.xaman_sign_dialog import resolve_status
    status = {"resolved": False, "signed": False, "cancelled": False, "expired": False,
              "txid": None, "account": None, "issued_user_token": None}
    result = resolve_status(status, "rSomeAddr")
    assert result["ok"] is False
    assert result["reason"] == "pending"


def test_resolve_status_no_expected_account():
    """When expected_account is empty string, any signed account is accepted."""
    from payment_app.ui_payment.xaman_sign_dialog import resolve_status
    status = {"resolved": True, "signed": True, "cancelled": False, "expired": False,
              "txid": "TXHASH", "account": "rAnyone", "issued_user_token": None}
    result = resolve_status(status, "")
    assert result["ok"] is True


# ── config_store (encrypted roundtrip) ───────────────────────────────────────

def test_config_store_roundtrip(tmp_path, monkeypatch):
    """set_config / get_config should roundtrip without touching the real DB."""
    import os
    # Point security module to a temp key file
    monkeypatch.setenv("HOME", str(tmp_path))
    import core.security as sec
    monkeypatch.setattr(sec, "_ENCRYPTION_KEY_FILE", str(tmp_path / ".enc_key"))

    # Use an in-memory SQLite for this test
    import sqlalchemy
    from sqlalchemy.orm import sessionmaker
    import core.database as db_module
    import core.models as models_module

    test_engine = sqlalchemy.create_engine("sqlite:///:memory:",
                                           connect_args={"check_same_thread": False})
    models_module.Base.metadata.create_all(test_engine)
    TestSession = sqlalchemy.orm.scoped_session(
        sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    )
    monkeypatch.setattr(db_module, "Session", TestSession)
    monkeypatch.setattr(db_module, "engine", test_engine)

    from core.config_store import set_config, get_config
    set_config("backend_url", "https://example.com")
    assert get_config("backend_url") == "https://example.com"
    assert get_config("missing_key", "default") == "default"
