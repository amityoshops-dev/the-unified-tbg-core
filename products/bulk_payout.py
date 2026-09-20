import uuid
from typing import List, Dict, Any

class BulkPayoutEngine:
    def __init__(self):
        self.batches: Dict[str, Dict[str, Any]] = {}

    def process_batch(self, batch_id: str, debit_account: str, items: List[dict]):
        if batch_id in self.batches:
            return {"status": "CACHED_BATCH", "batch": self.batches[batch_id]}

        processed_items = []
        total_debit = 0.0
        total_fees = 0.0

        for item in items:
            payout_fee = 5.00  # ₹5.00 transaction fee per payout line item
            amount = float(item["amount"])
            total_debit += (amount + payout_fee)
            total_fees += payout_fee
            processed_items.append({
                "item_id": item.get("item_id", f"ITEM_{uuid.uuid4().hex[:6].upper()}"),
                "beneficiary_iban_acc": item["account_number"],
                "ifsc": item["ifsc"],
                "amount": amount,
                "fee": payout_fee,
                "utr": f"UTR{uuid.uuid4().hex[:10].upper()}",
                "status": "PROCESSED"
            })

        batch_record = {
            "batch_id": batch_id,
            "debit_account": debit_account,
            "line_count": len(processed_items),
            "total_principal": total_debit - total_fees,
            "total_fees_collected": total_fees,
            "net_debit": total_debit,
            "status": "SETTLED",
            "items": processed_items
        }
        self.batches[batch_id] = batch_record
        return {"status": "SETTLED", "batch": batch_record}
