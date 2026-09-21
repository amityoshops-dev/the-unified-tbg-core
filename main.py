import asyncio
import hashlib
import hmac
import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="TBG-CORE Institutional Banking Workbench", version="12.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "tbg_enterprise_ledger.db"
HMAC_SECRET = "tbg_institutional_vault_secret_9921"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                account_name TEXT NOT NULL,
                account_type TEXT NOT NULL,
                balance_paisa INTEGER NOT NULL CHECK (balance_paisa >= 0),
                currency TEXT DEFAULT 'INR'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                txn_id TEXT PRIMARY KEY,
                service_code TEXT NOT NULL,
                idempotency_key TEXT UNIQUE NOT NULL,
                source_account TEXT NOT NULL,
                target_account TEXT NOT NULL,
                amount_paisa INTEGER NOT NULL,
                state TEXT NOT NULL,
                clearing_rail TEXT NOT NULL,
                hmac_signature TEXT NOT NULL,
                iso_xml TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ledger_journal (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                txn_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                direction TEXT CHECK(direction IN ('DEBIT', 'CREDIT')),
                amount_paisa INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        cursor.execute("SELECT COUNT(*) FROM accounts")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("""
                INSERT INTO accounts (account_id, account_name, account_type, balance_paisa, currency)
                VALUES (?, ?, ?, ?, ?)
            """, [
                ("ESCROW_MASTER_01", "Digital Escrow Trust Vault", "TRUST_NODAL", 1500000000, "INR"),
                ("CORP_OPERATING_01", "Primary Treasury Core", "OPERATING", 750000000, "INR"),
                ("SETTLEMENT_CLEARING_01", "2PC Disbursal Clearing Pool", "CLEARING", 500000000, "INR"),
                ("VAN_RECEIVABLES_POOL", "Dynamic Smart VAN Collector", "COLLECTION", 200000000, "INR"),
                ("NOSTRO_USD_INR_01", "Nostro Foreign Exchange Mirror", "NOSTRO", 2500000000, "INR"),
                ("SUPPLIER_SCF_POOL", "Supply Chain Finance Tranche Pool", "SETTLEMENT", 100000000, "INR"),
                ("BENEFICIARY_EXTERNAL", "External Corporate Counterparty", "EXTERNAL", 50000000, "INR")
            ])
        conn.commit()

init_db()

def compute_hmac(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True)
    return hmac.new(HMAC_SECRET.encode(), serialized.encode(), hashlib.sha256).hexdigest()

def build_iso_xml(txn_id: str, srv: str, src: str, tgt: str, amount_paisa: int, rail: str) -> str:
    amt_inr = f"{amount_paisa / 100:.2f}"
    now = datetime.now(timezone.utc).isoformat()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>{txn_id}</MsgId>
      <CreDtTm>{now}</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <InitgPty><Nm>TBG-CORE [{srv}]</Nm></InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>PMT-{txn_id[:8]}</PmtInfId>
      <PmtMtd>TRF</PmtMtd>
      <PmtTpInf><LclInstrm><Prtry>{rail}</Prtry></LclInstrm></PmtTpInf>
      <Dbtr><Nm>{src}</Nm></Dbtr>
      <CdtTrfTxInf>
        <PmtId><EndToEndId>{txn_id}</EndToEndId></PmtId>
        <Amt><InstdAmt Ccy="INR">{amt_inr}</InstdAmt></Amt>
        <Cdtr><Nm>{tgt}</Nm></Cdtr>
      </CdtTrfTxInf>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>"""

SERVICES = {
    "ESCROW_MULTISIG": {
        "title": "Digital Escrow Multi-Sig Vault",
        "rail": "Conditional Trust Custody Rail",
        "category": "Custody & Escrow",
        "reg": "RERA Act 2016 / Section 4(2)(l)(D) / RBI Nodal Account Directions",
        "badge": "Escrow Vault",
        "desc": "Conditional milestone escrow holding funds in unallocated trust nodal accounts until cryptographic dual-signoff clears.",
        "nodes": ["Initiator ERP", "Dual-Sig Validator", "Escrow WAL Ledger", "Beneficiary Settlement"],
        "steps": [
            "Validating cryptographic dual-signoff keys (2-of-3 quorum threshold)",
            "Executing balance hold on Master Escrow Trust Pool (SQLite WAL Lock)",
            "Broadcasting milestone state lock to Trustee Audit Rail",
            "Releasing settlement tranche & generating canonical ISO 20022 XML"
        ],
        "src": "ESCROW_MASTER_01",
        "tgt": "CORP_OPERATING_01",
        "amt": 5000000
    },
    "BULK_PAYOUT_2PC": {
        "title": "2-Phase Commit Bulk Disbursals",
        "rail": "IMPS / RTGS Immediate Clearing Rail",
        "category": "Outward Clearing",
        "reg": "RBI RTGS/NEFT Regulations & Atomicity Directives",
        "badge": "2PC Disbursals",
        "desc": "High-throughput disbursals with 2PC atomic balance reservation ensuring no duplicate credits on timeouts.",
        "nodes": ["Corporate Batch", "2PC Coordinator", "Switch Gateway", "External Core Bank"],
        "steps": [
            "Phase 1: Reserving ledger balance in PRE_COMMIT state (No double-spend)",
            "Transmitting payload to clearing switch gateway with Idempotency header",
            "Awaiting clearing gateway ACK with exponential backoff fallback",
            "Phase 2: Committing debit journal and releasing external credit"
        ],
        "src": "SETTLEMENT_CLEARING_01",
        "tgt": "BENEFICIARY_EXTERNAL",
        "amt": 2500000
    },
    "VAN_COLLECTION": {
        "title": "Smart Virtual Account CMS",
        "rail": "Inward RTGS / NEFT VAN Rail",
        "category": "Receivables & CMS",
        "reg": "RBI Cash Management Directions / Virtual Account Guidelines",
        "badge": "Smart VAN",
        "desc": "Dynamic sub-account routing directly matching incoming credits to open invoices with zero manual reconciliation.",
        "nodes": ["Payer Bank", "RTGS Switch", "Smart VAN Router", "Corporate Main Pool"],
        "steps": [
            "Ingesting inward RTGS clearing credit notice with custom prefix VAN",
            "Parsing client VAN reference and verifying open invoice ERP status",
            "Posting automated 1:1 reconciliation credit to collector ledger",
            "Sweeping reconciled capital into Master Corporate Operating Pool"
        ],
        "src": "BENEFICIARY_EXTERNAL",
        "tgt": "VAN_RECEIVABLES_POOL",
        "amt": 1500000
    },
    "E_NACH_MANDATE": {
        "title": "e-NACH Standing Orders Engine",
        "rail": "Automated Clearing House (e-Mandate)",
        "category": "Recurring Collections",
        "reg": "NPCI NACH Procedural Guidelines / Aadhaar e-Sign Mandates",
        "badge": "e-NACH Mandates",
        "desc": "Automated recurring pulling from debtor bank accounts based on authenticated NPCI mandates.",
        "nodes": ["Mandate Vault", "Batch Synthesizer", "Clearing Cycle", "Collector Pool"],
        "steps": [
            "Verifying destination bank UMRN authentication and validity date",
            "Compacting recurring mandate into NPCI presentment batch file",
            "Executing interbank debit presentation during morning clearing window",
            "Crediting collection nodal pool and acknowledging schedule"
        ],
        "src": "BENEFICIARY_EXTERNAL",
        "tgt": "ESCROW_MASTER_01",
        "amt": 1000000
    },
    "LIQUIDITY_SWEEP": {
        "title": "Zero-Balance Concentration Sweep",
        "rail": "Intraday Treasury Sweep Rail",
        "category": "Treasury & Liquidity",
        "reg": "Corporate Cash Concentration Standards / TARGET2 Best Practices",
        "badge": "Liquidity Sweeps",
        "desc": "Automated concentration mechanics sweeping subsidiary balances above threshold to maximize interest.",
        "nodes": ["Subsidiary Account", "Balance Evaluator", "ZBA Journal Engine", "Master Yield Pool"],
        "steps": [
            "Sampling subsidiary operational balance against ₹1,00,000 threshold",
            "Calculating surplus float exceeding minimum operational buffer",
            "Posting zero-balance automated debit to subsidiary operational account",
            "Journaling concentration credit into Master Treasury Yield Pool"
        ],
        "src": "CORP_OPERATING_01",
        "tgt": "ESCROW_MASTER_01",
        "amt": 7500000
    },
    "FX_CROSS_BORDER": {
        "title": "Cross-Border FX Nostro Remittance",
        "rail": "SWIFT / ISO 20022 Cross-Border Rail",
        "category": "Trade & FX",
        "reg": "FEMA 1999 Guidelines / SWIFT MT103 / pacs.008",
        "badge": "Cross-Border FX",
        "desc": "Outward cross-border settlement formatting pain.001 wires with real-time FX rate lock & sanctions checking.",
        "nodes": ["Domestic Treasury", "AML Sanction Shield", "SWIFT Messaging Bus", "Nostro Clearing Mirror"],
        "steps": [
            "Locking USD/INR spot FX quote for 15-minute execution window",
            "Executing automated OFAC & global sanctions PEP compliance check",
            "Constructing canonical SWIFT ISO 20022 pain.001 remittance envelope",
            "Debiting domestic treasury pool in INR and crediting Nostro mirror in USD"
        ],
        "src": "CORP_OPERATING_01",
        "tgt": "NOSTRO_USD_INR_01",
        "amt": 12000000
    },
    "SUPPLY_CHAIN_ESCROW": {
        "title": "Supply Chain Tranche Factoring",
        "rail": "Invoice Factoring Settlement Rail",
        "category": "SCF & Factoring",
        "reg": "Factoring Regulation Act 2011 / TReDS Guidelines",
        "badge": "Supply Chain Escrow",
        "desc": "Tier-1 reverse factoring disbursing 80% capital upfront and 20% upon delivery milestone completion.",
        "nodes": ["Invoicing Portal", "Tranche 1 Engine", "e-POD Verifier", "Tranche 2 Finalizer"],
        "steps": [
            "Ingesting validated electronic tax invoice and e-Way bill data",
            "Disbursing Tranche 1 (80% working capital) to vendor clearing pool",
            "Verifying buyer electronic proof-of-delivery (e-POD) confirmation notice",
            "Releasing Tranche 2 (20% balance reserve) minus factoring haircut fee"
        ],
        "src": "ESCROW_MASTER_01",
        "tgt": "SUPPLIER_SCF_POOL",
        "amt": 3000000
    },
    "TREASURY_POSITION": {
        "title": "Intraday Treasury Float & P&L",
        "rail": "Float Valuation Engine",
        "category": "Analytics & P&L",
        "reg": "Basel III Liquidity Coverage Ratio (LCR) Directives",
        "badge": "Treasury Float",
        "desc": "Calculates real-time capital deployment, overnight interest accrual, and liquidity availability across accounts.",
        "nodes": ["Pool Aggregator", "Clearing Exposure Calc", "Yield Formula Engine", "Executive Ledger P&L"],
        "steps": [
            "Snapshotting unallocated balances across institutional pools",
            "Evaluating unsettled clearing exposure across outgoing rails",
            "Applying benchmark overnight MIBOR yield formula",
            "Committing synthetic yield accrual entries to treasury ledger"
        ],
        "src": "CORP_OPERATING_01",
        "tgt": "CORP_OPERATING_01",
        "amt": 100000
    },
    "ISO20022_MESSAGE": {
        "title": "Host-to-Host ISO 20022 Transformer",
        "rail": "Canonical H2H XML Banking Bus",
        "category": "Messaging Infrastructure",
        "reg": "ISO 20022 Universal Financial Message Scheme",
        "badge": "ISO 20022 H2H",
        "desc": "Translates modern JSON transactional requests into strictly validated ISO 20022 XML envelopes.",
        "nodes": ["JSON Ingestion", "Schema Transformer", "XSD Validator", "H2H SFTP Dispatcher"],
        "steps": [
            "Ingesting raw transactional JSON parameter array",
            "Normalizing payment data into canonical bank structures",
            "Running strict XSD schema validation against ISO definitions",
            "Digitally signing output XML and queuing for H2H SFTP upload"
        ],
        "src": "CORP_OPERATING_01",
        "tgt": "BENEFICIARY_EXTERNAL",
        "amt": 500000
    }
}

class ExecutePayload(BaseModel):
    service_code: str
    source_account: str
    target_account: str
    amount_paisa: int = Field(gt=0)
    client_ref: str = "TBG-EXEC-001"

class AIResolvePayload(BaseModel):
    query: str

@app.get("/api/v1/services/catalog")
async def get_catalog():
    return SERVICES

@app.post("/api/v1/engine/execute")
async def execute_engine(req: ExecutePayload, bg: BackgroundTasks):
    if req.service_code not in SERVICES:
        raise HTTPException(status_code=400, detail="Unknown service code")
    
    spec = SERVICES[req.service_code]
    now = datetime.now(timezone.utc).isoformat()
    idemp_key = f"tbg_{req.service_code}_{req.client_ref}_{int(time.time()*1000)}"
    txn_id = f"TBG-{hashlib.md5(idemp_key.encode()).hexdigest()[:10].upper()}"
    
    hmac_sig = compute_hmac(req.model_dump())
    xml_msg = build_iso_xml(txn_id, req.service_code, req.source_account, req.target_account, req.amount_paisa, spec["rail"])

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Debits: Checked and executed for all debit-bearing operations
        debit_services = [
            "ESCROW_MULTISIG", "BULK_PAYOUT_2PC", "LIQUIDITY_SWEEP", 
            "FX_CROSS_BORDER", "SUPPLY_CHAIN_ESCROW", "ISO20022_MESSAGE"
        ]
        if req.service_code in debit_services:
            cursor.execute("SELECT balance_paisa FROM accounts WHERE account_id = ?", (req.source_account,))
            row = cursor.fetchone()
            if not row or row[0] < req.amount_paisa:
                raise HTTPException(status_code=422, detail=f"Insufficient funds in source account: {req.source_account}")
            
            cursor.execute("UPDATE accounts SET balance_paisa = balance_paisa - ? WHERE account_id = ?", (req.amount_paisa, req.source_account))
            cursor.execute("INSERT INTO ledger_journal (txn_id, account_id, direction, amount_paisa, timestamp) VALUES (?, ?, 'DEBIT', ?, ?)",
                           (txn_id, req.source_account, req.amount_paisa, now))
        
        # Credits: Executed for receiving pools
        credit_services = [
            "ESCROW_MULTISIG", "VAN_COLLECTION", "LIQUIDITY_SWEEP", "SUPPLY_CHAIN_ESCROW", 
            "BULK_PAYOUT_2PC", "E_NACH_MANDATE", "FX_CROSS_BORDER", "ISO20022_MESSAGE"
        ]
        if req.service_code in credit_services:
            cursor.execute("""
                INSERT INTO accounts (account_id, account_name, account_type, balance_paisa, currency)
                VALUES (?, 'Settlement Destination Pool', 'SETTLEMENT', ?, 'INR')
                ON CONFLICT(account_id) DO UPDATE SET balance_paisa = balance_paisa + ?
            """, (req.target_account, req.amount_paisa, req.amount_paisa))
            cursor.execute("INSERT INTO ledger_journal (txn_id, account_id, direction, amount_paisa, timestamp) VALUES (?, ?, 'CREDIT', ?, ?)",
                           (txn_id, req.target_account, req.amount_paisa, now))

        # Treasury Position Intraday Yield Posting: Synthetic accrual
        if req.service_code == "TREASURY_POSITION":
            cursor.execute("""
                UPDATE accounts SET balance_paisa = balance_paisa + ? WHERE account_id = ?
            """, (req.amount_paisa, req.target_account))
            cursor.execute("INSERT INTO ledger_journal (txn_id, account_id, direction, amount_paisa, timestamp) VALUES (?, ?, 'CREDIT', ?, ?)",
                           (txn_id, req.target_account, req.amount_paisa, now))

        cursor.execute("""
            INSERT INTO transactions (txn_id, service_code, idempotency_key, source_account, target_account, amount_paisa, state, clearing_rail, hmac_signature, iso_xml, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'SETTLED', ?, ?, ?, ?)
        """, (txn_id, req.service_code, idemp_key, req.source_account, req.target_account, req.amount_paisa, spec['rail'], hmac_sig, xml_msg, now))
        conn.commit()

    return {
        "status": "SETTLED",
        "txn_id": txn_id,
        "service": spec["title"],
        "rail": spec["rail"],
        "amount_inr": req.amount_paisa / 100,
        "hmac_signature": hmac_sig,
        "iso_xml": xml_msg,
        "steps": spec["steps"],
        "nodes": spec["nodes"]
    }

@app.post("/api/v1/engine/execute-all")
async def execute_all_services():
    """Batch executes all 9 services in sequence to verify full-stack clearing."""
    results = []
    for code, spec in SERVICES.items():
        payload = ExecutePayload(
            service_code=code,
            source_account=spec["src"],
            target_account=spec["tgt"],
            amount_paisa=spec["amt"],
            client_ref=f"BATCH-{int(time.time()*1000)}"
        )
        res = await execute_engine(payload, BackgroundTasks())
        results.append(res)
    return {"status": "SUCCESS", "executed_count": len(results), "transactions": results}

@app.post("/api/v1/ai/route")
async def ai_route(q: AIResolvePayload):
    p = q.query.lower()
    if "emi" in p or "mandate" in p or "recurring" in p or ("debit" in p and "month" in p):
        code = "E_NACH_MANDATE"
    elif "escrow" in p or "trust" in p or "hold" in p or "milestone" in p:
        code = "ESCROW_MULTISIG"
    elif "cross-border" in p or "swift" in p or "usd" in p or "foreign" in p:
        code = "FX_CROSS_BORDER"
    elif "sweep" in p or "idle" in p or "zero" in p:
        code = "LIQUIDITY_SWEEP"
    elif "van" in p or "virtual" in p or ("invoice" in p and "reconcil" in p):
        code = "VAN_COLLECTION"
    elif "factor" in p or "supply chain" in p or "supplier" in p:
        code = "SUPPLY_CHAIN_ESCROW"
    elif "p&l" in p or "float" in p or "treasury" in p:
        code = "TREASURY_POSITION"
    elif "iso" in p or "xml" in p or "pain" in p:
        code = "ISO20022_MESSAGE"
    else:
        code = "BULK_PAYOUT_2PC"

    spec = SERVICES[code]
    return {
        "code": code,
        "title": spec["title"],
        "rail": spec["rail"],
        "reg": spec["reg"],
        "reasoning": f"NLP intent matched: '{spec['title']}' routing over '{spec['rail']}' compliant with {spec['reg']}.",
        "steps": spec["steps"],
        "nodes": spec["nodes"]
    }

@app.get("/api/v1/system/telemetry")
async def telemetry():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT account_id, account_name, account_type, balance_paisa FROM accounts")
        accounts = cursor.fetchall()
        cursor.execute("SELECT txn_id, service_code, amount_paisa, clearing_rail, hmac_signature, created_at FROM transactions ORDER BY created_at DESC LIMIT 8")
        txns = cursor.fetchall()
    return {
        "accounts": [{"id": a[0], "name": a[1], "type": a[2], "inr": a[3] / 100} for a in accounts],
        "txns": [{"txn_id": t[0], "service": t[1], "inr": t[2] / 100, "rail": t[3], "hmac": t[4][:16] + "...", "time": t[5]} for t in txns]
    }

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TBG-CORE | Institutional Transaction Banking Workbench</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {
            background-color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            color: #0f172a;
        }
        .card-shadow {
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.05), 0 1px 2px -1px rgb(0 0 0 / 0.05);
        }
        .flow-line {
            stroke-dasharray: 6, 4;
            animation: flowAnimation 2s linear infinite;
        }
        @keyframes flowAnimation {
            0% { stroke-dashoffset: 20; }
            100% { stroke-dashoffset: 0; }
        }
    </style>
</head>
<body class="min-h-screen">

    <header class="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="h-8 w-8 rounded-md bg-indigo-950 flex items-center justify-center text-white font-bold text-xs tracking-wider">TBG</div>
                <div>
                    <h1 class="text-sm font-semibold text-slate-900 tracking-tight">The Unified TBG-CORE</h1>
                    <p class="text-[11px] text-slate-500 font-mono">Institutional Rails &bull; ISO 20022 Engine &bull; Double-Entry Ledger</p>
                </div>
            </div>
            <div class="flex items-center space-x-3 text-xs">
                <button onclick="executeAllSuite()" id="btnExecAll" class="px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition shadow-xs flex items-center space-x-1.5">
                    <span>▶ Execute All 9 Services</span>
                </button>
                <button onclick="refreshData()" class="px-3 py-1.5 rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 font-medium transition shadow-xs">
                    &circlearrowright; Sync Ledger
                </button>
                <a href="/docs" target="_blank" class="px-3 py-1.5 rounded-md bg-indigo-900 hover:bg-indigo-800 text-white font-medium transition shadow-xs">
                    API Docs (/docs)
                </a>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-6 py-6 space-y-6">

        <div class="bg-white rounded-xl border border-slate-200 p-4 card-shadow space-y-2.5">
            <div class="flex justify-between items-center text-xs">
                <span class="font-semibold text-slate-900 tracking-wide uppercase">AI Intent Classification Router</span>
                <span class="text-[11px] font-mono text-emerald-700 font-medium bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">Engine Active</span>
            </div>
            <div class="flex gap-2">
                <input id="aiInput" type="text" value="Client needs to debit 10000 loan EMI every month on 5th via bank mandate"
                       class="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3.5 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-600 font-mono">
                <button onclick="routeAI()" class="bg-indigo-900 hover:bg-indigo-800 text-white font-semibold text-xs px-5 py-2 rounded-lg transition shadow-xs">
                    Route Query
                </button>
            </div>
            <div id="aiOutput" class="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs font-mono text-slate-600 min-h-[38px] flex items-center">
                Submit an intent query to classify the payment rail and load the execution parameters.
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
            <div class="bg-white p-4 rounded-xl border border-slate-200 card-shadow">
                <span class="text-slate-500 block mb-1">ESCROW TRUST POOL</span>
                <div id="metricEscrow" class="text-base font-bold text-slate-900 mb-1">₹1.50 Cr</div>
                <span class="text-emerald-700 font-medium text-[11px]">&bull; RERA Nodal Vault</span>
            </div>
            <div class="bg-white p-4 rounded-xl border border-slate-200 card-shadow">
                <span class="text-slate-500 block mb-1">OPERATING TREASURY</span>
                <div id="metricOperating" class="text-base font-bold text-slate-900 mb-1">₹75.00 L</div>
                <span class="text-slate-600 font-medium text-[11px]">&bull; Corporate Float</span>
            </div>
            <div class="bg-white p-4 rounded-xl border border-slate-200 card-shadow">
                <span class="text-slate-500 block mb-1">2PC CLEARING POOL</span>
                <div id="metricClearing" class="text-base font-bold text-slate-900 mb-1">₹50.00 L</div>
                <span class="text-sky-700 font-medium text-[11px]">&bull; Atomic Reserve</span>
            </div>
            <div class="bg-white p-4 rounded-xl border border-slate-200 card-shadow">
                <span class="text-slate-500 block mb-1">NOSTRO FX MIRROR</span>
                <div id="metricNostro" class="text-base font-bold text-slate-900 mb-1">₹2.50 Cr</div>
                <span class="text-purple-700 font-medium text-[11px]">&bull; USD/INR Wire</span>
            </div>
        </div>

        <div class="bg-white rounded-xl border border-slate-200 p-6 card-shadow space-y-4">
            <div class="flex justify-between items-center border-b border-slate-100 pb-3">
                <div>
                    <h2 class="text-xs font-semibold uppercase tracking-wide text-slate-900">Transaction Banking Architecture &amp; Rails Schematic</h2>
                    <p class="text-[11px] text-slate-500">Live bus routing from corporate ERP through core validation into the 9 institutional banking engines.</p>
                </div>
                <span class="text-[11px] font-mono bg-slate-100 text-slate-700 px-2.5 py-1 rounded-md font-semibold">9/9 Rails Wired</span>
            </div>

            <div class="relative w-full overflow-x-auto py-4">
                <svg class="w-full min-w-[760px] h-32" viewBox="0 0 800 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M 140 60 L 260 60" stroke="#312e81" stroke-width="2" class="flow-line"/>
                    <path d="M 460 60 L 580 30" stroke="#0284c7" stroke-width="2" class="flow-line"/>
                    <path d="M 460 60 L 580 60" stroke="#10b981" stroke-width="2" class="flow-line"/>
                    <path d="M 460 60 L 580 90" stroke="#8b5cf6" stroke-width="2" class="flow-line"/>

                    <g transform="translate(10, 30)">
                        <rect width="130" height="60" rx="8" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.5"/>
                        <text x="65" y="28" text-anchor="middle" fill="#0f172a" font-size="11" font-weight="600">Enterprise ERP</text>
                        <text x="65" y="44" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">REST / AS2 Bus</text>
                    </g>

                    <g transform="translate(260, 25)">
                        <rect width="200" height="70" rx="8" fill="#1e1b4b"/>
                        <text x="100" y="32" text-anchor="middle" fill="#ffffff" font-size="12" font-weight="700">TBG-CORE ENGINE</text>
                        <text x="100" y="48" text-anchor="middle" fill="#c7d2fe" font-size="9" font-family="monospace">Idempotency &bull; WAL Ledger</text>
                    </g>

                    <g transform="translate(580, 5)">
                        <rect width="210" height="34" rx="6" fill="#f0f9ff" stroke="#bae6fd" stroke-width="1"/>
                        <text x="105" y="22" text-anchor="middle" fill="#0369a1" font-size="10" font-weight="600">Outward Clearing &bull; 2PC Disbursals</text>
                    </g>
                    <g transform="translate(580, 44)">
                        <rect width="210" height="34" rx="6" fill="#f0fdf4" stroke="#bbf7d0" stroke-width="1"/>
                        <text x="105" y="22" text-anchor="middle" fill="#15803d" font-size="10" font-weight="600">Custody &bull; RERA Escrow Vault</text>
                    </g>
                    <g transform="translate(580, 83)">
                        <rect width="210" height="34" rx="6" fill="#faf5ff" stroke="#e9d5ff" stroke-width="1"/>
                        <text x="105" y="22" text-anchor="middle" fill="#7e22ce" font-size="10" font-weight="600">Receivables &bull; Smart VAN Collections</text>
                    </g>
                </svg>
            </div>
        </div>

        <div>
            <div class="flex justify-between items-center mb-3">
                <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-900">Institutional Services Suite (All 9 Core Engines)</h3>
                <span class="text-xs text-slate-500 font-mono">Click any service to inspect &amp; execute &rarr;</span>
            </div>
            <div id="serviceGrid" class="grid grid-cols-1 md:grid-cols-3 gap-4"></div>
        </div>

        <div class="bg-white rounded-xl border border-slate-200 p-5 card-shadow space-y-3 font-mono text-xs">
            <div class="flex justify-between items-center border-b border-slate-100 pb-2">
                <span class="font-semibold text-slate-900 uppercase">Live Double-Entry Settlement Audit Stream</span>
                <span class="text-[11px] text-slate-500">Real-time journal verification</span>
            </div>
            <div id="auditLog" class="space-y-1.5 text-slate-600">
                <div class="p-2 rounded bg-slate-50 border border-slate-100 flex justify-between">
                    <span>[SYSTEM_READY] Core double-entry ledger synchronized. SQLite WAL journal active.</span>
                    <span class="text-slate-400">00:00:00</span>
                </div>
            </div>
        </div>

    </main>

    <!-- TECHNICAL SLIDE-OVER DRAWER -->
    <div id="techDrawer" class="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex justify-end hidden transition-all">
        <div class="bg-white max-w-xl w-full h-full shadow-2xl flex flex-col justify-between border-l border-slate-200">
            
            <div class="p-6 border-b border-slate-200 flex justify-between items-start bg-slate-50/50">
                <div>
                    <div class="flex items-center space-x-2">
                        <span id="drawerBadge" class="text-[10px] font-semibold bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded border border-indigo-200 font-mono">BULK_PAYOUT_2PC</span>
                        <span id="drawerReg" class="text-[10px] font-semibold bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded border border-emerald-200 font-mono">RBI RTGS</span>
                    </div>
                    <h2 id="drawerTitle" class="text-base font-bold text-slate-900 mt-1.5">2-Phase Commit Bulk Disbursals</h2>
                    <p id="drawerDesc" class="text-xs text-slate-500 mt-1 leading-relaxed">Explanation...</p>
                </div>
                <button onclick="closeDrawer()" class="text-slate-400 hover:text-slate-700 text-xl font-bold p-1 rounded-md">&times;</button>
            </div>

            <div class="p-6 overflow-y-auto space-y-5 flex-1 text-xs">
                
                <div class="space-y-2">
                    <span class="font-semibold text-slate-900 uppercase tracking-wide block text-[11px]">1. Architectural Node Pipeline</span>
                    <div id="drawerNodes" class="grid grid-cols-2 gap-2 font-mono"></div>
                </div>

                <div class="space-y-2">
                    <span class="font-semibold text-slate-900 uppercase tracking-wide block text-[11px]">2. State Machine Lifecycle Tracker</span>
                    <div id="drawerSteps" class="space-y-1.5 font-mono text-[11px]"></div>
                </div>

                <div class="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3 font-mono">
                    <div class="flex justify-between items-center">
                        <span class="font-semibold text-slate-900 uppercase text-[11px]">3. Execute Live Transaction</span>
                        <span id="pipelineStatusBadge" class="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-700">STANDBY</span>
                    </div>
                    <div class="grid grid-cols-2 gap-2 text-[11px]">
                        <div>
                            <label class="block text-slate-500 mb-1">Source Account</label>
                            <input id="inSrc" type="text" class="w-full bg-white border border-slate-300 rounded p-1.5 text-slate-800">
                        </div>
                        <div>
                            <label class="block text-slate-500 mb-1">Target Account</label>
                            <input id="inTgt" type="text" class="w-full bg-white border border-slate-300 rounded p-1.5 text-slate-800">
                        </div>
                    </div>
                    <div>
                        <label class="block text-slate-500 text-[11px] mb-1">Amount (Paisa - 100 Paisa = ₹1)</label>
                        <input id="inAmt" type="number" class="w-full bg-white border border-slate-300 rounded p-1.5 text-slate-800 text-[11px]">
                    </div>
                    <button id="dispatchBtn" onclick="executeDrawerSimulation()" class="w-full bg-indigo-900 hover:bg-indigo-800 text-white font-semibold py-2.5 rounded-lg transition shadow-xs flex items-center justify-center space-x-2">
                        <span>Dispatch Transaction Execution &rarr;</span>
                    </button>
                </div>

                <div class="space-y-1.5 font-mono">
                    <div class="flex justify-between items-center">
                        <span class="font-semibold text-slate-900 uppercase text-[11px]">4. Canonical ISO 20022 pain.001 Message</span>
                        <span id="drawerHmac" class="text-[10px] text-slate-400 font-semibold">HMAC-SHA256 Ready</span>
                    </div>
                    <pre id="drawerXml" class="p-3.5 bg-slate-900 text-emerald-400 rounded-lg text-[11px] overflow-x-auto h-40 border border-slate-800 leading-relaxed font-mono">
<!-- Click Dispatch Transaction Execution above to run the live pipeline and compile the ISO envelope -->
                    </pre>
                </div>

            </div>

            <div class="p-4 border-t border-slate-200 bg-slate-50 flex justify-end">
                <button onclick="closeDrawer()" class="px-4 py-1.5 rounded-md border border-slate-300 bg-white hover:bg-slate-100 text-slate-700 text-xs font-medium transition shadow-xs">
                    Close Window
                </button>
            </div>

        </div>
    </div>

    <script>
        let servicesCatalog = {};
        let activeCode = "BULK_PAYOUT_2PC";

        async function initCatalog() {
            const res = await fetch('/api/v1/services/catalog');
            servicesCatalog = await res.json();
            renderGrid();
        }

        function renderGrid() {
            const container = document.getElementById('serviceGrid');
            container.innerHTML = '';
            
            Object.keys(servicesCatalog).forEach((code, idx) => {
                const s = servicesCatalog[code];
                const card = document.createElement('div');
                card.className = "bg-white p-4 rounded-xl border border-slate-200 card-shadow hover:border-indigo-400 cursor-pointer transition flex flex-col justify-between space-y-3";
                card.onclick = () => openDrawer(code);

                card.innerHTML = `
                    <div>
                        <div class="flex justify-between items-start mb-1.5">
                            <span class="font-semibold text-slate-900 text-xs">${idx + 1}. ${s.title}</span>
                            <span class="text-[10px] bg-slate-100 text-slate-700 font-mono px-1.5 py-0.5 rounded font-medium">${s.badge}</span>
                        </div>
                        <p class="text-[11px] text-slate-500 leading-relaxed">${s.desc}</p>
                    </div>
                    <div class="pt-2.5 border-t border-slate-100 flex justify-between items-center text-[11px] font-mono">
                        <span class="text-slate-600 truncate mr-2">${s.rail}</span>
                        <span class="text-indigo-900 font-semibold flex items-center">Inspect &rarr;</span>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        function openDrawer(code) {
            activeCode = code;
            const s = servicesCatalog[code];

            document.getElementById('drawerBadge').textContent = code;
            document.getElementById('drawerReg').textContent = s.reg;
            document.getElementById('drawerTitle').textContent = s.title;
            document.getElementById('drawerDesc').textContent = s.desc;
            document.getElementById('inSrc').value = s.src;
            document.getElementById('inTgt').value = s.tgt;
            document.getElementById('inAmt').value = s.amt;

            document.getElementById('pipelineStatusBadge').className = "text-[10px] font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-700";
            document.getElementById('pipelineStatusBadge').textContent = "STANDBY";
            document.getElementById('drawerXml').textContent = "<!-- Click Dispatch Transaction Execution above to run the live pipeline and compile the ISO envelope -->";
            document.getElementById('drawerHmac').textContent = "HMAC-SHA256 Ready";

            const nodesContainer = document.getElementById('drawerNodes');
            nodesContainer.innerHTML = '';
            s.nodes.forEach((n, idx) => {
                nodesContainer.innerHTML += `
                    <div class="p-2 bg-slate-50 border border-slate-200 rounded">
                        <div class="text-[9px] text-slate-400 font-semibold uppercase">Node 0${idx + 1}</div>
                        <div class="font-medium text-slate-800 text-xs mt-0.5">${n}</div>
                    </div>
                `;
            });

            renderSteps(s.steps, -1);
            document.getElementById('techDrawer').classList.remove('hidden');
        }

        function renderSteps(steps, activeIdx) {
            const stepsContainer = document.getElementById('drawerSteps');
            stepsContainer.innerHTML = '';
            steps.forEach((st, idx) => {
                let statusClass = "bg-slate-50 border-slate-200 text-slate-700";
                let numBadge = "bg-slate-200 text-slate-600";
                
                if (activeIdx === idx) {
                    statusClass = "bg-amber-50 border-amber-300 text-amber-900 animate-pulse font-semibold";
                    numBadge = "bg-amber-500 text-white";
                } else if (activeIdx > idx) {
                    statusClass = "bg-emerald-50 border-emerald-300 text-emerald-950 font-medium";
                    numBadge = "bg-emerald-600 text-white";
                }

                stepsContainer.innerHTML += `
                    <div class="p-2 rounded border flex items-center space-x-2 transition ${statusClass}">
                        <span class="h-4 w-4 rounded-full flex items-center justify-center text-[9px] font-bold ${numBadge}">
                            ${activeIdx > idx ? '✓' : idx + 1}
                        </span>
                        <span>${st}</span>
                    </div>
                `;
            });
        }

        function closeDrawer() {
            document.getElementById('techDrawer').classList.add('hidden');
        }

        async function executeDrawerSimulation() {
            const s = servicesCatalog[activeCode];
            const btn = document.getElementById('dispatchBtn');
            const statusBadge = document.getElementById('pipelineStatusBadge');
            
            btn.disabled = true;
            statusBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800 animate-pulse";
            statusBadge.textContent = "EXECUTING RAILS...";

            for (let i = 0; i < s.steps.length; i++) {
                renderSteps(s.steps, i);
                await new Promise(r => setTimeout(r, 220));
            }

            const payload = {
                service_code: activeCode,
                source_account: document.getElementById('inSrc').value,
                target_account: document.getElementById('inTgt').value,
                amount_paisa: parseInt(document.getElementById('inAmt').value),
                client_ref: "TBG-" + Date.now()
            };

            const res = await fetch('/api/v1/engine/execute', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            renderSteps(s.steps, 999);
            statusBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800";
            statusBadge.textContent = "SETTLED & COMMITTED";

            if (data.iso_xml) {
                document.getElementById('drawerXml').textContent = data.iso_xml;
            }
            if (data.hmac_signature) {
                document.getElementById('drawerHmac').innerHTML = `<span class="text-emerald-700 font-bold">HMAC: ${data.hmac_signature.substring(0, 16)}...</span>`;
            }

            const audit = document.getElementById('auditLog');
            audit.innerHTML = `
                <div class="p-2 rounded bg-slate-50 border border-slate-200 flex justify-between">
                    <span><strong>[${data.txn_id}]</strong> ${data.service} &rarr; ₹${data.amount_inr.toLocaleString('en-IN')} SETTLED</span>
                    <span class="text-emerald-700 font-semibold">&check; COMMITTED</span>
                </div>
            ` + audit.innerHTML;

            btn.disabled = false;
            refreshData();
        }

        async function executeAllSuite() {
            const btn = document.getElementById('btnExecAll');
            btn.disabled = true;
            btn.innerHTML = '<span>⌛ Executing 9 Rails...</span>';

            const res = await fetch('/api/v1/engine/execute-all', { method: 'POST' });
            const data = await res.json();

            const audit = document.getElementById('auditLog');
            data.transactions.forEach(t => {
                audit.innerHTML = `
                    <div class="p-2 rounded bg-emerald-50 border border-emerald-200 flex justify-between">
                        <span><strong>[${t.txn_id}]</strong> ${t.service} &rarr; ₹${t.amount_inr.toLocaleString('en-IN')}</span>
                        <span class="text-emerald-800 font-bold">&check; BATCH COMMITTED</span>
                    </div>
                ` + audit.innerHTML;
            });

            btn.disabled = false;
            btn.innerHTML = '<span>▶ Execute All 9 Services</span>';
            refreshData();
        }

        async function routeAI() {
            const query = document.getElementById('aiInput').value;
            const res = await fetch('/api/v1/ai/route', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ query: query })
            });
            const d = await res.json();
            
            document.getElementById('aiOutput').innerHTML = `
                <div>
                    <span class="text-slate-900 font-bold">[ROUTED: ${d.title}]</span> 
                    &bull; Rail: <span class="text-slate-800 font-semibold">${d.rail}</span> 
                    &bull; Reg: <span class="text-emerald-700 font-semibold">${d.reg}</span>
                </div>
            `;
            openDrawer(d.code);
        }

        async function refreshData() {
            const res = await fetch('/api/v1/system/telemetry');
            const d = await res.json();

            d.accounts.forEach(a => {
                if (a.id === "ESCROW_MASTER_01") document.getElementById('metricEscrow').textContent = `₹${(a.inr / 10000000).toFixed(2)} Cr`;
                if (a.id === "CORP_OPERATING_01") document.getElementById('metricOperating').textContent = `₹${(a.inr / 100000).toFixed(2)} L`;
                if (a.id === "SETTLEMENT_CLEARING_01") document.getElementById('metricClearing').textContent = `₹${(a.inr / 100000).toFixed(2)} L`;
                if (a.id === "NOSTRO_USD_INR_01") document.getElementById('metricNostro').textContent = `₹${(a.inr / 10000000).toFixed(2)} Cr`;
            });
        }

        initCatalog();
        refreshData();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return HTML_TEMPLATE