import uuid
from decimal import Decimal
from typing import List, Dict, Any

class BulkPayoutCMSModule:
    def __init__(self, ledger_engine, corporate_operative_account: str):
        self.ledger = ledger_engine
        self.operative_account = corporate_operative_account

    def npci_synchronous_penny_drop(self, ifsc: str, account_no: str, expected_name: str) -> Dict[str, Any]:
        """Simulates real-time Name & IFSC check via NPCI Switch"""
        # Dormant/Invalid test condition
        if account_no.endswith("00"):
            return {"is_active": False, "match_percentage": 0.0, "status": "ACCOUNT_DORMANT"}
        
        # Simulates 95% string fuzzy match
        return {
            "is_active": True,
            "match_percentage": 94.8,
            "registered_title": expected_name.upper(),
            "status": "ACCOUNT_ACTIVE_VERIFIED"
        }

    def dispatch_single_payout(self, beneficiary_name: str, account_no: str, ifsc: str, amount: Decimal, enforce_penny_drop: bool = True) -> Dict[str, Any]:
        # Step 1: Inline Validation
        if enforce_penny_drop:
            check = self.npci_synchronous_penny_drop(ifsc, account_no, beneficiary_name)
            if not check["is_active"] or check["match_percentage"] < 75.0:
                return {
                    "status": "REJECTED_PRE_CLEARING",
                    "reason": f"Penny-drop validation failed: {check['status']}",
                    "beneficiary": beneficiary_name
                }

        # Step 2: Intelligent Rail Routing Logic
        # RTGS for ticket size >= 5,00,000 INR; IMPS for sub-5 Lakh instantaneous payouts
        clearing_rail = "RTGS" if amount >= Decimal("500000.00") else "IMPS"
        generated_utr = f"YESBR52026{uuid.uuid4().hex[:10].upper()}"

        # Step 3: Double-Entry Posting
        # Debit: Accounts Payable (Liability reduces)
        # Credit: Operative Current Account (Bank Asset reduces)
        entry_id = self.ledger.post_balanced_transaction(
            utr=generated_utr,
            narration=f"Bulk Payout to {beneficiary_name} via {clearing_rail}",
            dr_account="LIAB_ACCOUNTS_PAYABLE",
            cr_account=self.operative_account,
            amount=amount
        )

        return {
            "status": "SETTLED_STP",
            "utr": generated_utr,
            "rail": clearing_rail,
            "beneficiary": beneficiary_name,
            "amount": float(amount),
            "journal_entry_id": entry_id
        }