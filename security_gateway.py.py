import hashlib
import hmac
from fastapi import HTTPException, Security, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

API_KEY_HEADER = APIKeyHeader(name="X-Escrow-API-Key", auto_error=True)
INTERNAL_SECRET = "tbg-core-vault-key-2026"

class AutoPayoutRequest(BaseModel):
    contract_id: str
    milestone_id: str
    beneficiary_account_id: str
    payout_amount: float = Field(gt=0, description="Amount must be positive")
    idempotency_key: str

    model_config = {"extra": "forbid"}  # Blocks Mass Assignment vulnerability

def verify_tenant_authorization(contract_id: str, caller_tenant_id: str, db_session):
    """Mitigates BOLA: Ensures caller actually controls this specific escrow account."""
    contract = db_session.get_contract(contract_id)
    if not contract or contract["tenant_id"] != caller_tenant_id:
        raise HTTPException(status_code=403, detail="Forbidden: Broken Object Level Authorization")
    return contract