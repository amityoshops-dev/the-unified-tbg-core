import uuid
from decimal import Decimal

class BulkDisbursementService:
    def __init__(self, ledger: DoubleEntryEngine, operating_account_id: str):
        self.ledger = ledger
        self.operating_account_id = operating_account_id

    def mock_npci_penny_drop(self, ifsc: str, account_no: str) -> dict:
        """Hits synchronous verification switch to check beneficiary status"""
        if account_no.endswith("00"): # Test failure case
            return {"active": False, "name_match_score": 0.0, "registered_name": "UNKNOWN"}
        return {"active": True, "name_match_score": 94.5, "registered_name": "VERIFIED BENEFICIARY"}

    def dispatch_payment(self, beneficiary_name: str, ifsc: str, account_no: str, amount: Decimal, enforce_penny_drop: bool = True):
        # Pre-execution validation
        if enforce_penny_drop:
            validation = self.mock_npci_penny_drop(ifsc, account_no)
            if not validation["active"] or validation["name_match_score"] < 75.0:
                return {
                    "status": "REJECTED_AT_GATEWAY",
                    "reason": "Penny-Drop failed: Beneficiary inactive or name match under threshold."
                }

        # Select clearing rail
        clearing_rail = "RTGS" if amount >= Decimal("500000.00") else "IMPS"
        assigned_utr = f"YESBR52026{uuid.uuid4().hex[:10].upper()}"

        # Post transaction to ledger
        self.ledger.post_balanced_transaction(
            utr=assigned_utr,
            narration=f"Bulk Payout to {beneficiary_name} via {clearing_rail}",
            debit_acc_id="LIAB_ACCOUNTS_PAYABLE",
            credit_acc_id=self.operating_account_id,
            amount=amount
        )

        return {
            "status": "SUCCESS_STP",
            "utr": assigned_utr,
            "rail": clearing_rail,
            "amount": float(amount),
            "beneficiary": beneficiary_name
        }