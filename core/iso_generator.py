"""
ISO 20022 XML Message Generator

Generates core-aligned subset of:
- pacs.008 (Credit Transfer)
- camt.054 (Notification)
- camt.053 (Statement)

Note: This is a simplified, educational implementation.
NOT for production banking use.
"""

import uuid
from datetime import datetime
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
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"{prefix}{timestamp}{uuid.uuid4().hex[:8].upper()}"
    
    @staticmethod
    def format_datetime(dt: datetime = None) -> str:
        """Format datetime for ISO 20022 (ISO 8601)"""
        if dt is None:
            dt = datetime.utcnow()
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    
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
            xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08",
            nsmap={None: "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"}
        )
        
        # FIToFICstmrCdtTrf
        fi_to_fi = etree.SubElement(root, "FIToFICstmrCdtTrf")
        
        # Group Header
        grp_hdr = etree.SubElement(fi_to_fi, "GrpHdr")
        msg_id = etree.SubElement(grp_hdr, "MsgId")
        msg_id.text = payment_data.get('uetr')
        
        cre_dt_tm = etree.SubElement(grp_hdr, "CreDtTm")
        cre_dt_tm.text = self.format_datetime()
        
        nb_of_txs = etree.SubElement(grp_hdr, "NbOfTxs")
        nb_of_txs.text = "1"
        
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
        intrbnk_sttlm_amt.text = f"{payment_data.get('amount'):.2f}"
        
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
        
        # Supplementary Data (XRPL Transaction Hash)
        spl_data = etree.SubElement(cdt_trf_tx_inf, "SplmtryData")
        spl_data_envlp = etree.SubElement(spl_data, "Envlp")
        xrpl_hash = etree.SubElement(spl_data_envlp, "XRPLTxHash")
        xrpl_hash.text = payment_data.get('xrpl_tx_hash')
        
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
            xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.08",
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
        
        # Entry
        ntry = etree.SubElement(ntfctn_item, "Ntry")
        amt = etree.SubElement(ntry, "Amt")
        amt.set("Ccy", payment_data.get('currency', 'XRP'))
        amt.text = f"{payment_data.get('amount'):.2f}"
        
        cdt_dbt_ind = etree.SubElement(ntry, "CdtDbtInd")
        cdt_dbt_ind.text = "CRDT"  # Credit
        
        sts = etree.SubElement(ntry, "Sts")
        sts.text = "BOOK"  # Booked
        
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
    
    def generate_camt053(self, statement_data: Dict[str, Any]) -> str:
        """
        Generate camt.053.001.08 - BankToCustomerStatement (simplified)
        
        Args:
            statement_data: Dict containing:
                - account_id: str
                - account_name: str
                - statement_id: str
                - from_date: datetime
                - to_date: datetime
                - transactions: List[Dict] (payment_data dicts)
                
        Returns:
            XML string
        """
        root = etree.Element(
            "Document",
            xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08",
            nsmap={None: "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08"}
        )
        
        # BkToCstmrStmt
        stmt = etree.SubElement(root, "BkToCstmrStmt")
        
        # Group Header
        grp_hdr = etree.SubElement(stmt, "GrpHdr")
        msg_id = etree.SubElement(grp_hdr, "MsgId")
        msg_id.text = statement_data.get('statement_id', str(uuid.uuid4()))
        
        cre_dt_tm = etree.SubElement(grp_hdr, "CreDtTm")
        cre_dt_tm.text = self.format_datetime()
        
        # Statement
        stmt_item = etree.SubElement(stmt, "Stmt")
        stmt_id = etree.SubElement(stmt_item, "Id")
        stmt_id.text = statement_data.get('statement_id', str(uuid.uuid4()))
        
        # Account
        acct = etree.SubElement(stmt_item, "Acct")
        acct_id = etree.SubElement(acct, "Id")
        acct_othr = etree.SubElement(acct_id, "Othr")
        acct_othr_id = etree.SubElement(acct_othr, "Id")
        acct_othr_id.text = statement_data.get('account_id')
        
        # Balance (simplified - just showing final balance)
        bal = etree.SubElement(stmt_item, "Bal")
        tp = etree.SubElement(bal, "Tp")
        cd_or_prtry = etree.SubElement(tp, "CdOrPrtry")
        cd = etree.SubElement(cd_or_prtry, "Cd")
        cd.text = "CLBD"  # Closing Booked
        
        amt = etree.SubElement(bal, "Amt")
        amt.set("Ccy", "XRP")
        amt.text = "0.00"  # Placeholder
        
        cdt_dbt_ind = etree.SubElement(bal, "CdtDbtInd")
        cdt_dbt_ind.text = "CRDT"
        
        dt = etree.SubElement(bal, "Dt")
        dt_dt = etree.SubElement(dt, "Dt")
        dt_dt.text = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Transactions
        transactions = statement_data.get('transactions', [])
        for tx in transactions:
            ntry = etree.SubElement(stmt_item, "Ntry")
            
            ntry_amt = etree.SubElement(ntry, "Amt")
            ntry_amt.set("Ccy", tx.get('currency', 'XRP'))
            ntry_amt.text = f"{tx.get('amount'):.2f}"
            
            ntry_cdt_dbt = etree.SubElement(ntry, "CdtDbtInd")
            ntry_cdt_dbt.text = "CRDT"
            
            ntry_sts = etree.SubElement(ntry, "Sts")
            ntry_sts.text = "BOOK"
        
        return etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        ).decode('utf-8')
