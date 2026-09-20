import uuid
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class MilestoneItem(BaseModel):
    milestone_id: str
    description: str
    target_amount: float = Field(gt=0)
    is_completed: bool = False

class EscrowContract(BaseModel):
    contract_id: str
    depositor: str
    beneficiary: str
    trustee: str
    nodal_virtual_account: str
    total_amount: float
    current_balance: float = 0.0
    status: str = "DRAFT"
    milestones: List[MilestoneItem]
    signatures: List[str] = []

class EscrowEngine:
    def __init__(self, payout_pipeline):
        self.pipeline = payout_pipeline
        self.contracts: Dict[str, EscrowContract] = {}

    def create_contract(self, depositor: str, beneficiary: str, trustee: str, total_amount: float, milestones: list):
        cid = f"ESC_{uuid.uuid4().hex[:6].upper()}"
        va = f"VA_{uuid.uuid4().hex[:8].upper()}"
        items = [MilestoneItem(**m) for m in milestones]
        contract = EscrowContract(
            contract_id=cid,
            depositor=depositor,
            beneficiary=beneficiary,
            trustee=trustee,
            nodal_virtual_account=va,
            total_amount=total_amount,
            current_balance=0.0,
            milestones=items
        )
        self.contracts[cid] = contract
        return contract

    def deposit_inflow(self, va: str, amount: float):
        for contract in self.contracts.values():
            if contract.nodal_virtual_account == va:
                contract.current_balance += amount
                if contract.current_balance >= contract.total_amount:
                    contract.status = "FULLY_FUNDED"
                else:
                    contract.status = "PARTIALLY_FUNDED"
                return contract
        raise KeyError("Virtual Account not found")

    async def approve_and_release(self, contract_id: str, milestone_id: str, trustee_key: str):
        if contract_id not in self.contracts:
            raise KeyError("Contract not found")
        contract = self.contracts[contract_id]

        if contract.current_balance <= 0:
            raise ValueError("No locked balance available")

        milestone = next((m for m in contract.milestones if m.milestone_id == milestone_id), None)
        if not milestone:
            raise ValueError("Milestone not found")
        if milestone.is_completed:
            raise ValueError("Milestone already settled")
        if contract.current_balance < milestone.target_amount:
            raise ValueError("Insufficient balance for this milestone amount")

        # Digital Signature / Audit Stamp
        contract.signatures.append(f"{trustee_key}:{datetime.utcnow().isoformat()}")
        milestone.is_completed = True

        # Hardened Automated Disbursal
        idempotency_key = f"IDEM_{contract_id}_{milestone_id}"
        payout_res = await self.pipeline.execute_automated_payout(
            contract_id=contract_id,
            amount=milestone.target_amount,
            beneficiary=contract.beneficiary,
            idempotency_key=idempotency_key
        )

        contract.current_balance -= milestone.target_amount
        if contract.current_balance == 0:
            contract.status = "COMPLETED"

        return {"payout_receipt": payout_res, "escrow_contract": contract}
