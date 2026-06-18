"""
ISO 20022 XML Message Generator

Generates core-aligned subset of:
- pacs.008 (Credit Transfer)
- pacs.002 (Payment Status Report)
- camt.054 (Notification)
- camt.053 (Statement)

Note: This is a simplified, educational implementation.
NOT for production banking use.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any
from lxml import etree


class ISO20022Generator:
    """Generator for ISO 20022 XML messages"""

    @staticmethod
    def generate_uetr() -> str:
        """Generate a UETR (Unique End-to-end Transaction Reference) as UUID v4"""
        return str(uuid.uuid4())

    @staticmethod
    def generate_end_to_end_id(prefix: str = "E2E") -> str:
        """Generate an End-to-End ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{prefix}{timestamp}{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    def format_datetime(dt: datetime = None) -> str:
        """Format datetime for ISO 20022 (ISO 8601 with Z suffix for UTC)"""
        if dt is None:
            dt = datetime.now(timezone.utc)
        elif dt.tzinfo is None:
            # Assume UTC when no tzinfo provided
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def format_iso_amount(amount) -> str:
        """Format amount for ISO 20022 — full precision, no trailing zeros, no scientific notation."""
        d = Decimal(str(amount)).normalize()
        # Avoid scientific notation (e.g., 1E+2 -> 100)
        if 'E' in str(d) or 'e' in str(d):
            d = d.quantize(Decimal(1)) if d == d.to_integral() else d.quantize(Decimal('0.000001'))
        return str(d)

    def generate_pacs008(self, payment_data: Dict[str, Any]) -> str:
        """
        Generate pacs.008.001.08 - FIToFICustomerCreditTransfer (simplified)

        Args:
            payment_data: Dict containing:
                - uetr: str
                - amount: float
                - currency: str
                - debtor_name: str
                - debtor_account: str (XRPL address)
                - creditor_name: str
                - creditor_account: str (XRPL address)
                - xrpl_tx_hash: str
                - end_to_end_id: str (optional)

        Returns:
            XML string
        """
        # Create root element
        root = etree.Element(
            "Document",
            nsmap={None: "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"}
        )

        # FIToFICstmrCdtTrf
        fi_to_fi = etree.SubElement(root, "FIToFICstmrCdtTrf")

        # Group Header
        grp_hdr = etree.SubElement(fi_to_fi, "GrpHdr")

        # MsgId — distinct from UETR
        msg_id = etree.SubElement(grp_hdr, "MsgId")
        msg_id.text = (
            f"MSG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            f"-{uuid.uuid4().hex[:8].upper()}"
        )

        cre_dt_tm = etree.SubElement(grp_hdr, "CreDtTm")
        cre_dt_tm.text = self.format_datetime()

        nb_of_txs = etree.SubElement(grp_hdr, "NbOfTxs")
        nb_of_txs.text = "1"

        # Settlement Information (after NbOfTxs, per schema order)
        sttlm_inf = etree.SubElement(grp_hdr, "SttlmInf")
        sttlm_mtd = etree.SubElement(sttlm_inf, "SttlmMtd")
        sttlm_mtd.text = "CLRG"  # XRPL acts as clearing system

        # Credit Transfer Transaction Information
        cdt_trf_tx_inf = etree.SubElement(fi_to_fi, "CdtTrfTxInf")

        # Payment Identification
        pmt_id = etree.SubElement(cdt_trf_tx_inf, "PmtId")

        instr_id = etree.SubElement(pmt_id, "InstrId")
        instr_id.text = payment_data.get('uetr')

        end_to_end_id = etree.SubElement(pmt_id, "EndToEndId")
        end_to_end_id.text = payment_data.get(
            'end_to_end_id',
            self.generate_end_to_end_id()
        )

        uetr = etree.SubElement(pmt_id, "UETR")
        uetr.text = payment_data.get('uetr')

        # Interbank Settlement Amount
        intrbnk_sttlm_amt = etree.SubElement(cdt_trf_tx_inf, "IntrBkSttlmAmt")
        intrbnk_sttlm_amt.set("Ccy", payment_data.get('currency', 'XRP'))
        intrbnk_sttlm_amt.text = self.format_iso_amount(payment_data.get('amount', 0))

        # Interbank Settlement Date (after IntrBkSttlmAmt)
        intr_bk_sttlm_dt = etree.SubElement(cdt_trf_tx_inf, "IntrBkSttlmDt")
        intr_bk_sttlm_dt.text = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Charge Bearer (after IntrBkSttlmDt)
        chrg_br = etree.SubElement(cdt_trf_tx_inf, "ChrgBr")
        chrg_br.text = "DEBT"  # XRPL fee paid by sender

        # Debtor Agent (before Dbtr)
        dbtr_agt = etree.SubElement(cdt_trf_tx_inf, "DbtrAgt")
        dbtr_agt_fin_instn_id = etree.SubElement(dbtr_agt, "FinInstnId")
        dbtr_agt_othr = etree.SubElement(dbtr_agt_fin_instn_id, "Othr")
        dbtr_agt_othr_id = etree.SubElement(dbtr_agt_othr, "Id")
        dbtr_agt_othr_id.text = "XRPL"

        # Debtor (Sender)
        dbtr = etree.SubElement(cdt_trf_tx_inf, "Dbtr")
        dbtr_nm = etree.SubElement(dbtr, "Nm")
        dbtr_nm.text = payment_data.get('debtor_name')

        # Debtor Account
        dbtr_acct = etree.SubElement(cdt_trf_tx_inf, "DbtrAcct")
        dbtr_acct_id = etree.SubElement(dbtr_acct, "Id")
        dbtr_acct_othr = etree.SubElement(dbtr_acct_id, "Othr")
        dbtr_acct_othr_id = etree.SubElement(dbtr_acct_othr, "Id")
        dbtr_acct_othr_id.text = payment_data.get('debtor_account')

        # Creditor Agent (before Cdtr)
        cdtr_agt = etree.SubElement(cdt_trf_tx_inf, "CdtrAgt")
        cdtr_agt_fin_instn_id = etree.SubElement(cdtr_agt, "FinInstnId")
        cdtr_agt_othr = etree.SubElement(cdtr_agt_fin_instn_id, "Othr")
        cdtr_agt_othr_id = etree.SubElement(cdtr_agt_othr, "Id")
        cdtr_agt_othr_id.text = "XRPL"

        # Creditor (Receiver)
        cdtr = etree.SubElement(cdt_trf_tx_inf, "Cdtr")
        cdtr_nm = etree.SubElement(cdtr, "Nm")
        cdtr_nm.text = payment_data.get('creditor_name')

        # Creditor Account
        cdtr_acct = etree.SubElement(cdt_trf_tx_inf, "CdtrAcct")
        cdtr_acct_id = etree.SubElement(cdtr_acct, "Id")
        cdtr_acct_othr = etree.SubElement(cdtr_acct_id, "Othr")
        cdtr_acct_othr_id = etree.SubElement(cdtr_acct_othr, "Id")
        cdtr_acct_othr_id.text = payment_data.get('creditor_account')

        # Supplementary Data (XRPL Transaction Hash + Digital Token Identifier)
        spl_data = etree.SubElement(cdt_trf_tx_inf, "SplmtryData")
        spl_data_envlp = etree.SubElement(spl_data, "Envlp")
        xrpl_hash = etree.SubElement(spl_data_envlp, "XRPLTxHash")
        xrpl_hash.text = payment_data.get('xrpl_tx_hash')
        # XRP Digital Token Identifier per ISO 24165
        dti = etree.SubElement(spl_data_envlp, "DigitalTokenId")
        dti.text = "4H95J0R2X"

        # Convert to string
        return etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        ).decode('utf-8')

    def generate_camt054(self, payment_data: Dict[str, Any]) -> str:
        """
        Generate camt.054.001.08 - BankToCustomerDebitCreditNotification (simplified)

        Args:
            payment_data: Similar to pacs.008

        Returns:
            XML string
        """
        root = etree.Element(
            "Document",
            nsmap={None: "urn:iso:std:iso:20022:tech:xsd:camt.054.001.08"}
        )

        # BkToCstmrDbtCdtNtfctn
        ntfctn = etree.SubElement(root, "BkToCstmrDbtCdtNtfctn")

        # Group Header
        grp_hdr = etree.SubElement(ntfctn, "GrpHdr")
        msg_id = etree.SubElement(grp_hdr, "MsgId")
        msg_id.text = f"NTFCTN-{payment_data.get('uetr')}"

        cre_dt_tm = etree.SubElement(grp_hdr, "CreDtTm")
        cre_dt_tm.text = self.format_datetime()

        # Notification
        ntfctn_item = etree.SubElement(ntfctn, "Ntfctn")
        ntfctn_id = etree.SubElement(ntfctn_item, "Id")
        ntfctn_id.text = payment_data.get('uetr')

        # Account (after Id)
        acct = etree.SubElement(ntfctn_item, "Acct")
        acct_id = etree.SubElement(acct, "Id")
        acct_othr = etree.SubElement(acct_id, "Othr")
        acct_othr_id = etree.SubElement(acct_othr, "Id")
        acct_othr_id.text = payment_data.get('creditor_account', '')

        # Entry
        ntry = etree.SubElement(ntfctn_item, "Ntry")
        amt = etree.SubElement(ntry, "Amt")
        amt.set("Ccy", payment_data.get('currency', 'XRP'))
        amt.text = self.format_iso_amount(payment_data.get('amount', 0))

        cdt_dbt_ind = etree.SubElement(ntry, "CdtDbtInd")
        cdt_dbt_ind.text = "CRDT"  # Credit

        # Sts as complex type (Cd child element)
        sts = etree.SubElement(ntry, "Sts")
        cd_el = etree.SubElement(sts, "Cd")
        cd_el.text = "BOOK"

        # Bank Transaction Code (after Sts, before NtryDtls)
        bk_tx_cd = etree.SubElement(ntry, "BkTxCd")
        prtry = etree.SubElement(bk_tx_cd, "Prtry")
        prtry_cd = etree.SubElement(prtry, "Cd")
        prtry_cd.text = "XRPL-PMT"

        # Booking Date and Value Date (after BkTxCd)
        bookg_dt = etree.SubElement(ntry, "BookgDt")
        bookg_dt_tm = etree.SubElement(bookg_dt, "DtTm")
        bookg_dt_tm.text = self.format_datetime()

        val_dt = etree.SubElement(ntry, "ValDt")
        val_dt_tm = etree.SubElement(val_dt, "DtTm")
        val_dt_tm.text = self.format_datetime()

        # Transaction Details
        ntry_dtls = etree.SubElement(ntry, "NtryDtls")
        tx_dtls = etree.SubElement(ntry_dtls, "TxDtls")

        refs = etree.SubElement(tx_dtls, "Refs")
        end_to_end_id = etree.SubElement(refs, "EndToEndId")
        end_to_end_id.text = payment_data.get('end_to_end_id', self.generate_end_to_end_id())

        uetr = etree.SubElement(refs, "UETR")
        uetr.text = payment_data.get('uetr')

        return etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        ).decode('utf-8')

    def generate_camt053(self, payments_or_data, statement_data: Dict[str, Any] = None) -> str:
        """
        Generate camt.053.001.08 - BankToCustomerStatement (simplified)

        Can be called in two ways:
          generate_camt053(statement_data)           — legacy single-arg form
          generate_camt053(payments, statement_data) — new two-arg form

        Args (two-arg form):
            payments: List of payment dicts (may be empty)
            statement_data: Dict containing:
                - account_id: str
                - account_name: str
                - statement_id: str
                - from_date: datetime
                - to_date: datetime
                - opening_balance: float (optional, default 0)

        Args (single-arg form):
            statement_data: Same dict as above, plus optional 'transactions' key

        Returns:
            XML string
        """
        # Normalise arguments: support both calling conventions
        if statement_data is None:
            # Legacy: generate_camt053(statement_data_dict)
            statement_data = payments_or_data
            transactions = statement_data.get('transactions', [])
        else:
            # New: generate_camt053(payments_list, statement_data_dict)
            transactions = payments_or_data if payments_or_data is not None else []

        root = etree.Element(
            "Document",
            nsmap={None: "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08"}
        )

        # BkToCstmrStmt
        stmt = etree.SubElement(root, "BkToCstmrStmt")

        # Group Header
        grp_hdr = etree.SubElement(stmt, "GrpHdr")
        msg_id = etree.SubElement(grp_hdr, "MsgId")

        # Single statement_id reused for both MsgId and Stmt/Id (avoid double UUID)
        statement_id = statement_data.get('statement_id') or str(uuid.uuid4())
        msg_id.text = statement_id

        cre_dt_tm = etree.SubElement(grp_hdr, "CreDtTm")
        cre_dt_tm.text = self.format_datetime()

        # Statement
        stmt_item = etree.SubElement(stmt, "Stmt")
        stmt_id = etree.SubElement(stmt_item, "Id")
        stmt_id.text = statement_id  # Reuse same ID — no double UUID

        # Account
        acct = etree.SubElement(stmt_item, "Acct")
        acct_id = etree.SubElement(acct, "Id")
        acct_othr = etree.SubElement(acct_id, "Othr")
        acct_othr_id = etree.SubElement(acct_othr, "Id")
        acct_othr_id.text = statement_data.get('account_id')

        # FrToDt (date range, after Acct)
        if statement_data.get('from_date') and statement_data.get('to_date'):
            fr_to_dt = etree.SubElement(stmt_item, "FrToDt")
            fr_dt_tm = etree.SubElement(fr_to_dt, "FrDtTm")
            fr_dt_tm.text = self.format_datetime(statement_data['from_date'])
            to_dt_tm = etree.SubElement(fr_to_dt, "ToDtTm")
            to_dt_tm.text = self.format_datetime(statement_data['to_date'])

        # Balances — opening (OPBD) and closing (CLBD) calculated from transactions

        opening = float(statement_data.get('opening_balance', 0))
        total_tx = sum(float(tx.get('amount', 0)) for tx in transactions)
        closing = opening + total_tx

        for bal_type, bal_amt in [("OPBD", opening), ("CLBD", closing)]:
            bal = etree.SubElement(stmt_item, "Bal")
            tp = etree.SubElement(bal, "Tp")
            cd_or_prtry = etree.SubElement(tp, "CdOrPrtry")
            cd = etree.SubElement(cd_or_prtry, "Cd")
            cd.text = bal_type
            amt = etree.SubElement(bal, "Amt")
            amt.set("Ccy", "XRP")
            amt.text = str(Decimal(str(bal_amt)).quantize(Decimal("0.000001")))
            cdt_dbt_ind = etree.SubElement(bal, "CdtDbtInd")
            cdt_dbt_ind.text = "CRDT"
            dt = etree.SubElement(bal, "Dt")
            dt_dt = etree.SubElement(dt, "Dt")
            dt_dt.text = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Transactions
        for tx in transactions:
            ntry = etree.SubElement(stmt_item, "Ntry")

            ntry_amt = etree.SubElement(ntry, "Amt")
            ntry_amt.set("Ccy", tx.get('currency', 'XRP'))
            ntry_amt.text = self.format_iso_amount(tx.get('amount', 0))

            ntry_cdt_dbt = etree.SubElement(ntry, "CdtDbtInd")
            ntry_cdt_dbt.text = "CRDT"

            # Sts as complex type (Cd child element)
            ntry_sts = etree.SubElement(ntry, "Sts")
            ntry_sts_cd = etree.SubElement(ntry_sts, "Cd")
            ntry_sts_cd.text = "BOOK"

            # Bank Transaction Code (after Sts)
            bk_tx_cd = etree.SubElement(ntry, "BkTxCd")
            prtry = etree.SubElement(bk_tx_cd, "Prtry")
            prtry_cd = etree.SubElement(prtry, "Cd")
            prtry_cd.text = "XRPL-PMT"

            # Entry Details with UETR and EndToEndId
            ntry_dtls = etree.SubElement(ntry, "NtryDtls")
            tx_dtls = etree.SubElement(ntry_dtls, "TxDtls")
            refs = etree.SubElement(tx_dtls, "Refs")
            if tx.get('uetr'):
                uetr_el = etree.SubElement(refs, "UETR")
                uetr_el.text = tx['uetr']
            if tx.get('end_to_end_id'):
                e2e = etree.SubElement(refs, "EndToEndId")
                e2e.text = tx['end_to_end_id']

        return etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        ).decode('utf-8')

    def generate_pacs002(self, payment_data: Dict[str, Any], xrpl_result_code: str = "tesSUCCESS",
                         escrow_fulfillment: str = None) -> str:
        """Generate pacs.002.001.10 - FIToFIPaymentStatusReport (simplified educational subset).

        Maps XRPL transaction result codes to ISO 20022 status codes:
          tesSUCCESS          -> ACSC (AcceptedSettlementCompleted)
          tec* (any tec code) -> RJCT (Rejected) with XRPL code in StsRsnInf
          anything else       -> PDNG (Pending)

        When escrow_fulfillment is provided and status is ACSC, the fulfillment hex
        is embedded in SplmtryData. This makes the ISO message the literal release
        key for the XRPL escrow — whoever holds this message can call EscrowFinish.

        Args:
            payment_data: dict with keys: uetr, end_to_end_id, amount, currency,
                          debtor_name, creditor_name, xrpl_tx_hash,
                          rejection_reason (optional, used for RJCT)
            xrpl_result_code: XRPL engine result string
            escrow_fulfillment: hex fulfillment string (for escrow ACSC messages only)

        Returns:
            XML string
        """
        # Map XRPL result to ISO status
        if xrpl_result_code == "tesSUCCESS":
            tx_status = "ACSC"
        elif xrpl_result_code.startswith("tec"):
            tx_status = "RJCT"
        else:
            tx_status = "PDNG"

        root = etree.Element(
            "Document",
            nsmap={None: "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"},
        )

        fi_to_fi = etree.SubElement(root, "FIToFIPmtStsRpt")

        # Group Header
        grp_hdr = etree.SubElement(fi_to_fi, "GrpHdr")
        msg_id = etree.SubElement(grp_hdr, "MsgId")
        msg_id.text = f"STS-{self.format_datetime()}-{payment_data.get('uetr', '')[:8]}"
        cre_dt_tm = etree.SubElement(grp_hdr, "CreDtTm")
        cre_dt_tm.text = self.format_datetime()

        # Transaction Info and Status
        tx_inf = etree.SubElement(fi_to_fi, "TxInfAndSts")

        orig_refs = etree.SubElement(tx_inf, "OrgnlGrpInf")
        orig_msg_id = etree.SubElement(orig_refs, "OrgnlMsgId")
        orig_msg_id.text = payment_data.get("uetr")
        orig_msg_nm = etree.SubElement(orig_refs, "OrgnlMsgNmId")
        orig_msg_nm.text = "pacs.008.001.08"

        orig_e2e = etree.SubElement(tx_inf, "OrgnlEndToEndId")
        orig_e2e.text = payment_data.get("end_to_end_id", "NOTPROVIDED")

        orig_uetr = etree.SubElement(tx_inf, "OrgnlUETR")
        orig_uetr.text = payment_data.get("uetr")

        tx_sts = etree.SubElement(tx_inf, "TxSts")
        tx_sts.text = tx_status

        # Rejection reason (only for RJCT)
        if tx_status == "RJCT":
            sts_rsn = etree.SubElement(tx_inf, "StsRsnInf")
            rsn = etree.SubElement(sts_rsn, "Rsn")
            prtry = etree.SubElement(rsn, "Prtry")
            prtry.text = xrpl_result_code
            rejection_reason = payment_data.get("rejection_reason")
            if rejection_reason:
                addtl_inf = etree.SubElement(sts_rsn, "AddtlInf")
                addtl_inf.text = rejection_reason

        # Supplementary Data — XRPL hash + escrow fulfillment if applicable
        spl_data = etree.SubElement(tx_inf, "SplmtryData")
        envlp = etree.SubElement(spl_data, "Envlp")

        xrpl_hash_el = etree.SubElement(envlp, "XRPLTxHash")
        xrpl_hash_el.text = payment_data.get("xrpl_tx_hash", "")

        if escrow_fulfillment and tx_status == "ACSC":
            # The fulfillment is the cryptographic release key for the XRPL escrow.
            # Whoever holds this pacs.002 message can call EscrowFinish on the ledger.
            # This demonstrates ISO 20022 messaging driving on-chain settlement.
            ff_el = etree.SubElement(envlp, "EscrowFulfillment")
            ff_el.text = escrow_fulfillment
            note_el = etree.SubElement(envlp, "EscrowReleaseNote")
            note_el.text = "PREIMAGE-SHA-256 fulfillment - releases XRPL escrow via EscrowFinish"

        return etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        ).decode("utf-8")
