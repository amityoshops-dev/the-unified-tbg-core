import re
from decimal import Decimal
from typing import Dict, Any
from pydantic import BaseModel, field_validator

class RERAMilestoneReleaseRequest(BaseModel):
    project_registration_no: str
    architect_cert_pct: float    # Form 1
    engineer_cert_pct: float     # Form 2
    ca_claim_amount_inr: Decimal # Form 3
    ca_udin: str                 # Practicing CA UDIN

    @field_validator("ca_udin")
    def validate_udin_format(cls, val: str) -> str:
        # Standard ICAI UDIN Format: 2-digit Year (e.g. '26') + 6-digit Membership + 10 Alphanumeric characters
        if not re.match(r"^26\d{6}[A-Z0-9]{10}$", val):
            raise ValueError("ERR_INVALID_ICAI_UDIN_AUTHENTICATION_STRING")
        return val

class RERAEscrowModule:
    def __init__(self, ledger_engine, acc1_collection: str, acc2_separate_escrow: str, acc3_operative: str):
        self.ledger = ledger_engine
        self.acc1 = acc1_collection       # 100% Inflow, strictly Zero-Debit
        self.acc2 = acc2_separate_escrow   # 70% Construction & Land Escrow
        self.acc3 = acc3_operative         # 30% Free Operational Account

    def process_allottee_flat_inflow(self, flat_van: str, allottee_name: str, amount: Decimal, booking_utr: str) -> Dict[str, Any]:
        # Step 1: Credit Account 1
        self.ledger.post_balanced_transaction(
            utr=f"{booking_utr}_INFLOW",
            narration=f"Flat Inflow from {allottee_name} ({flat_van})",
            dr_account=self.acc1,
            cr_account="LIAB_ALLOTTEE_ESCROW_HOLDING",
            amount=amount
        )

        # Step 2: Automated 70:30 Waterfall Partition
        amount_70 = (amount * Decimal("0.70")).quantize(Decimal("0.01"))
        amount_30 = amount - amount_70

        # Sweep 70% to Account 2 (Separate Escrow)
        self.ledger.post_balanced_transaction(
            utr=f"{booking_utr}_SWEEP_70",
            narration=f"RERA 70% Construction Split - Unit {flat_van}",
            dr_account=self.acc2,
            cr_account=self.acc1,
            amount=amount_70
        )

        # Sweep 30% to Account 3 (Operative)
        self.ledger.post_balanced_transaction(
            utr=f"{booking_utr}_SWEEP_30",
            narration=f"RERA 30% Operative Split - Unit {flat_van}",
            dr_account=self.acc3,
            cr_account=self.acc1,
            amount=amount_30
        )

        return {
            "status": "WATERFALL_SPLIT_COMPLETE",
            "account_1_balance": 0.00,
            "account_2_credited_70": float(amount_70),
            "account_3_credited_30": float(amount_30),
            "flat_van": flat_van
        }

    def execute_verified_milestone_release(self, claim: RERAMilestoneReleaseRequest) -> Dict[str, Any]:
        # Rule: Architect and Engineer physical completion rates cannot diverge by > 5%
        if abs(claim.architect_cert_pct - claim.engineer_cert_pct) > 5.0:
            raise ValueError("ERR_RERA_SITE_DISCREPANCY: Architect & Engineer certificates diverge > 5.0%")

        release_utr = f"YESB_RERA_REL_{claim.ca_udin[:8]}"

        # Move cleared funds from Account 2 (Separate Escrow) to Account 3 (Operative)
        entry_id = self.ledger.post_balanced_transaction(
            utr=release_utr,
            narration=f"RERA Form 3 Milestone Release - UDIN {claim.ca_udin}",
            dr_account=self.acc3,
            cr_account=self.acc2,
            amount=claim.ca_claim_amount_inr
        )

        return {
            "status": "MILESTONE_RELEASED",
            "amount_released": float(claim.ca_claim_amount_inr),
            "udin_verified": claim.ca_udin,
            "journal_entry_id": entry_id
        }