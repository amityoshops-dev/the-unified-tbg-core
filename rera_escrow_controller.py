from decimal import Decimal
from pydantic import BaseModel, field_validator
import re

class RERACertificatePayload(BaseModel):
    project_id: str
    architect_completion_pct: float  # Form 1
    engineer_completion_pct: float   # Form 2
    ca_withdrawal_eligible_inr: Decimal # Form 3
    ca_udin: str                     # Must be 18 digits with valid prefix

    @field_validator("ca_udin")
    def validate_udin(cls, v):
        # Format: 2-digit Year (e.g. 26) + 6-digit ICAI Membership + 10 alphanumeric chars
        if not re.match(r"^26\d{6}[A-Z0-9]{10}$", v):
            raise ValueError("INVALID_ICAI_UDIN_AUTHENTICATION_STRING")
        return v

class RERAEscrowManager:
    def __init__(self, ledger: DoubleEntryEngine, acc1_id: str, acc2_id: str, acc3_id: str):
        self.ledger = ledger
        self.acc1_id = acc1_id # Designated Collection Account (100%)
        self.acc2_id = acc2_id # Separate Escrow Account (70%)
        self.acc3_id = acc3_id # Operative Account (30%)

    def handle_allottee_inflow(self, amount: Decimal, utr: str, flat_van: str):
        # Step 1: Inflow directly into Account 1
        self.ledger.post_balanced_transaction(
            utr=f"{utr}_COLL",
            narration=f"Allottee booking collection via {flat_van}",
            debit_acc_id=self.acc1_id,
            credit_acc_id="LIAB_ALLOTTEE_DEPOSITS",
            amount=amount
        )

        # Step 2: Automated End-of-Day/Real-Time Sweep (70:30 Rule)
        amount_70 = (amount * Decimal("0.70")).quantize(Decimal("0.01"))
        amount_30 = amount - amount_70

        # Sweep 70% to Account 2
        self.ledger.post_balanced_transaction(
            utr=f"{utr}_SWEEP_70",
            narration=f"RERA 70% mandatory project split for {flat_van}",
            debit_acc_id=self.acc2_id,
            credit_acc_id=self.acc1_id,
            amount=amount_70
        )

        # Sweep 30% to Account 3
        self.ledger.post_balanced_transaction(
            utr=f"{utr}_SWEEP_30",
            narration=f"RERA 30% operative split for {flat_van}",
            debit_acc_id=self.acc3_id,
            credit_acc_id=self.acc1_id,
            amount=amount_30
        )

    def release_milestone_funds(self, cert: RERACertificatePayload, release_utr: str):
        # Verification: Physical completion alignment
        if abs(cert.architect_completion_pct - cert.engineer_completion_pct) > 5.0:
            raise ValueError("SITE_DISCREPANCY: Architect and Engineer percentages diverge > 5.0%")

        # Post release from Account 2 to Account 3
        return self.ledger.post_balanced_transaction(
            utr=release_utr,
            narration=f"RERA Milestone Fund Release - Form 3 UDIN: {cert.ca_udin}",
            debit_acc_id=self.acc3_id,
            credit_acc_id=self.acc2_id,
            amount=cert.ca_withdrawal_eligible_inr
        )