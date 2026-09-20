import uuid
from datetime import datetime
from typing import Dict, List, Any
from pydantic import BaseModel, Field

class MandateStatus:
    REGISTERED = "REGISTERED"
    PRESENTED = "PRESENTED"
    SETTLED = "SETTLED"
    REJECTED = "REJECTED"

class NACHClearingEngine:
    def __init__(self):
        self.mandates: Dict[str, Dict[str, Any]] = {}
        self.presentations: List[Dict[str, Any]] = []

    def register_enach_mandate(self, debtor_name: str, debtor_account: str, ifsc: str, max_amount: float, auth_mode: str):
        """Simulates NPCI e-Mandate onboarding via NetBanking / Debit Card"""
        umrn = f"UMRN{uuid.uuid4().hex[:16].upper()}"  # Unique Mandate Reference Number
        mandate = {
            "umrn": umrn,
            "debtor_name": debtor_name,
            "debtor_account": debtor_account,
            "ifsc": ifsc,
            "max_amount": max_amount,
            "auth_mode": auth_mode, # NET_BANKING, DEBIT_CARD, AADHAAR
            "status": MandateStatus.REGISTERED,
            "created_at": datetime.utcnow().isoformat()
        }
        self.mandates[umrn] = mandate
        return mandate

    def present_nach_debit(self, umrn: str, amount: float, settlement_date: str):
        """Presents a collection batch file to NPCI clearing house"""
        if umrn not in self.mandates:
            raise KeyError("Mandate UMRN not found")
        mandate = self.mandates[umrn]
        if amount > mandate["max_amount"]:
            raise ValueError(f"Debit amount ₹{amount} exceeds registered mandate limit ₹{mandate['max_amount']}")

        clearing_ref = f"ACH_CLR_{uuid.uuid4().hex[:10].upper()}"
        presentation = {
            "clearing_ref": clearing_ref,
            "umrn": umrn,
            "debtor_account": mandate["debtor_account"],
            "amount": amount,
            "settlement_date": settlement_date,
            "clearing_type": "NPCI_NACH_APBS",
            "status": MandateStatus.SETTLED
        }
        self.presentations.append(presentation)
        return presentation

    def generate_us_ach_batch_file(self, company_id: str, company_name: str, entries: List[dict]) -> str:
        """Generates standard NACHA format batch for US ACH clearing"""
        # Header Record Type 5
        header = f"5200{company_name[:16].ljust(16)}{company_id[:10].ljust(10)}PPDCHECKOUT   {datetime.now().strftime('%y%m%d')}{datetime.now().strftime('%y%m%d')}   1091000010000001\n"
        body = ""
        total_debit = 0.0
        for idx, entry in enumerate(entries, start=1):
            amt_cents = int(float(entry['amount']) * 100)
            total_debit += float(entry['amount'])
            # Entry Detail Record Type 6
            body += f"627{entry['routing_number'][:8]}{entry['routing_number'][8]}{entry['account_number'][:17].ljust(17)}{str(amt_cents).zfill(10)}{entry['individual_name'][:15].ljust(15)}  0000000001{str(idx).zfill(4)}\n"
        
        # Batch Control Record Type 8
        control = f"8200{str(len(entries)).zfill(6)}000000000000{str(int(total_debit * 100)).zfill(12)}00000000000000000000000000000001\n"
        return header + body + control
