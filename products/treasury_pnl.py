from typing import List, Dict, Any
from datetime import datetime

class TreasuryPnLEngine:
    def __init__(self):
        # Double-entry transaction ledger
        self.ledger: List[Dict[str, Any]] = []

    def record_revenue(self, product: str, amount: float, reference_id: str):
        self.ledger.append({
            "timestamp": datetime.utcnow().isoformat(),
            "product": product,
            "type": "REVENUE",
            "amount": amount,
            "reference_id": reference_id
        })

    def record_cost(self, product: str, amount: float, reference_id: str):
        self.ledger.append({
            "timestamp": datetime.utcnow().isoformat(),
            "product": product,
            "type": "EXPENSE",
            "amount": amount,
            "reference_id": reference_id
        })

    def compute_product_pnl(self) -> Dict[str, Any]:
        pnl = {
            "ESCROW": {"revenue": 0.0, "cost": 0.0, "net_pnl": 0.0, "margin_percent": 0.0},
            "BULK_PAYOUT": {"revenue": 0.0, "cost": 0.0, "net_pnl": 0.0, "margin_percent": 0.0},
            "RECEIVABLES": {"revenue": 0.0, "cost": 0.0, "net_pnl": 0.0, "margin_percent": 0.0},
            "FX_REMITTANCE": {"revenue": 0.0, "cost": 0.0, "net_pnl": 0.0, "margin_percent": 0.0},
            "LIQUIDITY_SWEEP": {"revenue": 0.0, "cost": 0.0, "net_pnl": 0.0, "margin_percent": 0.0}
        }
        for entry in self.ledger:
            prod = entry["product"]
            if prod in pnl:
                if entry["type"] == "REVENUE":
                    pnl[prod]["revenue"] += entry["amount"]
                elif entry["type"] == "EXPENSE":
                    pnl[prod]["cost"] += entry["amount"]

        total_rev = 0.0
        total_cost = 0.0
        for prod, stats in pnl.items():
            net = stats["revenue"] - stats["cost"]
            stats["net_pnl"] = round(net, 2)
            stats["margin_percent"] = round((net / stats["revenue"] * 100), 2) if stats["revenue"] > 0 else 0.0
            total_rev += stats["revenue"]
            total_cost += stats["cost"]

        return {
            "company_total_revenue": round(total_rev, 2),
            "company_total_expenses": round(total_cost, 2),
            "company_net_profit": round(total_rev - total_cost, 2),
            "product_breakdown": pnl
        }
