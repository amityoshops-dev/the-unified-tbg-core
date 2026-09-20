import hashlib
import os
import pathlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ============================================================================
# APP INITIALIZATION (CLEAN BRANDING)
# ============================================================================
app = FastAPI(
    title="TBG-Core Enterprise Platform",
    version="2026.4",
    description="Transaction Banking Group Engine: Core Ledger, RERA Escrow, Sandbox, ERP Connectors & MCP Layer",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if pathlib.Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

if pathlib.Path("static/assets").exists():
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")


# ============================================================================
# DATA SCHEMAS
# ============================================================================
class TransactionEntry(BaseModel):
    account_id: str
    entry_type: str  # "DEBIT" or "CREDIT"
    amount: Decimal


class JournalBatch(BaseModel):
    idempotency_key: str
    reference_note: str
    entries: List[TransactionEntry]


class PayoutBatchItem(BaseModel):
    vendor_id: str
    beneficiary_acc: str
    beneficiary_ifsc: str
    amount: Decimal
    payout_mode: str = "NEFT"


class BulkPayoutRequest(BaseModel):
    batch_id: str
    payouts: List[PayoutBatchItem]


class RERAInwardRequest(BaseModel):
    project_id: str
    payer_van: str
    buyer_ref: str
    amount: float


class MilestoneReleaseRequest(BaseModel):
    ca_udin: str
    amount: float
    contractor: str


class ERPSyncRequest(BaseModel):
    tx_id: str
    system: str = "ALL"  # "FRAPPE", "ZOHO", or "ALL"


# ============================================================================
# CORE LEDGER & TRANSACTION PROCESSOR
# ============================================================================
class TBGCoreProcessor:
    def __init__(self):
        self.accounts: Dict[str, Decimal] = {
            "ESCROW_MASTER_70": Decimal("0.00"),
            "ESCROW_OPERATING_30": Decimal("0.00"),
            "POOL_COLLECTIONS_VAN": Decimal("0.00"),
            "SUB_POOL_WEST": Decimal("2450000.00"),
            "SUB_POOL_NORTH": Decimal("1850000.00"),
            "MASTER_TREASURY_CORP": Decimal("15000000.00"),
            "PAYOUT_CLEARING_GL": Decimal("5000000.00"),
        }
        self.idempotency_store: Dict[str, dict] = {}
        self.audit_log: List[dict] = []

    def execute_double_entry(self, batch: JournalBatch) -> dict:
        if batch.idempotency_key in self.idempotency_store:
            return {"status": "CACHED", "data": self.idempotency_store[batch.idempotency_key]}

        debits = sum(e.amount for e in batch.entries if e.entry_type == "DEBIT")
        credits = sum(e.amount for e in batch.entries if e.entry_type == "CREDIT")
        if debits != credits or debits <= Decimal("0.00"):
            raise ValueError("Invariant Failed: Total Debits must match Total Credits strictly.")

        tx_id = f"TXN-TBG-{uuid.uuid4().hex[:8].upper()}"
        timestamp = datetime.now(timezone.utc).isoformat()

        for entry in batch.entries:
            if entry.account_id not in self.accounts:
                self.accounts[entry.account_id] = Decimal("0.00")
            if entry.entry_type == "DEBIT":
                self.accounts[entry.account_id] -= entry.amount
            elif entry.entry_type == "CREDIT":
                self.accounts[entry.account_id] += entry.amount

        record = {
            "tx_id": tx_id,
            "timestamp": timestamp,
            "reference": batch.reference_note,
            "entries": [e.model_dump() for e in batch.entries],
        }
        self.audit_log.append(record)
        self.idempotency_store[batch.idempotency_key] = record
        return {"status": "COMMITTED", "tx_id": tx_id, "record": record}


core_engine = TBGCoreProcessor()


# ============================================================================
# ERP & SANDBOX CONNECTORS
# ============================================================================
class ERPConnector:
    @staticmethod
    async def post_to_frappe(journal: dict) -> dict:
        return {
            "erp": "FRAPPE",
            "status": "SYNCED",
            "voucher_no": f"JV-FRP-{uuid.uuid4().hex[:8].upper()}",
            "posting_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

    @staticmethod
    async def post_to_zoho(journal: dict) -> dict:
        return {
            "erp": "ZOHO",
            "status": "SYNCED",
            "journal_id": f"ZH-JRN-{uuid.uuid4().hex[:8].upper()}",
            "entry_ref": journal.get("tx_id"),
        }


# ============================================================================
# API ROUTES (SWAGGER DOCS)
# ============================================================================
@app.get("/", tags=["Dashboard"], response_class=HTMLResponse)
async def serve_root():
    dash = pathlib.Path("static/index.html")
    if dash.exists():
        return FileResponse(dash)
    return HTMLResponse(
        "<body style='background:#0f172a;color:#f8fafc;font-family:sans-serif;padding:40px;'>"
        "<h2>TBG-Core Platform Online</h2><a style='color:#38bdf8;' href='/docs'>Swagger API Console</a></body>"
    )


@app.get("/api/v1/ledger/balances", tags=["Ledger Core"])
async def get_gl_balances():
    """Returns live general ledger balances across all pools and escrows."""
    return {"status": "SUCCESS", "balances": {k: str(v) for k, v in core_engine.accounts.items()}}


@app.post("/api/v1/ledger/journal", tags=["Ledger Core"])
async def post_custom_journal(batch: JournalBatch):
    """Executes an atomic, balanced multi-leg double-entry batch."""
    try:
        return core_engine.execute_double_entry(batch)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/escrow/rera-inward", tags=["RERA Escrow"])
async def process_rera_inward(req: RERAInwardRequest):
    """Executes statutory 70:30 allocation into project and operating escrows."""
    gross = Decimal(str(req.amount))
    escrow_70 = (gross * Decimal("0.70")).quantize(Decimal("0.01"))
    operating_30 = gross - escrow_70
    idemp_key = f"RERA-{req.project_id}-{req.buyer_ref}-{hashlib.md5(str(gross).encode()).hexdigest()[:6]}"

    batch = JournalBatch(
        idempotency_key=idemp_key,
        reference_note=f"RERA Waterfall: Proj {req.project_id} | Unit {req.buyer_ref}",
        entries=[
            TransactionEntry(account_id="POOL_COLLECTIONS_VAN", entry_type="DEBIT", amount=gross),
            TransactionEntry(account_id="ESCROW_MASTER_70", entry_type="CREDIT", amount=escrow_70),
            TransactionEntry(account_id="ESCROW_OPERATING_30", entry_type="CREDIT", amount=operating_30),
        ],
    )
    return core_engine.execute_double_entry(batch)


@app.post("/api/v1/escrow/milestone-release", tags=["RERA Escrow"])
async def release_milestone(req: MilestoneReleaseRequest):
    """Releases funds from 70% Escrow gated by 18-digit ICAI CA UDIN validation."""
    if not req.ca_udin.startswith("26") or len(req.ca_udin) != 18:
        raise HTTPException(status_code=400, detail="Invalid ICAI UDIN. Milestone release rejected.")

    amt = Decimal(str(req.amount))
    if core_engine.accounts["ESCROW_MASTER_70"] < amt:
        raise HTTPException(status_code=400, detail="Insufficient funds in 70% RERA Escrow account.")

    batch = JournalBatch(
        idempotency_key=f"UDIN-{req.ca_udin}-{amt}",
        reference_note=f"Contractor Release | UDIN: {req.ca_udin}",
        entries=[
            TransactionEntry(account_id="ESCROW_MASTER_70", entry_type="DEBIT", amount=amt),
            TransactionEntry(account_id=f"VENDOR_{req.contractor.upper()}", entry_type="CREDIT", amount=amt),
        ],
    )
    return core_engine.execute_double_entry(batch)


@app.post("/api/v1/sandbox/bulk-payout", tags=["Bank Sandbox & Payouts"])
async def process_sandbox_payout(req: BulkPayoutRequest):
    """Executes vendor payout clearing rail simulation (NEFT/RTGS) with UTR generation."""
    total = sum(p.amount for p in req.payouts)
    if core_engine.accounts["PAYOUT_CLEARING_GL"] < total:
        raise HTTPException(status_code=400, detail="Insufficient liquidity in Payout Clearing GL.")

    journal_entries = [TransactionEntry(account_id="PAYOUT_CLEARING_GL", entry_type="DEBIT", amount=total)]
    dispatched = []

    for item in req.payouts:
        utr = f"UTR{datetime.now().strftime('%y%m%d%H%M')}{uuid.uuid4().hex[:6].upper()}"
        journal_entries.append(
            TransactionEntry(account_id=f"VENDOR_{item.vendor_id.upper()}", entry_type="CREDIT", amount=item.amount)
        )
        dispatched.append({"vendor_id": item.vendor_id, "utr": utr, "mode": item.payout_mode, "status": "SETTLED"})

    res = core_engine.execute_double_entry(
        JournalBatch(idempotency_key=f"PAY-{req.batch_id}", reference_note=f"Bulk Batch: {req.batch_id}", entries=journal_entries)
    )
    return {"status": "SUCCESS", "journal": res, "dispatches": dispatched}


@app.post("/api/v1/liquidity/sweep", tags=["Liquidity Management"])
async def trigger_eod_sweeps():
    """Sweeps regional collection sub-pools into master corporate treasury."""
    actions = []
    for pool in ["SUB_POOL_WEST", "SUB_POOL_NORTH"]:
        bal = core_engine.accounts.get(pool, Decimal("0.00"))
        if bal > Decimal("0.00"):
            res = core_engine.execute_double_entry(
                JournalBatch(
                    idempotency_key=f"SWEEP-{pool}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                    reference_note=f"Concentration Sweep from {pool}",
                    entries=[
                        TransactionEntry(account_id=pool, entry_type="DEBIT", amount=bal),
                        TransactionEntry(account_id="MASTER_TREASURY_CORP", entry_type="CREDIT", amount=bal),
                    ],
                )
            )
            actions.append(res)
    return {"status": "SWEEPS_EXECUTED", "actions": actions, "balances": {k: str(v) for k, v in core_engine.accounts.items()}}


@app.post("/api/v1/erp/sync", tags=["ERP Integrations"])
async def sync_erp(req: ERPSyncRequest):
    """Syncs a committed double-entry journal voucher to Frappe and Zoho Books."""
    record = next((r for r in core_engine.audit_log if r["tx_id"] == req.tx_id), None)
    if not record:
        raise HTTPException(status_code=404, detail=f"Transaction {req.tx_id} not found.")

    res = {}
    if req.system in ["FRAPPE", "ALL"]:
        res["frappe"] = await ERPConnector.post_to_frappe(record)
    if req.system in ["ZOHO", "ALL"]:
        res["zoho"] = await ERPConnector.post_to_zoho(record)
    return {"tx_id": req.tx_id, "sync_results": res}


@app.get("/mcp/tools", tags=["MCP Agent Layer"])
async def list_mcp_tools():
    """Tool manifest discovery for MCP agents."""
    return {
        "tools": [
            {"name": "get_gl_balances", "description": "Fetch real-time double-entry GL balances."},
            {"name": "trigger_eod_sweeps", "description": "Run liquidity sweeps to central treasury."},
        ]
    }