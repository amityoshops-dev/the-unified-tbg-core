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
<div class="tbg-sub">Institutional Payment & Ledger Orchestration Workbench Â· Enterprise Demo Build</div>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs([
    "Command Center","Simulator","Products","Architecture","API Lab","API Docs",
    "Postman","PRD","LLM Lab","Sandbox","Audit"
])

with tabs[0]:
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Escrow Trust Pool","â‚¹14,920,000")
    c2.metric("Treasury Float","â‚¹7,349,150")
    c3.metric("2PC Atomic Pool","â‚¹4,975,000")
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
        st.markdown(f'<div class="step"><b>{n} Â· {title}</b><br>{desc}</div>', unsafe_allow_html=True)

with tabs[1]:
    st.subheader("Transaction Simulator")
    req = st.text_area("Business requirement", value="Client needs to debit â‚¹10,000 loan EMI every month on the 5th via bank mandate", height=90)
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
        st.success(f"{r['status']} Â· {r['transaction_id']}")
        st.write(f"Intent: **{r['intent']}** | Rail: **{r['rail']}** | Pool: **{r['pool']}**")
        st.subheader("Execution trace")
        for e in r["audit"]:
            st.markdown(f"**{e['event']}** Â· `{e['state']}` â€” {e['detail']}")

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
        â†“
Requirement Normalizer
        â†“
AI / Rules Intent Layer
        â†“
Rail Candidate Engine
        â†“
Deterministic Policy & Eligibility
        â†“
Risk / Limits / Idempotency
        â†“
Liquidity & Pool Controller
        â†“
Transaction Orchestrator
        â†“
Rail Adapter Layer
        â†“
Provider / Sandbox
        â†“
State Machine
        â†“
Double-Entry Ledger
        â†“
Settlement / Pool Movement
        â†“
Reconciliation
        â†“
Exception & Retry
        â†“
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
4. Run Health â†’ Route Requirement â†’ Execute Simulation.
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
        st.write(f"**{name}** â€” `{status}`")
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
