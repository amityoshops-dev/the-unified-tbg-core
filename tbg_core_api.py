from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid, os
from datetime import datetime, timezone

app = FastAPI(title="TBG-CORE API", version="1.0.0", description="Institutional Payment & Ledger Orchestration Workbench â€” simulation/sandbox API.")

TXNS = {}

class RouteRequest(BaseModel):
    business_requirement: str
    amount: float = 0
    currency: str = "INR"

class SimRequest(RouteRequest):
    rail: Optional[str] = None

def route(req: RouteRequest):
    x=req.business_requirement.lower()
    if any(k in x for k in ["emi","mandate","recurring","monthly debit"]): intent, rail="EMI_COLLECTION","NACH"
    elif any(k in x for k in ["bill","electricity","water","bbps"]): intent, rail="BILL_PAYMENT","BBPS"
    elif any(k in x for k in ["escrow","hold funds","release"]): intent, rail="CONTROLLED_FUNDS","ESCROW"
    elif any(k in x for k in ["cross border","fx","usd","eur","foreign"]): intent, rail="CROSS_BORDER","FX"
    elif req.amount >= 200000: intent, rail="HIGH_VALUE_TRANSFER","RTGS"
    else: intent, rail="DOMESTIC_TRANSFER","NEFT"
    return intent, rail

@app.get("/health")
def health():
    return {"status":"ok","service":"TBG-CORE API","mode":"simulation","time":datetime.now(timezone.utc).isoformat()}

@app.post("/v1/route")
def route_requirement(req: RouteRequest, x_api_key: Optional[str]=Header(default=None)):
    intent, rail=route(req)
    return {"intent":intent,"selected_rail":rail,"status":"ROUTED","mode":"simulation"}

@app.post("/v1/simulate")
def simulate(req: SimRequest, x_api_key: Optional[str]=Header(default=None)):
    intent, selected=route(req)
    rail=req.rail or selected
    tid="TBG-"+uuid.uuid4().hex[:12].upper()
    result={
        "transaction_id":tid,
        "status":"SIMULATED_SUCCESS",
        "intent":intent,
        "rail":rail,
        "amount":req.amount,
        "currency":req.currency,
        "lifecycle":[
            "REQUIREMENT_CAPTURED",
            "NORMALIZED",
            "AI_RULES_INTERPRETATION",
            "INTENT_CLASSIFIED",
            "CANDIDATE_RAIL_DISCOVERY",
            "RAIL_SELECTED",
            "ELIGIBILITY_VALIDATED",
            "POLICY_CHECKED",
            "PARTY_VALIDATED",
            "IDEMPOTENCY_CHECKED",
            "RISK_LIMITS_CHECKED",
            "LIQUIDITY_CHECKED",
            "TXN_INITIATED",
            "MESSAGE_CONSTRUCTED",
            "RAIL_ADAPTER_SUBMITTED",
            "PROVIDER_ACKNOWLEDGED",
            "STATE_TRANSITIONED",
            "LEDGER_POSTED",
            "POOL_RESERVED",
            "SETTLEMENT_SIMULATED",
            "RECONCILED",
            "EXCEPTION_RETRY_CHECKED",
            "COMPLETE",
            "AUDITED",
            "METRICS_RECORDED"
        ]
    }
    TXNS[tid]=result
    return result

@app.get("/v1/transactions/{transaction_id}")
def get_transaction(transaction_id: str):
    if transaction_id not in TXNS:
        raise HTTPException(status_code=404, detail="Transaction not found in this demo instance")
    return TXNS[transaction_id]
