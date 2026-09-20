import qrcode
from decimal import Decimal
from typing import Dict, Any

class ReceivablesCMSModule:
    def __init__(self, ledger_engine, master_corp_prefix: str = "YESB0941"):
        self.ledger = ledger_engine
        self.corp_prefix = master_corp_prefix
        # Mapping: { "VAN": { "dealer_id": "...", "dealer_name": "..." } }
        self.van_master_registry: Dict[str, Dict[str, str]] = {}

    def issue_dealer_van(self, dealer_code: str, dealer_name: str) -> str:
        van = f"{self.corp_prefix}{dealer_code.upper()}"
        self.van_master_registry[van] = {
            "dealer_code": dealer_code,
            "dealer_name": dealer_name
        }
        return van

    def generate_b2b_dynamic_invoice_qr(self, dealer_code: str, invoice_id: str, amount_inr: Decimal) -> Dict[str, Any]:
        """Constructs an NPCI-compliant B2B URI and encodes it as a QR"""
        vpa = f"yesb.{dealer_code.lower()}@yesbank"
        # tr: Transaction Reference locks to ERP Invoice Number
        # mc: 5065 (Electrical & Electronics Distributors)
        upi_uri = (
            f"upi://pay?pa={vpa}"
            f"&pn=HavellsNoidaManufacturing"
            f"&tr={invoice_id}"
            f"&am={amount_inr:.2f}"
            f"&cu=INR"
            f"&mc=5065"
        )
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(upi_uri)
        qr.make(fit=True)
        return {
            "vpa": vpa,
            "invoice_id": invoice_id,
            "amount": float(amount_inr),
            "upi_uri": upi_uri,
            "van": f"{self.corp_prefix}{dealer_code.upper()}"
        }

    def process_incoming_collection(self, van: str, amount: Decimal, clearing_utr: str, invoice_id: str) -> Dict[str, Any]:
        if van not in self.van_master_registry:
            raise ValueError(f"ERR_VAN_NOT_FOUND: Virtual account {van} is unassigned.")

        dealer_meta = self.van_master_registry[van]
        
        # Real-Time Double-Entry Posting:
        # Debit: Bank Transit / Clearing Asset
        # Credit: Corporate Accounts Receivable (Dealer Sub-Ledger)
        entry_id = self.ledger.post_balanced_transaction(
            utr=clearing_utr,
            narration=f"STP B2B Receipt - Invoice {invoice_id} via {van}",
            dr_account="ASSET_YESB_CLEARING_POOL",
            cr_account="LIAB_DEALER_RECEIVABLES",
            amount=amount
        )

        # Structure Webhook Callback for Client ERP
        erp_callback_payload = {
            "event": "PAYMENT_COLLECTED_STP",
            "invoice_id": invoice_id,
            "dealer_code": dealer_meta["dealer_code"],
            "dealer_name": dealer_meta["dealer_name"],
            "cleared_amount": float(amount),
            "bank_utr": clearing_utr,
            "ledger_entry_id": entry_id,
            "credit_limit_action": "RESTORE_IMMEDIATE"
        }
        return erp_callback_payload