from typing import Dict, List
import uuid

class LiquiditySweepEngine:
    def __init__(self):
        self.master_pool_balance = 50000000.0  # Master Operating Account
        self.va_accounts: Dict[str, float] = {
            "VA_PUNE_BRANCH": 1250000.0,
            "VA_MUMBAI_BRANCH": 3400000.0,
            "VA_COLLECTIONS": 850000.0
        }

    def execute_auto_sweep(self, threshold: float = 500000.0):
        sweep_records = []
        for va_num, balance in list(self.va_accounts.items()):
            if balance > threshold:
                excess = balance - threshold
                self.va_accounts[va_num] -= excess
                self.master_pool_balance += excess
                sweep_records.append({
                    "sweep_id": f"SWP_{uuid.uuid4().hex[:8].upper()}",
                    "from_va": va_num,
                    "to_pool": "MASTER_POOL_01",
                    "amount_swept": excess,
                    "remaining_va_balance": threshold,
                    "status": "SWEEP_COMPLETED"
                })
        return {
            "total_swept": sum(r["amount_swept"] for r in sweep_records),
            "master_pool_balance": self.master_pool_balance,
            "sweeps": sweep_records
        }
