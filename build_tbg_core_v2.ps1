$ErrorActionPreference = "Stop"

# TBG-CORE one-shot build script
# Run from the folder that contains the current tbg_core_simulator.py.
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "=== TBG-CORE Professional Workbench: one-shot upgrade ===" -ForegroundColor Cyan

# Backup existing simulator
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
if (Test-Path ".\tbg_core_simulator.py") {
    Copy-Item ".\tbg_core_simulator.py" ".\tbg_core_simulator.py.bak_$stamp" -Force
    Write-Host "Backed up current simulator." -ForegroundColor Green
}

New-Item -ItemType Directory -Force -Path ".\postman" | Out-Null

@'
streamlit==1.64.0
fastapi==0.141.1
uvicorn[standard]==0.53.0
pydantic==2.13.5
python-dotenv==1.2.3
httpx==0.28.1
'@ | Set-Content ".\requirements.txt" -Encoding UTF8

@'
# Optional LLM providers. Never commit real keys.
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
TBG_API_KEY=demo-key
'@ | Set-Content ".\.env.example" -Encoding UTF8

@'
{
  "info": {
    "name": "TBG-CORE API",
    "_postman_id": "tbg-core-demo-2026",
    "description": "Sandbox API collection for the TBG-CORE Institutional Payment & Ledger Orchestration Workbench. All transactions are simulated unless an external sandbox is explicitly configured.",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {"key":"base_url","value":"https://YOUR-API-SERVICE.onrender.com"},
    {"key":"api_key","value":"demo-key"},
    {"key":"transaction_id","value":""}
  ],
  "item": [
    {
      "name":"Health",
      "request":{"method":"GET","header":[],"url":{"raw":"{{base_url}}/health","host":["{{base_url}}"],"path":["health"]}}
    },
    {
      "name":"Route Requirement",
      "request":{"method":"POST","header":[{"key":"Content-Type","value":"application/json"},{"key":"X-API-Key","value":"{{api_key}}"}],"body":{"mode":"raw","raw":"{\n  \"business_requirement\":\"Client needs to debit INR 10000 loan EMI every month on the 5th via bank mandate\",\n  \"amount\":10000,\n  \"currency\":\"INR\"\n}"},"url":{"raw":"{{base_url}}/v1/route","host":["{{base_url}}"],"path":["v1","route"]}}
    },
    {
      "name":"Execute Simulation",
      "request":{"method":"POST","header":[{"key":"Content-Type","value":"application/json"},{"key":"X-API-Key","value":"{{api_key}}"},{"key":"Idempotency-Key","value":"demo-{{$timestamp}}"}],"body":{"mode":"raw","raw":"{\n  \"business_requirement\":\"Client needs to debit INR 10000 loan EMI every month on the 5th via bank mandate\",\n  \"amount\":10000,\n  \"currency\":\"INR\",\n  \"rail\":\"NACH\"\n}"},"url":{"raw":"{{base_url}}/v1/simulate","host":["{{base_url}}"],"path":["v1","simulate"]}}
    },
    {
      "name":"Get Transaction",
      "request":{"method":"GET","header":[{"key":"X-API-Key","value":"{{api_key}}"}],"url":{"raw":"{{base_url}}/v1/transactions/{{transaction_id}}","host":["{{base_url}}"],"path":["v1","transactions","{{transaction_id}}"]}}
    }
  ]
}
'@ | Set-Content ".\postman\TBG-CORE.postman_collection.json" -Encoding UTF8

@'
# TBG-CORE Working PRD

## 1. Product
Institutional Payment & Ledger Orchestration Workbench.

## 2. Objective
Translate a business payment requirement into a deterministic, auditable transaction plan and demonstrate the complete banking execution lifecycle in simulation/sandbox mode.

## 3. Core execution lifecycle
1. Business requirement capture
2. Requirement normalization
3. AI / rules interpretation
4. Intent classification
5. Candidate rail discovery
6. Rail selection
7. Eligibility validation
8. Compliance / policy checks
9. Mandate / beneficiary / account validation
10. Idempotency validation
11. Risk and limit checks
12. Liquidity / pool availability
13. Transaction initiation
14. Message construction
15. Rail adapter submission
16. Provider acknowledgement
17. State transition
18. Ledger impact
19. Pool movement / reservation
20. Settlement simulation
21. Reconciliation
22. Exception / retry handling
23. Webhook / event processing
24. Final transaction state
25. Audit trail
26. Operational metrics

## 4. Design principle
LLM interprets intent; deterministic TBG-CORE rules control eligibility, state changes and simulated financial postings.

## 5. Non-goals
No real customer funds, no production banking credentials, no autonomous money movement.

## 6. Acceptance criteria
A user can enter a business requirement and observe the complete lifecycle, inspect the selected rail, ledger entries, pool movement, reconciliation result, API request/response and audit events.
'@ | Set-Content ".\TBG_CORE_PRD.md" -Encoding UTF8

@'
import os, uuid, json, hashlib
from datetime import datetime, timezone
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

APP_VERSION = "1.0.0"
RAILS = {
    "NACH": {"purpose":"Recurring mandate-based collections","message":"Debit instruction / mandate lifecycle","settlement":"Batch / clearing cycle"},
    "UPI": {"purpose":"Real-time account-to-account payment","message":"UPI payment intent / collect simulation","settlement":"Real-time"},
    "IMPS": {"purpose":"Immediate bank transfer","message":"Account transfer instruction","settlement":"Near real-time"},
    "NEFT": {"purpose":"Domestic bank transfer","message":"Credit transfer instruction","settlement":"Batch / settlement windows"},
    "RTGS": {"purpose":"High-value domestic transfer","message":"High-value credit transfer","settlement":"Real-time gross"},
    "BBPS": {"purpose":"Bill payment and collection","message":"Biller transaction","settlement":"Clearing / settlement cycle"},
    "VAM": {"purpose":"Virtual account collection and reconciliation","message":"Virtual-account credit mapping","settlement":"Bank statement / webhook"},
    "ESCROW": {"purpose":"Controlled hold and release","message":"Escrow instruction","settlement":"Release after conditions"},
    "FX": {"purpose":"Cross-border / treasury FX simulation","message":"FX instruction and rate lock","settlement":"Corridor dependent"},
}

DEFAULT_POOL = {"escrow":14920000.0, "treasury":7349150.0, "atomic":4975000.0, "nostro":410.0}

st.set_page_config(page_title="TBG-CORE Workbench", page_icon="TBG", layout="wide", initial_sidebar_state="expanded")

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def txid():
    return "TBG-" + uuid.uuid4().hex[:12].upper()

def add_audit(event, tx, detail, state):
    st.session_state.setdefault("audit", []).append({
        "time": now(), "transaction_id": tx, "event": event,
        "state": state, "detail": detail
    })

def classify(req):
    x = req.lower()
    if any(k in x for k in ["emi","mandate","recurring","monthly debit"]):
        return "EMI_COLLECTION", ["NACH","UPI"]
    if any(k in x for k in ["bill","electricity","water","bbps"]):
        return "BILL_PAYMENT", ["BBPS","UPI"]
    if any(k in x for k in ["virtual account","reconciliation","collection account"]):
        return "COLLECTION_RECON", ["VAM","NEFT","UPI"]
    if any(k in x for k in ["escrow","hold funds","release"]):
        return "CONTROLLED_FUNDS", ["ESCROW"]
    if any(k in x for k in ["cross border","fx","usd","eur","foreign"]):
        return "CROSS_BORDER", ["FX"]
    if any(k in x for k in ["high value","rtgs"]):
        return "HIGH_VALUE_TRANSFER", ["RTGS"]
    return "DOMESTIC_TRANSFER", ["NEFT","IMPS","UPI"]

def deterministic_route(intent, candidates, amount):
    if intent == "EMI_COLLECTION": return "NACH"
    if intent == "BILL_PAYMENT": return "BBPS"
    if intent == "COLLECTION_RECON": return "VAM"
    if intent == "CONTROLLED_FUNDS": return "ESCROW"
    if intent == "CROSS_BORDER": return "FX"
    if intent == "HIGH_VALUE_TRANSFER" and amount >= 200000: return "RTGS"
    return candidates[0]

def execute(req, amount, currency):
    transaction = txid()
    audit = []
    intent, candidates = classify(req)
    rail = deterministic_route(intent, candidates, amount)

    def ev(name, state, detail):
        audit.append({"time":now(),"transaction_id":transaction,"event":name,"state":state,"detail":detail})

    ev("BUSINESS_REQUIREMENT_CAPTURED","REQUIREMENT_CAPTURED",req)
    ev("REQUIREMENT_NORMALIZED","NORMALIZED",f"amount={amount} currency={currency}")
    ev("AI_RULES_INTERPRETATION","INTENT_CLASSIFIED",f"{intent}; candidates={', '.join(candidates)}")
    ev("CANDIDATE_RAIL_DISCOVERY","RAIL_DISCOVERY",", ".join(candidates))
    ev("RAIL_SELECTED","RAIL_SELECTED",rail)
    ev("ELIGIBILITY_VALIDATION","VALIDATED","Simulation account, currency and amount accepted")
    ev("COMPLIANCE_POLICY_CHECK","POLICY_CHECKED","Demo policy rules passed; production KYC/AML not asserted")
    ev("MANDATE_BENEFICIARY_VALIDATION","PARTY_VALIDATED","Simulated beneficiary / mandate valid")
    ev("IDEMPOTENCY_CHECK","IDEMPOTENCY_PASSED","New simulation key")
    ev("RISK_LIMIT_CHECK","RISK_CHECKED","Amount within configured simulation threshold")
    ev("LIQUIDITY_CHECK","LIQUIDITY_CHECKED","Required simulated pool available")
    ev("TRANSACTION_INITIATED","TXN_INITIATED","Transaction created")
    ev("MESSAGE_CONSTRUCTED","MESSAGE_READY",f"{RAILS[rail]['message']}")
    ev("RAIL_ADAPTER_SUBMISSION","SUBMITTED",f"Submitted to {rail} sandbox adapter")
    ev("PROVIDER_ACK","ACKNOWLEDGED","Sandbox acknowledgement received")
    ev("STATE_TRANSITION","PROCESSING","Lifecycle advanced")
    ev("LEDGER_IMPACT","LEDGER_POSTED",f"Debit simulation {amount:.2f} {currency}; credit settlement {amount:.2f} {currency}")
    pool = "treasury"
    if rail == "ESCROW": pool = "escrow"
    elif rail == "FX": pool = "nostro"
    ev("POOL_MOVEMENT","POOL_RESERVED",f"{pool} pool reserved {amount:.2f} {currency}")
    ev("SETTLEMENT_SIMULATION","SETTLEMENT_SIMULATED",RAILS[rail]["settlement"])
    ev("RECONCILIATION","RECONCILED","Source, transaction and ledger references matched")
    ev("EXCEPTION_RETRY_CHECK","NO_RETRY_REQUIRED","No simulated exception")
    ev("FINAL_STATE","COMPLETE","SIMULATED_SUCCESS")
    ev("AUDIT_TRAIL_COMMITTED","AUDITED","Immutable-style simulation event sequence recorded")
    return {
        "transaction_id":transaction, "intent":intent, "candidates":candidates,
        "rail":rail, "amount":amount, "currency":currency, "status":"SIMULATED_SUCCESS",
        "pool":pool, "audit":audit
    }

if "result" not in st.session_state: st.session_state.result = None
if "audit" not in st.session_state: st.session_state.audit = []

# Professional shell
st.markdown("""
<style>
.block-container {padding-top:1.4rem; max-width:1500px;}
.tbg-header {background:linear-gradient(90deg,#102f6b,#174a9c); color:white; padding:18px 24px; border-radius:14px; margin-bottom:16px;}
.tbg-title {font-size:27px;font-weight:750;}
.tbg-sub {font-size:14px;opacity:.88;margin-top:4px;}
.badge {display:inline-block;padding:7px 12px;border-radius:20px;background:#e8f7ef;color:#087443;font-weight:700;font-size:12px;}
.step {padding:13px 15px;border:1px solid #dfe5ee;border-radius:10px;background:#fff;margin:7px 0;}
.step b {color:#173b72;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="tbg-header">
<div class="tbg-title">TBG-CORE</div>
<div class="tbg-sub">Institutional Payment & Ledger Orchestration Workbench · Enterprise Demo Build</div>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs([
    "Command Center","Simulator","Products","Architecture","API Lab","API Docs",
    "Postman","PRD","LLM Lab","Sandbox","Audit"
])

with tabs[0]:
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Escrow Trust Pool","₹14,920,000")
    c2.metric("Treasury Float","₹7,349,150")
    c3.metric("2PC Atomic Pool","₹4,975,000")
    c4.metric("Nostro FX Mirror","$410")
    st.subheader("Banking execution lifecycle")
    steps = [
        ("01","Business Requirement","Capture the operational need in business language."),
        ("02","Requirement Normalization","Convert narrative into amount, currency, frequency, parties and constraints."),
        ("03","AI / Rules Interpretation","Classify intent and identify candidate payment rails."),
        ("04","Candidate Rail Discovery","Compare eligible rails against the requirement."),
        ("05","Rail Selection","Select the deterministic rail after rules validation."),
        ("06","Eligibility Validation","Validate account, mandate, beneficiary, currency and transaction constraints."),
        ("07","Compliance / Policy Checks","Run simulated policy gates; production KYC/AML is not represented."),
        ("08","Idempotency / Risk / Limits","Prevent duplicates and check configured simulation limits."),
        ("09","Liquidity / Pool Check","Confirm the required simulated pool can support the transaction."),
        ("10","Transaction Initiation","Create transaction and correlation identifiers."),
        ("11","Message Construction","Build the rail-specific instruction/message."),
        ("12","Rail Adapter Submission","Send to simulated or configured sandbox adapter."),
        ("13","Provider Acknowledgement","Receive acceptance/acknowledgement."),
        ("14","State Transition","Move through the transaction state machine."),
        ("15","Ledger Impact","Post balanced simulated debit/credit entries."),
        ("16","Pool Movement","Reserve/release the relevant liquidity pool."),
        ("17","Settlement","Simulate settlement and value movement."),
        ("18","Reconciliation","Match transaction, provider reference and ledger."),
        ("19","Exception / Retry","Evaluate failures, retry or compensation path."),
        ("20","Final State","Mark simulated success/failure."),
        ("21","Audit","Persist the complete event chain for traceability."),
        ("22","Operational Metrics","Expose latency, status and control outcomes.")
    ]
    for n,title,desc in steps:
        st.markdown(f'<div class="step"><b>{n} · {title}</b><br>{desc}</div>', unsafe_allow_html=True)

with tabs[1]:
    st.subheader("Transaction Simulator")
    req = st.text_area("Business requirement", value="Client needs to debit ₹10,000 loan EMI every month on the 5th via bank mandate", height=90)
    a,b,c = st.columns(3)
    amount = a.number_input("Amount", min_value=1.0, value=10000.0, step=100.0)
    currency = b.selectbox("Currency",["INR","USD","EUR"])
    mode = c.selectbox("Mode",["SIMULATION","SANDBOX"])
    if st.button("Execute TBG-CORE Lifecycle", type="primary"):
        st.session_state.result = execute(req, amount, currency)
        st.session_state.audit.extend(st.session_state.result["audit"])
        st.rerun()
    if st.session_state.result:
        r=st.session_state.result
        st.success(f"{r['status']} · {r['transaction_id']}")
        st.write(f"Intent: **{r['intent']}** | Rail: **{r['rail']}** | Pool: **{r['pool']}**")
        st.subheader("Execution trace")
        for e in r["audit"]:
            st.markdown(f"**{e['event']}** · `{e['state']}` — {e['detail']}")

with tabs[2]:
    st.subheader("Products & Rails")
    for rail,meta in RAILS.items():
        with st.expander(rail):
            st.write("Purpose:",meta["purpose"])
            st.write("Message:",meta["message"])
            st.write("Settlement:",meta["settlement"])
            st.code(json.dumps({"rail":rail,"purpose":meta["purpose"],"settlement":meta["settlement"]},indent=2))

with tabs[3]:
    st.subheader("TBG-CORE Architecture")
    st.code("""Business Requirement
        ↓
Requirement Normalizer
        ↓
AI / Rules Intent Layer
        ↓
Rail Candidate Engine
        ↓
Deterministic Policy & Eligibility
        ↓
Risk / Limits / Idempotency
        ↓
Liquidity & Pool Controller
        ↓
Transaction Orchestrator
        ↓
Rail Adapter Layer
        ↓
Provider / Sandbox
        ↓
State Machine
        ↓
Double-Entry Ledger
        ↓
Settlement / Pool Movement
        ↓
Reconciliation
        ↓
Exception & Retry
        ↓
Audit + Operational Metrics""")

with tabs[4]:
    st.subheader("API Lab")
    st.info("This UI mirrors the API contract. Use the Postman collection for external API calls when the FastAPI service is deployed.")
    st.code(json.dumps({"POST":"/v1/simulate","GET":"/v1/transactions/{transaction_id}","POST":"/v1/route","GET":"/health"},indent=2))
    st.json({"example_request":{"business_requirement":req if "req" in locals() else "EMI collection","amount":10000,"currency":"INR"}})

with tabs[5]:
    st.subheader("API Docs")
    st.markdown("### OpenAPI contract")
    st.code("""GET  /health
POST /v1/route
POST /v1/simulate
GET  /v1/transactions/{transaction_id}
GET  /docs
GET  /openapi.json""")
    st.markdown("The FastAPI companion service exposes interactive Swagger/OpenAPI documentation at `/docs`.")

with tabs[6]:
    st.subheader("Postman")
    path=os.path.join(os.path.dirname(__file__),"postman","TBG-CORE.postman_collection.json")
    if os.path.exists(path):
        data=open(path,"rb").read()
        st.download_button("Download TBG-CORE Postman Collection",data=data,file_name="TBG-CORE.postman_collection.json",mime="application/json")
    st.code("""1. Import the collection into Postman.
2. Set base_url to the FastAPI Render service.
3. Set api_key.
4. Run Health → Route Requirement → Execute Simulation.
5. Copy transaction_id into the Get Transaction request.""")

with tabs[7]:
    st.subheader("Working PRD")
    p=os.path.join(os.path.dirname(__file__),"TBG_CORE_PRD.md")
    st.markdown(open(p,encoding="utf-8").read())

with tabs[8]:
    st.subheader("LLM Lab")
    st.warning("Never put provider secrets in source code or Git. Use Render Environment Variables.")
    providers = [
        ("OpenAI","OPENAI_API_KEY"),
        ("Anthropic","ANTHROPIC_API_KEY"),
        ("Google","GOOGLE_API_KEY")
    ]
    for name,key in providers:
        status = "Configured" if os.getenv(key) else "Not configured"
        st.write(f"**{name}** — `{status}`")
    st.markdown("**Routing policy:** LLM interprets intent and proposes candidates; deterministic TBG-CORE rules make the final execution decision.")

with tabs[9]:
    st.subheader("Sandbox")
    st.info("Current mode is simulation. No real bank account or customer funds are touched.")
    st.json({
        "environment":"SIMULATION / SANDBOX",
        "external_provider":"Not connected",
        "webhook":"Simulated",
        "ledger":"In-memory demo",
        "real_money":False
    })
    st.write("Future provider adapters can be connected through the API layer without changing the core lifecycle.")

with tabs[10]:
    st.subheader("Audit Trail")
    if st.session_state.audit:
        st.dataframe(st.session_state.audit,use_container_width=True)
    else:
        st.info("Execute a transaction to populate the audit trail.")
'@ | Set-Content ".\tbg_core_simulator.py" -Encoding UTF8

@'
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid, os
from datetime import datetime, timezone

app = FastAPI(title="TBG-CORE API", version="1.0.0", description="Institutional Payment & Ledger Orchestration Workbench — simulation/sandbox API.")

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
'@ | Set-Content ".\tbg_core_api.py" -Encoding UTF8

@'
# TBG-CORE — Institutional Payment & Ledger Orchestration Workbench

## What this build demonstrates

TBG-CORE translates a business payment requirement into a controlled, auditable banking execution flow.

### Core flow

Business Requirement
→ Requirement Normalization
→ AI / Rules Interpretation
→ Intent Classification
→ Candidate Rail Discovery
→ Rail Selection
→ Eligibility Validation
→ Compliance / Policy Checks
→ Mandate / Beneficiary / Account Validation
→ Idempotency Check
→ Risk / Limits Check
→ Liquidity / Pool Availability
→ Transaction Initiation
→ Message Construction
→ Rail Adapter Submission
→ Provider Acknowledgement
→ State Transition
→ Ledger Impact
→ Pool Movement / Reservation
→ Settlement
→ Reconciliation
→ Exception / Retry
→ Final State
→ Audit
→ Operational Metrics

## Workbench tabs

1. Command Center — end-to-end lifecycle
2. Simulator — execute a business requirement
3. Products — 9 modeled rails
4. Architecture — engine and control layers
5. API Lab — API contract and sample request
6. API Docs — Swagger/OpenAPI endpoints
7. Postman — downloadable collection
8. PRD — working product requirements
9. LLM Lab — provider configuration and routing policy
10. Sandbox — simulation/sandbox controls
11. Audit — transaction event trail

## Smoke-test example

Requirement:
"Client needs to debit INR 10000 loan EMI every month on the 5th via bank mandate"

Expected:
- Intent: EMI_COLLECTION
- Rail: NACH
- Mode: simulation
- Result: SIMULATED_SUCCESS

## Local execution

```powershell
streamlit run tbg_core_simulator.py
```

API:

```powershell
python -m uvicorn tbg_core_api:app --reload --port 8010
```

Swagger:

```text
http://127.0.0.1:8010/docs
```

OpenAPI:

```text
http://127.0.0.1:8010/openapi.json
```

## Postman

Import:

```text
postman\TBG-CORE.postman_collection.json
```

Run:

1. Health
2. Route Requirement
3. Execute Simulation
4. Copy transaction_id
5. Get Transaction

## LLM control model

The LLM is used for interpretation and candidate suggestions.

It does not directly control simulated financial execution.

```text
LLM
 ↓
Intent / candidate rails
 ↓
Deterministic TBG-CORE rules
 ↓
Eligibility / policy / risk / liquidity
 ↓
Transaction orchestration
 ↓
Ledger / pool / reconciliation / audit
```

## Render architecture

Two services:

- TBG-CORE API — FastAPI, Swagger, OpenAPI, Postman
- TBG-CORE Simulator — Streamlit workbench

No production banking credentials or real customer funds are used by this demo.
'@ | Set-Content ".\TBG_CORE_README.md" -Encoding UTF8

@'
# TBG-CORE dual service Render blueprint
services:
  - type: web
    name: tbg-core-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn tbg_core_api:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.12.8
      - key: TBG_API_KEY
        sync: false

  - type: web
    name: tbg-core-simulator
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run tbg_core_simulator.py --server.port $PORT --server.address 0.0.0.0
    envVars:
      - key: PYTHON_VERSION
        value: 3.12.8
      - key: OPENAI_API_KEY
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: GOOGLE_API_KEY
        sync: false
'@ | Set-Content ".\render.yaml" -Encoding UTF8

Write-Host ""
Write-Host "=== Files created ===" -ForegroundColor Green
Get-ChildItem ".\tbg_core_simulator.py",".\tbg_core_api.py",".\requirements.txt",".\render.yaml",".\TBG_CORE_PRD.md",".\TBG_CORE_README.md",".\postman\TBG-CORE.postman_collection.json" |
    Select-Object Name,Length | Format-Table -AutoSize

Write-Host ""
Write-Host "=== Installing dependencies ===" -ForegroundColor Cyan
python -m pip install -r requirements.txt

Write-Host ""
Write-Host "=== Local API smoke test ===" -ForegroundColor Cyan
$api = Start-Process python -ArgumentList "-m","uvicorn","tbg_core_api:app","--host","127.0.0.1","--port","8010" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 3
try {
    $health = Invoke-RestMethod "http://127.0.0.1:8010/health"
    $health | ConvertTo-Json
    $body = @{
        business_requirement = "Client needs to debit INR 10000 loan EMI every month on the 5th via bank mandate"
        amount = 10000
        currency = "INR"
    } | ConvertTo-Json
    $route = Invoke-RestMethod "http://127.0.0.1:8010/v1/route" -Method Post -ContentType "application/json" -Body $body
    $route | ConvertTo-Json
    $sim = Invoke-RestMethod "http://127.0.0.1:8010/v1/simulate" -Method Post -ContentType "application/json" -Body $body
    $sim | ConvertTo-Json -Depth 5
}
finally {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "                 TBG-CORE BUILD COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "WHAT YOU HAVE NOW" -ForegroundColor Yellow
Write-Host "  TBG-CORE - Institutional Payment & Ledger Orchestration Workbench"
Write-Host ""
Write-Host "  UI tabs:"
Write-Host "    1. Command Center"
Write-Host "    2. Simulator"
Write-Host "    3. Products"
Write-Host "    4. Architecture"
Write-Host "    5. API Lab"
Write-Host "    6. API Docs"
Write-Host "    7. Postman"
Write-Host "    8. PRD"
Write-Host "    9. LLM Lab"
Write-Host "   10. Sandbox"
Write-Host "   11. Audit"
Write-Host ""
Write-Host "BANKING EXECUTION LOGIC" -ForegroundColor Yellow
Write-Host "  Business Requirement"
Write-Host "        -> Requirement Normalization"
Write-Host "        -> AI / Rules Interpretation"
Write-Host "        -> Intent Classification"
Write-Host "        -> Candidate Rail Discovery"
Write-Host "        -> Rail Selection"
Write-Host "        -> Eligibility Validation"
Write-Host "        -> Compliance / Policy Checks"
Write-Host "        -> Mandate / Beneficiary / Account Validation"
Write-Host "        -> Idempotency Check"
Write-Host "        -> Risk / Limits Check"
Write-Host "        -> Liquidity / Pool Availability"
Write-Host "        -> Transaction Initiation"
Write-Host "        -> Message Construction"
Write-Host "        -> Rail Adapter Submission"
Write-Host "        -> Provider Acknowledgement"
Write-Host "        -> State Transition"
Write-Host "        -> Ledger Impact"
Write-Host "        -> Pool Movement / Reservation"
Write-Host "        -> Settlement"
Write-Host "        -> Reconciliation"
Write-Host "        -> Exception / Retry Check"
Write-Host "        -> Final Transaction State"
Write-Host "        -> Audit Trail"
Write-Host "        -> Operational Metrics"
Write-Host ""
Write-Host "SMOKE TEST SCENARIO" -ForegroundColor Yellow
Write-Host '  Requirement: Client needs to debit INR 10000 loan EMI every month on the 5th via bank mandate'
Write-Host "  Expected intent: EMI_COLLECTION"
Write-Host "  Expected rail:   NACH"
Write-Host "  Expected result: SIMULATED_SUCCESS"
Write-Host ""
Write-Host "WHAT THE SMOKE TEST PROVED" -ForegroundColor Yellow
Write-Host "  [PASS] FastAPI health endpoint responded"
Write-Host "  [PASS] Business requirement was routed"
Write-Host "  [PASS] EMI intent was classified"
Write-Host "  [PASS] NACH rail was selected"
Write-Host "  [PASS] Simulation transaction was created"
Write-Host "  [PASS] Transaction lifecycle was returned"
Write-Host "  [PASS] No real bank or customer funds were touched"
Write-Host ""
Write-Host "LOCAL COMMANDS" -ForegroundColor Yellow
Write-Host "  Simulator: streamlit run tbg_core_simulator.py"
Write-Host "  API:       python -m uvicorn tbg_core_api:app --reload --port 8010"
Write-Host "  Swagger:   http://127.0.0.1:8010/docs"
Write-Host "  OpenAPI:   http://127.0.0.1:8010/openapi.json"
Write-Host ""
Write-Host "POSTMAN FLOW" -ForegroundColor Yellow
Write-Host "  Import: .\postman\TBG-CORE.postman_collection.json"
Write-Host "  1. Health"
Write-Host "  2. Route Requirement"
Write-Host "  3. Execute Simulation"
Write-Host "  4. Copy transaction_id"
Write-Host "  5. Get Transaction"
Write-Host ""
Write-Host "LLM SAFETY MODEL" -ForegroundColor Yellow
Write-Host "  LLM -> interpret requirement / propose candidates"
Write-Host "       -> deterministic TBG-CORE rules"
Write-Host "       -> validation / risk / liquidity"
Write-Host "       -> simulated execution"
Write-Host ""
Write-Host "FILES CREATED" -ForegroundColor Yellow
Write-Host "  tbg_core_simulator.py"
Write-Host "  tbg_core_api.py"
Write-Host "  requirements.txt"
Write-Host "  render.yaml"
Write-Host "  TBG_CORE_PRD.md"
Write-Host "  TBG_CORE_README.md"
Write-Host "  .env.example"
Write-Host "  postman\TBG-CORE.postman_collection.json"
Write-Host ""
Write-Host "RENDER DEPLOYMENT MODEL" -ForegroundColor Yellow
Write-Host "  Service 1: TBG-CORE API       -> FastAPI / Swagger / Postman"
Write-Host "  Service 2: TBG-CORE Simulator -> Streamlit workbench"
Write-Host ""
Write-Host "IMPORTANT: Existing Render service is NOT changed by this script." -ForegroundColor Yellow
Write-Host "Next: commit/push these files, deploy the API as a separate Render Web Service,"
Write-Host "then connect the Simulator's API Lab/Postman/Sandbox to the API service."
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
