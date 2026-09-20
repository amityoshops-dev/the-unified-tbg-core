from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid

class EscrowStatus(str, Enum):
    DRAFT = "DRAFT"
    FUNDED = "FUNDED"
    MILESTONE_MET = "MILESTONE_MET"
    TRUSTEE_APPROVED = "TRUSTEE_APPROVED"
    DISBURSED = "DISBURSED"
    DISPUTED = "DISPUTED"

class MilestoneCondition(BaseModel):
    milestone_id: str
    description: str
    target_amount: float = Field(gt=0)
    requires_trustee_approval: bool = True
    is_completed: bool = False

class DigitalEscrowContract(BaseModel):
    contract_id: str
    depositor_id: str
    beneficiary_id: str
    trustee_id: str
    virtual_account_no: str
    total_locked_amount: float
    current_balance: float
    status: EscrowStatus
    milestones: List[MilestoneCondition]
    approval_signatures: List[str] = []

class DigitalEscrowEngine:
    def __init__(self, db_client, payout_pipeline):
        self.db = db_client
        self.payout_pipeline = payout_pipeline

    def create_escrow_deal(self, depositor: str, beneficiary: str, trustee: str, amount: float, milestones: List[dict]):
        contract_id = f"ESC_{uuid.uuid4().hex[:8].upper()}"
        va_number = f"VA_{uuid.uuid4().hex[:10].upper()}"
        
        parsed_milestones = [MilestoneCondition(**m) for m in milestones]
        
        contract = DigitalEscrowContract(
            contract_id=contract_id,
            depositor_id=depositor,
            beneficiary_id=beneficiary,
            trustee_id=trustee,
            virtual_account_no=va_number,
            total_locked_amount=amount,
            current_balance=0.0,
            status=EscrowStatus.DRAFT,
            milestones=parsed_milestones
        )
        self.db.save_contract(contract.model_dump())
        return contract

    def deposit_funds_webhook(self, va_number: str, amount: float, bank_utr: str):
        """Simulates Castler receiving money into a designated nodal virtual account"""
        contract = self.db.get_by_virtual_account(va_number)
        contract["current_balance"] += amount
        if contract["current_balance"] >= contract["total_locked_amount"]:
            contract["status"] = EscrowStatus.FUNDED
        
        self.db.update_contract(contract["contract_id"], contract)
        return {"contract_id": contract["contract_id"], "status": contract["status"], "balance": contract["current_balance"]}

    async def sign_and_release_milestone(self, contract_id: str, milestone_id: str, trustee_signature: str):
        """Trustee sign-off + automated payout trigger"""
        contract = self.db.get_contract(contract_id)
        
        if contract["status"] not in [EscrowStatus.FUNDED, EscrowStatus.MILESTONE_MET]:
            raise ValueError("Escrow funds not locked or contract not in executable state")

        # Find target milestone
        milestone = next((m for m in contract["milestones"] if m["milestone_id"] == milestone_id), None)
        if not milestone:
            raise ValueError("Milestone not found")

        if contract["current_balance"] < milestone["target_amount"]:
            raise ValueError("Insufficient balance in escrow to disburse this milestone")

        # Record trustee multi-sig signature
        contract["approval_signatures"].append(f"{trustee_signature}_{datetime.utcnow().isoformat()}")
        milestone["is_completed"] = True

        # Trigger hardened payout pipeline with idempotency
        idempotency_key = f"IDEM_{contract_id}_{milestone_id}"
        payout_res = await self.payout_pipeline.execute_automated_payout(
            contract_id=contract_id,
            amount=milestone["target_amount"],
            beneficiary=contract["beneficiary_id"],
            idempotency_key=idempotency_key
        )

        contract["current_balance"] -= milestone["target_amount"]
        if contract["current_balance"] == 0:
            contract["status"] = EscrowStatus.DISBURSED

        self.db.update_contract(contract_id, contract)
        return {"payout": payout_res, "remaining_escrow_balance": contract["current_balance"]}