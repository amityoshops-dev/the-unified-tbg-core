import uuid
from typing import Dict, Any

class ReceivablesEngine:
    def __init__(self):
        self.invoices: Dict[str, Dict[str, Any]] = {}

    def raise_invoice(self, debtor_name: str, debtor_pan: str, amount: float, due_date: str, product_code: str):
        inv_id = f"INV_{uuid.uuid4().hex[:8].upper()}"
        assigned_va = f"VA_{debtor_pan[-4:]}_{uuid.uuid4().hex[:4].upper()}"
        record = {
            "invoice_id": inv_id,
            "debtor_name": debtor_name,
            "debtor_pan": debtor_pan,
            "virtual_collection_acc": assigned_va,
            "billed_amount": amount,
            "paid_amount": 0.0,
            "due_date": due_date,
            "product_code": product_code,
            "reconciliation_status": "UNPAID"
        }
        self.invoices[inv_id] = record
        return record

    def reconcile_collection(self, virtual_acc: str, received_amount: float):
        for inv in self.invoices.values():
            if inv["virtual_collection_acc"] == virtual_acc:
                inv["paid_amount"] += received_amount
                if inv["paid_amount"] >= inv["billed_amount"]:
                    inv["reconciliation_status"] = "RECONCILED"
                else:
                    inv["reconciliation_status"] = "PARTIALLY_PAID"
                return inv
        return None
