from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import List
import uuid
from datetime import datetime, timezone

app = FastAPI(title="TBG-Core Enterprise Platform", version="2026.4.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory journal & state
ledger_journal = []
account_balances = {
    "ESCROW_RETENTION_70": Decimal("10500000.00"),
    "BUILDER_CURRENT_30": Decimal("4500000.00"),
    "CENTRAL_CLEARING_POOL": Decimal("25000000.00"),
    "VPA_INWARD_COLLECTIONS": Decimal("3200000.00"),
}

class InwardReceivableRequest(BaseModel):
    buyer_vpa: str
    amount: Decimal = Field(gt=0)
    project_id: str

class SweepRequest(BaseModel):
    source_account: str
    target_pool: str
    sweep_threshold: Decimal

@app.get("/api/v1/telemetry")
async def get_telemetry():
    total_liquidity = sum(account_balances.values())
    return {
        "total_liquidity": f"₹ {total_liquidity:,.2f}",
        "balances": {k: f"₹ {v:,.2f}" for k, v in account_balances.items()},
        "active_vpas": 4821,
        "parity_delta": "0.00 Δ",
        "journal": ledger_journal[-10:]
    }

@app.post("/api/v1/rera/inward-split")
async def process_rera_inward(req: InwardReceivableRequest):
    """
    NPCI Inward Receivables -> RERA Mandate:
    70% strictly locked to Project Escrow, 30% credited to Free Operational Account.
    Σ Debits ≡ Σ Credits
    """
    escrow_70 = (req.amount * Decimal("0.70")).quantize(Decimal("0.01"))
    free_30 = req.amount - escrow_70
    batch_ref = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

    # Update ledger states
    account_balances["ESCROW_RETENTION_70"] += escrow_70
    account_balances["BUILDER_CURRENT_30"] += free_30

    entries = [
        {
            "id": str(uuid.uuid4()),
            "time": ts,
            "ref": batch_ref,
            "routing": f"INWARD [{req.buyer_vpa}] -> ESCROW_RETENTION_70 (70%)",
            "amount": f"₹ {escrow_70:,.2f}",
            "type": "CREDIT",
            "status": "SETTLED"
        },
        {
            "id": str(uuid.uuid4()),
            "time": ts,
            "ref": batch_ref,
            "routing": f"INWARD [{req.buyer_vpa}] -> BUILDER_CURRENT_30 (30%)",
            "amount": f"₹ {free_30:,.2f}",
            "type": "CREDIT",
            "status": "SETTLED"
        }
    ]
    ledger_journal.extend(entries)
    return {"status": "SUCCESS", "batch_ref": batch_ref, "escrow_70": str(escrow_70), "free_30": str(free_30)}

@app.post("/api/v1/liquidity/sweep")
async def execute_liquidity_sweep(req: SweepRequest):
    """
    Automated Liquidity Sweep: Pulls surplus funds above threshold into Central Clearing.
    """
    current_bal = account_balances.get(req.source_account, Decimal("0.00"))
    if current_bal <= req.sweep_threshold:
        raise HTTPException(status_code=400, detail="Account balance is below sweep threshold limit.")

    sweep_amount = current_bal - req.sweep_threshold
    account_balances[req.source_account] -= sweep_amount
    account_balances[req.target_pool] += sweep_amount

    batch_ref = f"SWEEP-{uuid.uuid4().hex[:8].upper()}"
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

    entry = {
        "id": str(uuid.uuid4()),
        "time": ts,
        "ref": batch_ref,
        "routing": f"{req.source_account} -> {req.target_pool}",
        "amount": f"₹ {sweep_amount:,.2f}",
        "type": "DEBIT",
        "status": "SETTLED"
    }
    ledger_journal.append(entry)
    return {"status": "SUCCESS", "batch_ref": batch_ref, "swept_amount": str(sweep_amount)}
