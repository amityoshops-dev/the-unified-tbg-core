"""
TBG-CORE Engine API (FastAPI)
=============================
A standalone REST API exposing the same 9 simulated rails as the
Streamlit dashboard (tbg_core_simulator.py), so they can be called
live from Postman, curl, or any HTTP client.

SIMULATION ONLY: no real bank, NPCI, RTGS/IMPS, SWIFT, or Account
Aggregator infrastructure is connected. All balances, mandates and
FX rates are generated in-process, in memory, per running instance.

--------------------------------------------------------------------------
RUN LOCALLY
--------------------------------------------------------------------------
    pip install -r requirements_api.txt
    uvicorn tbg_core_api:app --reload --port 8000

    Swagger UI   -> http://localhost:8000/docs
    OpenAPI spec -> http://localhost:8000/openapi.json

--------------------------------------------------------------------------
USE FROM POSTMAN (two options)
--------------------------------------------------------------------------
    A) Postman -> Import -> Link -> paste your /openapi.json URL.
       Postman auto-generates a full collection with every endpoint.
    B) Import the included TBG-CORE.postman_collection.json directly,
       then set the collection variable `base_url` to your server URL.

--------------------------------------------------------------------------
DEPLOY ON RENDER (separate Web Service from the Streamlit app)
--------------------------------------------------------------------------
    Build Command: pip install -r requirements_api.txt
    Start Command: uvicorn tbg_core_api:app --host 0.0.0.0 --port $PORT
--------------------------------------------------------------------------
"""

import os
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    import anthropic
    ANTHROPIC_SDK_AVAILABLE = True
except ImportError:
    ANTHROPIC_SDK_AVAILABLE = False

DEFAULT_MODEL = "claude-sonnet-5"

app = FastAPI(
    title="TBG-CORE Engine API (Simulation)",
    description=(
        "Simulated payment/treasury orchestration engine \u2014 9 rails, one in-memory ledger. "
        "SIMULATION ONLY: not connected to any real bank, NPCI, RTGS/IMPS, SWIFT or AA rail."
    ),
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ============================================================================
# IN-MEMORY LEDGER + TRANSACTION LOG (single-process demo state)
# ============================================================================

class Ledger:
    def __init__(self):
        self.accounts = {
            "escrow_trust_pool": 14_920_000.0,
            "treasury_float": 7_349_150.0,
            "atomic_pool_2pc": 4_975_000.0,
            "nostro_fx_mirror_usd": 410.00,
        }

    def adjust(self, account, delta):
        self.accounts[account] = self.accounts.get(account, 0) + delta
        return self.accounts[account]

    def transfer(self, src, dst, amount):
        if self.accounts.get(src, 0) < amount:
            raise ValueError(
                f"Insufficient balance in {src}: available {self.accounts.get(src,0):.2f}, required {amount:.2f}"
            )
        self.accounts[src] -= amount
        self.accounts[dst] = self.accounts.get(dst, 0) + amount


ledger = Ledger()
MANDATES: Dict[str, Dict[str, Any]] = {}
TRANSACTIONS: List[Dict[str, Any]] = []
STARTED_AT = datetime.utcnow()


def log_txn(service, action, amount, currency, status, detail=""):
    txn = {
        "id": f"TBG-{uuid.uuid4().hex[:10].upper()}",
        "time": datetime.utcnow().isoformat() + "Z",
        "service": service, "action": action,
        "amount": amount, "currency": currency,
        "status": status, "detail": detail,
    }
    TRANSACTIONS.insert(0, txn)
    return txn


# ============================================================================
# RAIL LOGIC (mirrors tbg_core_simulator.py)
# ============================================================================

def do_escrow_lock(amount):
    ledger.adjust("escrow_trust_pool", +amount)
    return log_txn("Escrow Multi-Sig", "Lock", amount, "INR", "LOCKED", "Funds held pending 2-of-3 signoff")


def do_escrow_release(amount, sig_count):
    if sig_count < 2:
        raise ValueError(f"Release blocked: only {sig_count}/3 signatures collected (need >= 2).")
    ledger.adjust("escrow_trust_pool", -amount)
    return log_txn("Escrow Multi-Sig", "Release", amount, "INR", "RELEASED", f"{sig_count}/3 signatures verified")


def do_2pc(amount, force_timeout=False):
    ledger.transfer("treasury_float", "atomic_pool_2pc", amount)
    rolled_back = force_timeout or (random.random() < 0.08)
    if rolled_back:
        ledger.transfer("atomic_pool_2pc", "treasury_float", amount)
        return log_txn("2PC Bulk Disbursals", "Rollback", amount, "INR", "ROLLED BACK", "Simulated upstream bank timeout")
    ledger.adjust("atomic_pool_2pc", -amount)
    return log_txn("2PC Bulk Disbursals", "Payout", amount, "INR", "SETTLED", "IMPS/RTGS commit acknowledged")


def do_va_collect(amount, invoice_id):
    van = f"VAN{random.randint(100000,999999)}"
    ledger.adjust("treasury_float", +amount)
    return log_txn("Virtual Accounts (CMS)", "Collect Credit", amount, "INR", "RECONCILED", f"{van} matched to {invoice_id}")


def do_enach_register(amount, freq_days, start_date):
    mandate_id = f"MNDT-{uuid.uuid4().hex[:8].upper()}"
    MANDATES[mandate_id] = {"amount": amount, "freq_days": freq_days, "next_due": start_date}
    log_txn("e-NACH Standing Orders", "Register Mandate", amount, "INR", "ACTIVE", f"{mandate_id} every {freq_days}d")
    return mandate_id


def do_enach_trigger(mandate_id):
    if mandate_id not in MANDATES:
        raise ValueError(f"Unknown mandate_id '{mandate_id}'")
    m = MANDATES[mandate_id]
    ledger.adjust("treasury_float", +m["amount"])
    m["next_due"] = m["next_due"] + timedelta(days=m["freq_days"])
    return log_txn("e-NACH Standing Orders", "Trigger Pull", m["amount"], "INR", "DEBITED",
                    f"{mandate_id} next due {m['next_due'].date()}")


def do_sweep():
    sub_balances = [random.randint(8_000, 30_000) for _ in range(4)]
    total = sum(sub_balances)
    ledger.adjust("treasury_float", +total)
    return log_txn("Liquidity Sweep Pool", "Sweep Float", total, "INR", "SWEPT", f"4 accounts: {sub_balances}"), sub_balances


def current_fx_rate():
    return round(83.10 + random.uniform(-0.35, 0.35), 4)


def do_fx(amount_usd):
    rate = current_fx_rate()
    inr_needed = amount_usd * rate
    if ledger.accounts["treasury_float"] < inr_needed:
        raise ValueError("Insufficient Treasury Float for FX leg")
    ledger.accounts["treasury_float"] -= inr_needed
    ledger.accounts["nostro_fx_mirror_usd"] += amount_usd
    ref = f"MT103-{uuid.uuid4().hex[:8].upper()}"
    txn = log_txn("Cross-Border FX Nostro", "Dispatch Remit", amount_usd, "USD", "SETTLED", f"{ref} @ {rate}")
    return txn, rate, ref


def do_aa_pull(purpose):
    snapshot = {
        "avg_monthly_inflow": random.randint(60_000, 220_000),
        "existing_emi_obligations": random.randint(5_000, 40_000),
        "avg_eod_balance_90d": random.randint(15_000, 150_000),
        "bounce_rate_90d": random.choice([0, 0, 1, 2]),
    }
    txn = log_txn("Account Aggregator Consent Flow", "Data Pull", 0, "INR", "DATA_PULLED", purpose)
    return txn, snapshot


def do_split(gross, commission_pct):
    commission = round(gross * commission_pct / 100, 2)
    payout = round(gross - commission, 2)
    ledger.adjust("treasury_float", +commission)
    ledger.adjust("escrow_trust_pool", +payout)
    txn = log_txn("Marketplace Split", "Instant Split", gross, "INR", "SETTLED",
                   f"commission {commission} payout {payout}")
    return txn, commission, payout


def do_gst(amount):
    gst = round(amount * 0.18, 2)
    ledger.adjust("escrow_trust_pool", +gst)
    txn = log_txn("Statutory Tax Escrow", "Sequester GST", gst, "INR", "SEQUESTERED", f"18% of {amount}")
    return txn, gst


SERVICE_DEFS = [
    {"id": "escrow", "name": "Escrow Multi-Sig", "tag": "2-of-3 Safe",
     "keywords": ["escrow", "milestone", "multi-sig", "multisig", "trust", "custody"]},
    {"id": "2pc", "name": "2PC Bulk Disbursals", "tag": "IMPS/RTGS",
     "keywords": ["disbursal", "disburse", "payout", "2pc", "bulk payment", "rtgs", "imps"]},
    {"id": "va", "name": "Virtual Accounts (CMS)", "tag": "Smart VAN",
     "keywords": ["virtual account", "van", "collection", "invoice", "credit"]},
    {"id": "enach", "name": "e-NACH Standing Orders", "tag": "NPCI Mandate",
     "keywords": ["nach", "mandate", "emi", "recurring", "standing order", "debit", "loan"]},
    {"id": "sweep", "name": "Liquidity Sweep Pool", "tag": "ZBA/TBA",
     "keywords": ["sweep", "liquidity", "zba", "concentration", "eod"]},
    {"id": "fx", "name": "Cross-Border FX Nostro", "tag": "SWIFT MT103",
     "keywords": ["fx", "forex", "cross-border", "nostro", "swift", "remittance", "currency"]},
    {"id": "aa", "name": "Account Aggregator Consent Flow", "tag": "Consent Rail",
     "keywords": ["account aggregator", "consent", "underwriting", "data pull"]},
    {"id": "split", "name": "Marketplace Split", "tag": "Instant Split",
     "keywords": ["marketplace", "split", "commission", "seller payout"]},
    {"id": "gst", "name": "Statutory Tax Escrow", "tag": "PA/PG Safe",
     "keywords": ["gst", "tax", "statutory", "liability", "compliance"]},
]
SERVICE_BY_ID = {s["id"]: s for s in SERVICE_DEFS}

# ============================================================================
# REQUEST MODELS
# ============================================================================

class EscrowRequest(BaseModel):
    action: str = Field(..., pattern="^(lock|release)$")
    amount: float = Field(..., gt=0)
    milestone_id: Optional[str] = None
    signatures: int = 0


class DisbursalRequest(BaseModel):
    amount: float = Field(..., gt=0)
    beneficiary_vpa: Optional[str] = None
    force_timeout: bool = False


class VARequest(BaseModel):
    amount: float = Field(..., gt=0)
    invoice_id: str = "INV-0000"


class ENachRequest(BaseModel):
    action: str = Field(..., pattern="^(register|trigger)$")
    amount: Optional[float] = None
    frequency_days: int = 30
    mandate_id: Optional[str] = None


class FXRequest(BaseModel):
    amount_usd: float = Field(..., gt=0)


class AARequest(BaseModel):
    consent_granted: bool
    purpose: str = "underwriting"


class SplitRequest(BaseModel):
    gross_amount: float = Field(..., gt=0)
    commission_pct: float = 10


class GSTRequest(BaseModel):
    transaction_amount: float = Field(..., gt=0)


class RouteRequest(BaseModel):
    query: str


class ExecuteRequest(BaseModel):
    service_id: str
    params: Dict[str, Any] = {}


# ============================================================================
# GENERAL ENDPOINTS
# ============================================================================

@app.get("/", tags=["General"])
def root():
    return {
        "service": "TBG-CORE Engine API",
        "mode": "SIMULATION",
        "docs": "/docs",
        "catalog": "/api/v1/services/catalog",
    }


@app.get("/api/v1/services/catalog", tags=["General"])
def get_catalog():
    return {"rails": SERVICE_DEFS, "pools": ledger.accounts}


@app.get("/api/v1/transactions/{txn_id}/status", tags=["General"])
def get_txn_status(txn_id: str):
    for t in TRANSACTIONS:
        if t["id"] == txn_id:
            return t
    raise HTTPException(status_code=404, detail=f"Transaction '{txn_id}' not found")


@app.get("/api/v1/transactions", tags=["General"])
def list_transactions(limit: int = 50):
    return {"count": len(TRANSACTIONS), "transactions": TRANSACTIONS[:limit]}


@app.get("/api/v1/system/telemetry", tags=["General"])
def telemetry():
    uptime = (datetime.utcnow() - STARTED_AT).seconds
    return {
        "uptime_seconds": uptime,
        "simulated_latency_ms": random.randint(28, 55),
        "transactions_processed": len(TRANSACTIONS),
        "pools": ledger.accounts,
        "mode": "SIMULATION",
    }


def rule_based_route(query: str):
    q = query.lower()
    scores = {s["id"]: sum(1 for kw in s["keywords"] if kw in q) for s in SERVICE_DEFS}
    best_id = max(scores, key=scores.get)
    if scores[best_id] == 0:
        return None, "No confident keyword match."
    matched = [kw for kw in SERVICE_BY_ID[best_id]["keywords"] if kw in q]
    return best_id, f"Matched on: {', '.join(matched)}."


@app.post("/api/v1/ai/route", tags=["AI Agent"])
def ai_route(body: RouteRequest):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key and ANTHROPIC_SDK_AVAILABLE:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            service_list = "\n".join(f"- {s['id']}: {s['name']}" for s in SERVICE_DEFS)
            resp = client.messages.create(
                model=os.environ.get("TBG_MODEL", DEFAULT_MODEL),
                max_tokens=200,
                system=(
                    "You are the TBG-CORE routing agent. Choose one service_id from:\n" + service_list +
                    '\nRespond with STRICT JSON only: {"service_id": "...", "reasoning": "..."}'
                ),
                messages=[{"role": "user", "content": body.query}],
            )
            import json as _json
            raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip().strip("`")
            data = _json.loads(raw)
            return {"engine": "llm", "service_id": data["service_id"], "reasoning": data.get("reasoning", "")}
        except Exception as e:
            pass  # fall through to rule-based
    sid, reasoning = rule_based_route(body.query)
    return {"engine": "rule_based", "service_id": sid, "reasoning": reasoning}


@app.post("/api/v1/engine/execute", tags=["AI Agent"])
def engine_execute(body: ExecuteRequest):
    dispatch = {
        "escrow": lambda p: do_escrow_lock(p.get("amount", 50000)),
        "2pc": lambda p: do_2pc(p.get("amount", 25000), p.get("force_timeout", False)),
        "va": lambda p: do_va_collect(p.get("amount", 15000), p.get("invoice_id", "INV-0000")),
        "enach": lambda p: do_enach_trigger(
            p.get("mandate_id") or (list(MANDATES)[0] if MANDATES else do_enach_register(10000, 30, datetime.utcnow()))
        ),
        "sweep": lambda p: do_sweep()[0],
        "fx": lambda p: do_fx(p.get("amount_usd", 500))[0],
        "aa": lambda p: do_aa_pull(p.get("purpose", "underwriting"))[0],
        "split": lambda p: do_split(p.get("gross_amount", 20000), p.get("commission_pct", 10))[0],
        "gst": lambda p: do_gst(p.get("transaction_amount", 100000))[0],
    }
    if body.service_id not in dispatch:
        raise HTTPException(status_code=400, detail=f"Unknown service_id '{body.service_id}'")
    try:
        return dispatch[body.service_id](body.params)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/v1/engine/execute-all", tags=["AI Agent"])
def engine_execute_all():
    results = {}
    for sid in SERVICE_BY_ID:
        try:
            results[sid] = engine_execute(ExecuteRequest(service_id=sid, params={}))
        except HTTPException as e:
            results[sid] = {"error": e.detail}
    return results


# ============================================================================
# RAIL-SPECIFIC ENDPOINTS
# ============================================================================

@app.post("/api/v1/services/escrow-multisig", tags=["Rails"])
def escrow_multisig(body: EscrowRequest):
    try:
        if body.action == "lock":
            return do_escrow_lock(body.amount)
        return do_escrow_release(body.amount, body.signatures)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/v1/services/bulk-disbursal", tags=["Rails"])
def bulk_disbursal(body: DisbursalRequest):
    try:
        return do_2pc(body.amount, body.force_timeout)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/v1/services/virtual-account", tags=["Rails"])
def virtual_account(body: VARequest):
    return do_va_collect(body.amount, body.invoice_id)


@app.post("/api/v1/services/enach-mandate", tags=["Rails"])
def enach_mandate(body: ENachRequest):
    try:
        if body.action == "register":
            if not body.amount:
                raise HTTPException(status_code=422, detail="amount is required to register a mandate")
            mandate_id = do_enach_register(body.amount, body.frequency_days, datetime.utcnow())
            return {"mandate_id": mandate_id, "status": "ACTIVE"}
        if not body.mandate_id:
            raise HTTPException(status_code=422, detail="mandate_id is required to trigger a pull")
        return do_enach_trigger(body.mandate_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/v1/services/liquidity-sweep", tags=["Rails"])
def liquidity_sweep():
    txn, sub_balances = do_sweep()
    return {**txn, "sub_balances": sub_balances}


@app.post("/api/v1/services/fx-nostro", tags=["Rails"])
def fx_nostro(body: FXRequest):
    try:
        txn, rate, ref = do_fx(body.amount_usd)
        return {**txn, "rate": rate, "ref": ref}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/v1/services/account-aggregator", tags=["Rails"])
def account_aggregator(body: AARequest):
    if not body.consent_granted:
        raise HTTPException(status_code=403, detail="Consent not granted \u2014 cannot pull data")
    txn, snapshot = do_aa_pull(body.purpose)
    return {**txn, "snapshot": snapshot}


@app.post("/api/v1/services/marketplace-split", tags=["Rails"])
def marketplace_split(body: SplitRequest):
    txn, commission, payout = do_split(body.gross_amount, body.commission_pct)
    return {**txn, "commission": commission, "seller_payout": payout}


@app.post("/api/v1/services/gst-statutory-escrow", tags=["Rails"])
def gst_statutory_escrow(body: GSTRequest):
    txn, gst = do_gst(body.transaction_amount)
    return {**txn, "gst_sequestered": gst}
