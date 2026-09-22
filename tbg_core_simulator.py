"""
TBG-CORE Engine Simulator
=========================

An educational, self-contained SIMULATION of a 9-rail payments/treasury
orchestration engine (escrow, disbursals, virtual accounts, e-NACH, sweeps,
cross-border FX, account-aggregator consent, marketplace split, statutory
tax escrow), with:

  * a small in-memory ledger that actually moves numbers between pools
    (so every "Execute" button has a real, inspectable effect),
  * a natural-language "AI Agent Rail Routing Console" that can be backed
    by a real Claude model (via the Anthropic SDK) or, with no API key,
    falls back to a transparent rule-based keyword router,
  * a light ("daylight") professional dashboard UI built with Streamlit,
  * a running transaction ledger you can inspect/export.

IMPORTANT: This is a DEMO / SIMULATION only. It does not connect to any
real bank, NPCI, RTGS/IMPS, SWIFT, or Account Aggregator infrastructure.
All balances, mandates, FX rates and "bank acknowledgements" are generated
in-process for demonstration purposes.

--------------------------------------------------------------------------
SETUP
--------------------------------------------------------------------------
    pip install streamlit pandas anthropic
    streamlit run tbg_core_simulator.py

The Anthropic SDK / API key are optional. Without them, the routing
console still works fully using the built-in rule-based engine.
--------------------------------------------------------------------------
"""

import json
import random
import time
import uuid
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

try:
    import anthropic
    ANTHROPIC_SDK_AVAILABLE = True
except ImportError:
    ANTHROPIC_SDK_AVAILABLE = False

DEFAULT_MODEL = "claude-sonnet-5"

# ============================================================================
# PAGE CONFIG + LIGHT / "DAYLIGHT" THEME
# ============================================================================

st.set_page_config(
    page_title="TBG-CORE Engine Simulator",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .stApp { background-color: #F4F6FA; }
    #MainMenu, footer { visibility: hidden; }

    .tbg-header {
        display: flex; align-items: center; justify-content: space-between;
        background: #FFFFFF; border: 1px solid #E4E8F0; border-radius: 14px;
        padding: 18px 26px; margin-bottom: 18px;
        box-shadow: 0 1px 3px rgba(16,24,40,0.06);
    }
    .tbg-logo-box {
        display:flex; align-items:center; gap: 14px;
    }
    .tbg-logo-badge {
        background: linear-gradient(135deg,#0F2A5C,#1B4CA0); color:white;
        font-weight:800; font-size:15px; padding: 10px 12px; border-radius: 10px;
        letter-spacing: 0.5px;
    }
    .tbg-title { font-size: 20px; font-weight: 700; color:#0F2A44; margin:0; }
    .tbg-subtitle { font-size: 12.5px; color:#67728A; margin:0; }
    .tbg-pill {
        background:#E7F8EF; color:#0F7A45; border:1px solid #B8ECD0;
        padding:6px 14px; border-radius:999px; font-size:12.5px; font-weight:700;
        white-space:nowrap;
    }

    .tbg-metric {
        background:#FFFFFF; border:1px solid #E4E8F0; border-radius:14px;
        padding:16px 18px; box-shadow: 0 1px 3px rgba(16,24,40,0.05);
    }
    .tbg-metric-label { font-size:11.5px; color:#8792A6; font-weight:700; text-transform:uppercase; letter-spacing:0.04em;}
    .tbg-metric-value { font-size:22px; color:#0F2A44; font-weight:800; margin-top:2px;}
    .tbg-metric-sub { font-size:11.5px; color:#8B98B0; margin-top:4px;}

    .tbg-card-tag {
        display:inline-block; color:white; font-size:10.5px; font-weight:700;
        padding:3px 9px; border-radius:999px; letter-spacing:0.02em;
    }
    .tbg-card-title { font-size:15.5px; font-weight:700; color:#0F2A44; margin: 6px 0 2px 0;}
    .tbg-card-desc { font-size:12.5px; color:#6B7690; line-height:1.4; margin-bottom:10px;}

    div[data-testid="stStatusWidget"] { background:#FFFFFF; }
    .stButton>button {
        border-radius:8px; font-weight:600; border:1px solid #D6DCE8;
    }
    .stButton>button[kind="primary"] {
        background:#0F2A5C; border-color:#0F2A5C;
    }
    section[data-testid="stSidebar"] { background:#FBFCFE; border-right:1px solid #E4E8F0;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def fmt_inr(x):
    return f"\u20b9{x:,.0f}"


def fmt_usd(x):
    return f"${x:,.2f}"


def badge(text, color):
    return f'<span class="tbg-card-tag" style="background:{color};">{text}</span>'


TAG_COLORS = {
    "2-of-3 Safe": "#2563EB",
    "IMPS/RTGS": "#16A34A",
    "Smart VAN": "#7C3AED",
    "NPCI Mandate": "#EA580C",
    "ZBA/TBA": "#0891B2",
    "SWIFT MT103": "#DB2777",
    "Consent Rail": "#4338CA",
    "Instant Split": "#CA8A04",
    "PA/PG Safe": "#9333EA",
}

# ============================================================================
# SERVICE CATALOG (drives the routing agent + the 3x3 grid)
# ============================================================================

SERVICE_DEFS = [
    {
        "id": "escrow", "name": "Escrow Multi-Sig", "tag": "2-of-3 Safe",
        "desc": "Milestone trust custody. Locks buyer funds in a segregated nodal pool until cryptographic signoff.",
        "keywords": ["escrow", "milestone", "multi-sig", "multisig", "trust", "custody", "buyer funds", "signoff"],
    },
    {
        "id": "2pc", "name": "2PC Bulk Disbursals", "tag": "IMPS/RTGS",
        "desc": "Two-phase balance reservation clearing that prevents duplicate debits during upstream bank timeouts.",
        "keywords": ["disbursal", "disburse", "payout", "2pc", "two-phase", "bulk payment", "rtgs", "imps"],
    },
    {
        "id": "va", "name": "Virtual Accounts (CMS)", "tag": "Smart VAN",
        "desc": "Dynamic sub-account routing that matches incoming RTGS/NEFT credit straight into invoice ledgers.",
        "keywords": ["virtual account", "van", "collection", "invoice", "credit", "cms", "reconcile", "reconciliation"],
    },
    {
        "id": "enach", "name": "e-NACH Standing Orders", "tag": "NPCI Mandate",
        "desc": "Automated recurring debits with NPCI mandate registration, presentation and batch processing.",
        "keywords": ["nach", "mandate", "emi", "recurring", "standing order", "debit", "loan", "installment", "monthly"],
    },
    {
        "id": "sweep", "name": "Liquidity Sweep Pool", "tag": "ZBA/TBA",
        "desc": "Automated end-of-day, multi-entity balance concentration sweeps into a master pool for yield.",
        "keywords": ["sweep", "liquidity", "zba", "tba", "concentration", "eod", "end of day", "idle balance"],
    },
    {
        "id": "fx", "name": "Cross-Border FX Nostro", "tag": "SWIFT MT103",
        "desc": "Multi-currency cross-border trade settlement with automated FX conversion and mirror ledgering.",
        "keywords": ["fx", "forex", "cross-border", "nostro", "swift", "remittance", "currency", "usd", "export", "import"],
    },
    {
        "id": "aa", "name": "Account Aggregator Consent Flow", "tag": "Consent Rail",
        "desc": "Consent-backed financial data pull via Account Aggregator for algorithmic, real-time underwriting.",
        "keywords": ["account aggregator", "aa", "consent", "underwriting", "data pull", "kyc", "credit assessment"],
    },
    {
        "id": "split", "name": "Marketplace Split", "tag": "Instant Split",
        "desc": "Programmatic revenue splitting with automated platform commission sequestering prior to payout.",
        "keywords": ["marketplace", "split", "commission", "seller payout", "platform fee", "gross transaction"],
    },
    {
        "id": "gst", "name": "Statutory Tax Escrow", "tag": "PA/PG Safe",
        "desc": "Automated 18% GST liability sequestering into nodal escrow sub-ledgers compliant with RBI directions.",
        "keywords": ["gst", "tax", "statutory", "liability", "compliance", "rbi"],
    },
]
SERVICE_BY_ID = {s["id"]: s for s in SERVICE_DEFS}

STEP_FLOWS = {
    "escrow_lock": [
        "Validate milestone trigger conditions",
        "Open segregated nodal escrow sub-ledger",
        "Lock buyer funds into Escrow Trust Pool",
        "Emit escrow-hold confirmation",
    ],
    "escrow_release": [
        "Broadcast signature request to 3 authorized signatories",
        "Collect cryptographic signoffs (2-of-3 threshold)",
        "Release funds from Escrow Trust Pool to beneficiary",
        "Close milestone and archive audit trail",
    ],
    "2pc": [
        "Phase 1: reserve balance from Treasury Float into 2PC Atomic Pool",
        "Validate beneficiary account (simulated penny-drop)",
        "Phase 2: dispatch commit instruction to IMPS/RTGS rail",
        "Await upstream bank acknowledgement",
        "Finalize commit, or roll back the reservation on timeout",
    ],
    "va": [
        "Generate dynamic Virtual Account Number (VAN)",
        "Map VAN to invoice / customer sub-ledger",
        "Detect simulated incoming RTGS/NEFT credit",
        "Auto-reconcile credit against open invoice",
        "Post to sub-ledger with zero recon variance",
    ],
    "enach_register": [
        "Validate mandate amount, frequency and start date",
        "Register mandate with NPCI e-NACH registry (simulated)",
        "Await debtor bank authorization (simulated auto-approve)",
        "Activate mandate and schedule next debit date",
    ],
    "enach_trigger": [
        "Fetch active mandate from registry",
        "Present debit instruction in NPCI presentation cycle",
        "Await destination bank response (simulated)",
        "Post successful debit to Treasury Float",
        "Advance mandate to next due date",
    ],
    "sweep": [
        "Compute EOD balances across 4 linked sub-accounts (ZBA/TBA)",
        "Apply sweep-in threshold per account",
        "Concentrate surplus into master Treasury Float",
        "Post consolidated sweep entries",
        "Confirm zero uncommitted balance remaining",
    ],
    "fx": [
        "Lock indicative USD/INR spot rate",
        "Validate Nostro account coverage",
        "Generate simulated SWIFT MT103-style remittance reference",
        "Debit INR settlement leg from Treasury Float",
        "Credit Nostro FX Mirror in destination currency",
    ],
    "aa": [
        "Dispatch Account Aggregator consent request (simulated)",
        "Confirm customer consent artefact",
        "Pull financial data bundle via consent rail",
        "Run algorithmic underwriting scoring on retrieved data",
        "Store consent + pull audit trail",
    ],
    "split": [
        "Receive gross marketplace transaction amount",
        "Compute platform commission and seller payout split",
        "Post commission entry to Treasury Float",
        "Post seller payout entry to Escrow Trust Pool",
        "Confirm instant split settlement",
    ],
    "gst": [
        "Compute 18% GST liability on transaction amount",
        "Sequester GST portion into statutory escrow sub-ledger",
        "Tag entry with PA/PG statutory compliance reference",
        "Reserve balance pending remittance due date",
    ],
}

# ============================================================================
# LEDGER + SESSION STATE
# ============================================================================

class Ledger:
    """A tiny in-memory pool ledger. Not real accounting, just enough
    structure to make every simulated action have a visible, consistent
    effect on the four headline pools."""

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
                f"Insufficient balance in {src.replace('_',' ')}: "
                f"available {fmt_inr(self.accounts.get(src,0))}, required {fmt_inr(amount)}"
            )
        self.accounts[src] -= amount
        self.accounts[dst] = self.accounts.get(dst, 0) + amount


def init_state():
    if "ledger" not in st.session_state:
        st.session_state.ledger = Ledger()
    if "log" not in st.session_state:
        st.session_state.log = []
    if "mandates" not in st.session_state:
        st.session_state.mandates = {}
    if "route_result" not in st.session_state:
        st.session_state.route_result = None
    if "started_at" not in st.session_state:
        st.session_state.started_at = datetime.now()


def reset_state():
    for k in ["ledger", "log", "mandates", "route_result"]:
        if k in st.session_state:
            del st.session_state[k]
    init_state()


init_state()
ledger: Ledger = st.session_state.ledger


def new_txn_id():
    return f"TBG-{uuid.uuid4().hex[:10].upper()}"


def log_txn(service_name, action, amount, currency, status, detail=""):
    st.session_state.log.insert(0, {
        "Txn ID": new_txn_id(),
        "Time": datetime.now().strftime("%H:%M:%S"),
        "Rail": service_name,
        "Action": action,
        "Amount": f"{fmt_usd(amount) if currency=='USD' else fmt_inr(amount)}",
        "Status": status,
        "Detail": detail,
    })


def run_process(label, steps, effect_fn):
    """Render a step-by-step 'how it's actually processed' animation,
    then apply the real ledger effect and report outcome."""
    with st.status(f"Processing \u2014 {label}", expanded=True) as status:
        for i, step in enumerate(steps, 1):
            st.write(f"**Step {i}.** {step}")
            time.sleep(0.28)
        try:
            result = effect_fn()
            status.update(label=f"{label} \u2014 Completed", state="complete")
            return True, result
        except ValueError as e:
            status.update(label=f"{label} \u2014 Failed", state="error")
            st.error(str(e))
            return False, str(e)


# ============================================================================
# RAIL EFFECT FUNCTIONS (the "sound logic" behind each of the 9 services)
# ============================================================================

def do_escrow_lock(amount):
    ledger.adjust("escrow_trust_pool", +amount)
    log_txn("Escrow Multi-Sig", "Lock", amount, "INR", "LOCKED",
             "Funds held pending 2-of-3 signoff")
    return {"escrow_trust_pool": ledger.accounts["escrow_trust_pool"]}


def do_escrow_release(amount, sig_count):
    if sig_count < 2:
        raise ValueError(f"Release blocked: only {sig_count}/3 signatures collected (need \u2265 2).")
    ledger.transfer("escrow_trust_pool", "atomic_pool_2pc", 0)  # no-op keeps symmetry
    ledger.adjust("escrow_trust_pool", -amount)
    log_txn("Escrow Multi-Sig", "Release", amount, "INR", "RELEASED",
             f"{sig_count}/3 signatures verified")
    return {"escrow_trust_pool": ledger.accounts["escrow_trust_pool"]}


def do_2pc(amount, force_timeout=False):
    ledger.transfer("treasury_float", "atomic_pool_2pc", amount)
    rolled_back = force_timeout or (random.random() < 0.08)
    if rolled_back:
        ledger.transfer("atomic_pool_2pc", "treasury_float", amount)
        log_txn("2PC Bulk Disbursals", "Rollback", amount, "INR", "ROLLED BACK",
                 "Upstream bank timeout simulated \u2014 reservation released")
        return {"status": "ROLLED BACK"}
    ledger.adjust("atomic_pool_2pc", -amount)
    log_txn("2PC Bulk Disbursals", "Payout", amount, "INR", "SETTLED",
             "IMPS/RTGS commit acknowledged")
    return {"status": "SETTLED"}


def do_va_collect(amount, label):
    van = f"VAN{random.randint(100000,999999)}"
    ledger.adjust("treasury_float", +amount)
    log_txn("Virtual Accounts (CMS)", "Collect Credit", amount, "INR", "RECONCILED",
             f"{van} matched to {label}")
    return {"van": van}


def do_enach_register(amount, freq_days, start_date):
    mandate_id = f"MNDT-{uuid.uuid4().hex[:8].upper()}"
    st.session_state.mandates[mandate_id] = {
        "amount": amount, "freq_days": freq_days,
        "next_due": start_date, "created": datetime.now().strftime("%Y-%m-%d"),
    }
    log_txn("e-NACH Standing Orders", "Register Mandate", amount, "INR", "ACTIVE",
             f"{mandate_id} \u00b7 every {freq_days}d")
    return {"mandate_id": mandate_id}


def do_enach_trigger(mandate_id):
    m = st.session_state.mandates[mandate_id]
    ledger.adjust("treasury_float", +m["amount"])
    m["next_due"] = m["next_due"] + timedelta(days=m["freq_days"])
    log_txn("e-NACH Standing Orders", "Trigger Pull", m["amount"], "INR", "DEBITED",
             f"{mandate_id} \u00b7 next due {m['next_due'].strftime('%Y-%m-%d')}")
    return {"next_due": m["next_due"]}


def do_sweep():
    sub_balances = [random.randint(8_000, 30_000) for _ in range(4)]
    total = sum(sub_balances)
    ledger.adjust("treasury_float", +total)
    log_txn("Liquidity Sweep Pool", "Sweep Float", total, "INR", "SWEPT",
             f"4 accounts: {', '.join(fmt_inr(b) for b in sub_balances)}")
    return {"sub_balances": sub_balances, "total": total}


def current_fx_rate():
    return round(83.10 + random.uniform(-0.35, 0.35), 4)


def do_fx(amount_usd):
    rate = current_fx_rate()
    inr_needed = amount_usd * rate
    ledger.transfer("treasury_float", "nostro_fx_mirror_usd", 0)  # symmetry no-op
    if ledger.accounts["treasury_float"] < inr_needed:
        raise ValueError(f"Insufficient Treasury Float for FX leg: need {fmt_inr(inr_needed)}")
    ledger.accounts["treasury_float"] -= inr_needed
    ledger.accounts["nostro_fx_mirror_usd"] += amount_usd
    ref = f"MT103-{uuid.uuid4().hex[:8].upper()}"
    log_txn("Cross-Border FX Nostro", "Dispatch Remit", amount_usd, "USD", "SETTLED",
             f"{ref} @ {rate}")
    return {"rate": rate, "inr_debited": inr_needed, "ref": ref}


def do_aa_pull(purpose):
    snapshot = {
        "Avg. Monthly Inflow": fmt_inr(random.randint(60_000, 220_000)),
        "Existing EMI Obligations": fmt_inr(random.randint(5_000, 40_000)),
        "Avg. EOD Balance (90d)": fmt_inr(random.randint(15_000, 150_000)),
        "Bounce Rate (90d)": f"{random.choice([0,0,1,2])} instances",
    }
    log_txn("Account Aggregator Consent Flow", "Data Pull", 0, "INR", "DATA PULLED", purpose)
    return snapshot


def do_split(gross, commission_pct):
    commission = round(gross * commission_pct / 100, 2)
    payout = round(gross - commission, 2)
    ledger.adjust("treasury_float", +commission)
    ledger.adjust("escrow_trust_pool", +payout)
    log_txn("Marketplace Split", "Instant Split", gross, "INR", "SETTLED",
             f"Commission {fmt_inr(commission)} \u00b7 Seller {fmt_inr(payout)}")
    return {"commission": commission, "payout": payout}


def do_gst(amount):
    gst = round(amount * 0.18, 2)
    ledger.adjust("escrow_trust_pool", +gst)
    log_txn("Statutory Tax Escrow", "Sequester GST", gst, "INR", "SEQUESTERED",
             f"18% of {fmt_inr(amount)}")
    return {"gst": gst}


QUICK_RUN = {
    "escrow": lambda: do_escrow_lock(50_000),
    "2pc": lambda: do_2pc(25_000),
    "va": lambda: do_va_collect(15_000, "Auto-routed collection"),
    "enach": lambda: do_enach_trigger(
        list(st.session_state.mandates)[0] if st.session_state.mandates
        else do_enach_register(10_000, 30, datetime.now())["mandate_id"]
    ),
    "sweep": lambda: do_sweep(),
    "fx": lambda: do_fx(500),
    "aa": lambda: do_aa_pull("AI-agent-routed underwriting pull"),
    "split": lambda: do_split(20_000, 10),
    "gst": lambda: do_gst(100_000),
}

QUICK_STEP_KEY = {
    "escrow": "escrow_lock", "2pc": "2pc", "va": "va", "enach": "enach_trigger",
    "sweep": "sweep", "fx": "fx", "aa": "aa", "split": "split", "gst": "gst",
}

# ============================================================================
# ROUTING AGENT (LLM-backed, with rule-based fallback)
# ============================================================================

def rule_based_route(query):
    q = query.lower()
    scores = {s["id"]: sum(1 for kw in s["keywords"] if kw in q) for s in SERVICE_DEFS}
    best_id = max(scores, key=scores.get)
    if scores[best_id] == 0:
        return None, "No confident keyword match. Try mentioning a rail explicitly (e.g. 'NACH mandate', 'cross-border remittance', 'escrow milestone')."
    matched_kws = [kw for kw in SERVICE_BY_ID[best_id]["keywords"] if kw in q]
    return best_id, f"Matched on: {', '.join(matched_kws)}."


def llm_route(query, api_key, model):
    client = anthropic.Anthropic(api_key=api_key)
    service_list = "\n".join(f"- {s['id']}: {s['name']} \u2014 {s['desc']}" for s in SERVICE_DEFS)
    system_prompt = (
        "You are the TBG-CORE AI Rail Routing Agent for a simulated treasury/payments "
        "orchestration engine. Given a natural-language operations request, choose the "
        "single best-fit rail from this list:\n\n" + service_list + "\n\n"
        'Respond with STRICT JSON only (no markdown fences), exactly: '
        '{"service_id": "<id from the list>", "reasoning": "<one sentence>", "confidence": <0-1 float>}'
    )
    resp = client.messages.create(
        model=model, max_tokens=250,
        system=system_prompt,
        messages=[{"role": "user", "content": query}],
    )
    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    raw = raw.strip("`")
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    data = json.loads(raw)
    sid = data["service_id"]
    if sid not in SERVICE_BY_ID:
        raise ValueError(f"Model returned unknown service_id '{sid}'")
    return sid, data.get("reasoning", ""), float(data.get("confidence", 0.75))


# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown("### \u2699\ufe0f Engine Console")
    st.caption("Simulation controls \u00b7 nothing here touches a real bank.")

    use_llm = st.toggle("Use LLM agent for routing", value=False,
                         disabled=not ANTHROPIC_SDK_AVAILABLE,
                         help="Requires the `anthropic` package and an API key.")
    api_key = None
    model_name = DEFAULT_MODEL
    if use_llm:
        if not ANTHROPIC_SDK_AVAILABLE:
            st.warning("`anthropic` package not installed. Falling back to rule-based routing.")
        api_key = st.text_input("Anthropic API key", type="password",
                                 help="Kept only in this session, never written to disk.")
        model_name = st.text_input("Model", value=DEFAULT_MODEL)

    st.divider()
    st.markdown("##### Live pool snapshot")
    for acct, label in [
        ("escrow_trust_pool", "Escrow Trust Pool"),
        ("treasury_float", "Treasury Float"),
        ("atomic_pool_2pc", "2PC Atomic Pool"),
    ]:
        st.caption(f"{label}: **{fmt_inr(ledger.accounts[acct])}**")
    st.caption(f"Nostro FX Mirror: **{fmt_usd(ledger.accounts['nostro_fx_mirror_usd'])}**")

    st.divider()
    elapsed = (datetime.now() - st.session_state.started_at).seconds
    st.caption(f"Session uptime: {elapsed}s \u00b7 Simulated latency: {random.randint(28,55)}ms")
    st.caption(f"Transactions this session: {len(st.session_state.log)}")

    st.divider()
    if st.button("\u21bb Reset Simulation", use_container_width=True):
        reset_state()
        st.rerun()

# ============================================================================
# HEADER
# ============================================================================

st.markdown(f"""
<div class="tbg-header">
    <div class="tbg-logo-box">
        <div class="tbg-logo-badge">TBG</div>
        <div>
            <p class="tbg-title">TBG-CORE Engine Simulator</p>
            <p class="tbg-subtitle">Institutional Payment &amp; Ledger Orchestration Workbench &middot; Enterprise Demo Build</p>
        </div>
    </div>
    <div class="tbg-pill">\u25cf SIMULATION MODE &middot; 9 RAILS MODELED</div>
</div>
""", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
metric_data = [
    (m1, "Escrow Trust Pool", fmt_inr(ledger.accounts["escrow_trust_pool"]), "RERA-style vault, simulated"),
    (m2, "Treasury Float", fmt_inr(ledger.accounts["treasury_float"]), "4 linked accounts (ZBA)"),
    (m3, "2PC Atomic Pool", fmt_inr(ledger.accounts["atomic_pool_2pc"]), "In-flight reservations"),
    (m4, "Nostro FX Mirror", fmt_usd(ledger.accounts["nostro_fx_mirror_usd"]), "USD/INR spot lock"),
]
for col, label, value, sub in metric_data:
    with col:
        st.markdown(f"""
        <div class="tbg-metric">
            <div class="tbg-metric-label">{label}</div>
            <div class="tbg-metric-value">{value}</div>
            <div class="tbg-metric-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

st.write("")

# ============================================================================
# AI AGENT RAIL ROUTING CONSOLE
# ============================================================================

with st.container(border=True):
    st.markdown("#### \U0001F9ED AI Agent Rail Routing Console")
    st.caption("Describe an operations need in plain English \u2014 the agent picks the rail and explains why.")
    rc1, rc2 = st.columns([5, 1])
    with rc1:
        query = st.text_input(
            "Query", value="Client needs to debit \u20b910,000 loan EMI every month on the 5th via bank mandate",
            label_visibility="collapsed",
        )
    with rc2:
        route_clicked = st.button("Route Query", type="primary", use_container_width=True)

    if route_clicked and query.strip():
        if use_llm and api_key:
            try:
                sid, reasoning, conf = llm_route(query, api_key, model_name)
                st.session_state.route_result = {"id": sid, "reasoning": reasoning, "confidence": conf, "engine": "LLM Agent"}
            except Exception as e:
                st.warning(f"LLM routing failed ({e}). Falling back to rule-based engine.")
                sid, reasoning = rule_based_route(query)
                st.session_state.route_result = {"id": sid, "reasoning": reasoning, "confidence": None, "engine": "Rule-based fallback"}
        else:
            sid, reasoning = rule_based_route(query)
            st.session_state.route_result = {"id": sid, "reasoning": reasoning, "confidence": None, "engine": "Rule-based engine"}

    rr = st.session_state.route_result
    if rr:
        if rr["id"] is None:
            st.info(rr["reasoning"])
        else:
            svc = SERVICE_BY_ID[rr["id"]]
            cA, cB = st.columns([3, 1])
            with cA:
                st.markdown(
                    f"{badge(svc['tag'], TAG_COLORS[svc['tag']])} &nbsp; **{svc['name']}**  \n"
                    f"<span style='color:#6B7690;font-size:13px;'>{rr['reasoning']}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(f"Routed by: {rr['engine']}" + (f" \u00b7 confidence {rr['confidence']:.0%}" if rr.get("confidence") else ""))
                if rr.get("confidence") is not None:
                    st.progress(min(max(rr["confidence"], 0.0), 1.0))
            with cB:
                if st.button("\u25b8 Execute via routed rail", use_container_width=True):
                    ok, result = run_process(f"AI-Routed: {svc['name']}", STEP_FLOWS[QUICK_STEP_KEY[rr['id']]], QUICK_RUN[rr['id']])
                    if ok:
                        st.success(f"{svc['name']} executed successfully via the routing agent.")
                        st.rerun()

st.write("")
st.markdown("#### Institutional Payment & Ledger Services Suite")
st.caption("9 simulated rails, grouped as a 3\u00d73 operational grid.")

# ============================================================================
# 9 SERVICE CARDS (3x3 GRID)
# ============================================================================

def card_header(svc):
    st.markdown(
        f"{badge(svc['tag'], TAG_COLORS[svc['tag']])}"
        f"<div class='tbg-card-title'>{svc['name']}</div>"
        f"<div class='tbg-card-desc'>{svc['desc']}</div>",
        unsafe_allow_html=True,
    )


def render_escrow_card():
    svc = SERVICE_BY_ID["escrow"]
    with st.container(border=True):
        card_header(svc)
        amount = st.number_input("Milestone amount (\u20b9)", min_value=1000, value=50_000, step=5000, key="escrow_amt")
        if st.button("Dispatch Lock", key="escrow_lock_btn", use_container_width=True):
            run_process("Escrow Multi-Sig \u2014 Lock", STEP_FLOWS["escrow_lock"], lambda: do_escrow_lock(amount))
            st.rerun()
        st.caption("Release requires 2-of-3 signatories:")
        s1, s2, s3 = st.columns(3)
        sig1 = s1.checkbox("Sig 1", key="sig1")
        sig2 = s2.checkbox("Sig 2", key="sig2")
        sig3 = s3.checkbox("Sig 3", key="sig3")
        if st.button("Release Escrow", key="escrow_release_btn", use_container_width=True):
            sig_count = sum([sig1, sig2, sig3])
            run_process("Escrow Multi-Sig \u2014 Release", STEP_FLOWS["escrow_release"], lambda: do_escrow_release(amount, sig_count))
            st.rerun()


def render_2pc_card():
    svc = SERVICE_BY_ID["2pc"]
    with st.container(border=True):
        card_header(svc)
        amount = st.number_input("Disbursal amount (\u20b9)", min_value=1000, value=25_000, step=1000, key="2pc_amt")
        force_timeout = st.checkbox("Force bank timeout (demo rollback)", key="2pc_timeout")
        if st.button("Execute Payout", key="2pc_btn", use_container_width=True):
            run_process("2PC Bulk Disbursals", STEP_FLOWS["2pc"], lambda: do_2pc(amount, force_timeout))
            st.rerun()


def render_va_card():
    svc = SERVICE_BY_ID["va"]
    with st.container(border=True):
        card_header(svc)
        amount = st.number_input("Collection amount (\u20b9)", min_value=1000, value=15_000, step=1000, key="va_amt")
        label = st.text_input("Invoice label", value="INV-1042", key="va_label")
        if st.button("Collect Credit", key="va_btn", use_container_width=True):
            run_process("Virtual Accounts (CMS)", STEP_FLOWS["va"], lambda: do_va_collect(amount, label))
            st.rerun()


def render_enach_card():
    svc = SERVICE_BY_ID["enach"]
    with st.container(border=True):
        card_header(svc)
        tab1, tab2 = st.tabs(["Register", "Trigger Pull"])
        with tab1:
            amount = st.number_input("EMI amount (\u20b9)", min_value=500, value=10_000, step=500, key="enach_amt")
            freq = st.selectbox("Frequency", ["Monthly (30d)", "Weekly (7d)"], key="enach_freq")
            freq_days = 30 if "Monthly" in freq else 7
            if st.button("Register Mandate", key="enach_reg_btn", use_container_width=True):
                run_process("e-NACH \u2014 Register", STEP_FLOWS["enach_register"],
                            lambda: do_enach_register(amount, freq_days, datetime.now()))
                st.rerun()
        with tab2:
            if st.session_state.mandates:
                mid = st.selectbox("Active mandate", list(st.session_state.mandates.keys()), key="enach_pick")
                m = st.session_state.mandates[mid]
                st.caption(f"\u20b9{m['amount']:,.0f} \u00b7 every {m['freq_days']}d \u00b7 next due {m['next_due'].strftime('%Y-%m-%d')}")
                if st.button("Trigger Pull", key="enach_trig_btn", use_container_width=True):
                    run_process("e-NACH \u2014 Trigger Pull", STEP_FLOWS["enach_trigger"], lambda: do_enach_trigger(mid))
                    st.rerun()
            else:
                st.caption("No active mandates yet \u2014 register one first.")


def render_sweep_card():
    svc = SERVICE_BY_ID["sweep"]
    with st.container(border=True):
        card_header(svc)
        st.caption("Sweeps 4 simulated linked sub-accounts into Treasury Float.")
        if st.button("Sweep Float", key="sweep_btn", use_container_width=True):
            ok, result = run_process("Liquidity Sweep Pool", STEP_FLOWS["sweep"], do_sweep)
            if ok:
                st.caption("Sub-account balances swept: " + ", ".join(fmt_inr(b) for b in result["sub_balances"]))
            st.rerun()


def render_fx_card():
    svc = SERVICE_BY_ID["fx"]
    with st.container(border=True):
        card_header(svc)
        amount = st.number_input("Remit amount (USD)", min_value=10, value=500, step=10, key="fx_amt")
        st.caption(f"Indicative spot: 1 USD \u2248 \u20b9{current_fx_rate()}")
        if st.button("Dispatch Remit", key="fx_btn", use_container_width=True):
            run_process("Cross-Border FX Nostro", STEP_FLOWS["fx"], lambda: do_fx(amount))
            st.rerun()


def render_aa_card():
    svc = SERVICE_BY_ID["aa"]
    with st.container(border=True):
        card_header(svc)
        consent = st.checkbox("Customer has granted AA consent", key="aa_consent")
        purpose = st.text_input("Purpose", value="Algorithmic underwriting", key="aa_purpose")
        if st.button("Pull Consent Data", key="aa_btn", use_container_width=True):
            if not consent:
                st.error("Cannot pull data \u2014 customer consent not granted.")
            else:
                ok, snapshot = run_process("Account Aggregator Consent Flow", STEP_FLOWS["aa"], lambda: do_aa_pull(purpose))
                if ok:
                    st.table(pd.DataFrame(snapshot.items(), columns=["Metric", "Value"]))


def render_split_card():
    svc = SERVICE_BY_ID["split"]
    with st.container(border=True):
        card_header(svc)
        gross = st.number_input("Gross transaction (\u20b9)", min_value=1000, value=20_000, step=1000, key="split_amt")
        pct = st.slider("Platform commission %", 0, 30, 10, key="split_pct")
        if st.button("Execute Instant Split", key="split_btn", use_container_width=True):
            ok, result = run_process("Marketplace Split", STEP_FLOWS["split"], lambda: do_split(gross, pct))
            if ok:
                st.caption(f"Commission {fmt_inr(result['commission'])} \u00b7 Seller payout {fmt_inr(result['payout'])}")
            st.rerun()


def render_gst_card():
    svc = SERVICE_BY_ID["gst"]
    with st.container(border=True):
        card_header(svc)
        amount = st.number_input("Transaction value (\u20b9)", min_value=1000, value=100_000, step=1000, key="gst_amt")
        st.caption(f"GST @ 18% = {fmt_inr(amount*0.18)}")
        if st.button("Sequester GST", key="gst_btn", use_container_width=True):
            run_process("Statutory Tax Escrow", STEP_FLOWS["gst"], lambda: do_gst(amount))
            st.rerun()


row1 = st.columns(3)
with row1[0]: render_escrow_card()
with row1[1]: render_2pc_card()
with row1[2]: render_va_card()

row2 = st.columns(3)
with row2[0]: render_enach_card()
with row2[1]: render_sweep_card()
with row2[2]: render_fx_card()

row3 = st.columns(3)
with row3[0]: render_aa_card()
with row3[1]: render_split_card()
with row3[2]: render_gst_card()

# ============================================================================
# TRANSACTION LEDGER
# ============================================================================

st.write("")
st.markdown("#### Transaction Ledger")
if st.session_state.log:
    df = pd.DataFrame(st.session_state.log)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "Export ledger as CSV", df.to_csv(index=False).encode("utf-8"),
        file_name="tbg_core_simulated_ledger.csv", mime="text/csv",
    )
else:
    st.caption("No transactions yet \u2014 execute a rail above to see it appear here.")

st.divider()
st.caption(
    "TBG-CORE Engine Simulator \u2014 an educational simulation environment. "
    "No real bank accounts, NPCI/RTGS/SWIFT rails, or regulated financial infrastructure are connected. "
    "All balances, mandates and FX rates are generated in-process for demonstration purposes."
)
