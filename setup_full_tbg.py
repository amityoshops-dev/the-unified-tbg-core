import pathlib

full_app_code = """import os
import ipaddress
from fastapi import FastAPI, Header, HTTPException, Query, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from products.payout_pipeline import PayoutPipeline
from products.escrow_engine import EscrowEngine
from products.liquidity_sweep import LiquiditySweepEngine
from products.cross_border import CrossBorderRailEngine
from products.security_gateway import SecurityGateway
from products.mcp_bridge import MCPToolBridge
from products.bulk_payout import BulkPayoutEngine
from products.receivables import ReceivablesEngine
from products.treasury_pnl import TreasuryPnLEngine
from products.callback_dispatcher import WebhookCallbackEngine
from products.nach_ach_engine import NACHClearingEngine
from products.pg_aggregator import PaymentGatewayRouter
from products.erp_engine import ERPCompatibilityEngine
from products.agent_router import FinancialAgentRouter

app = FastAPI(
    title="The Unified TBG Core Enterprise Engine",
    description="Complete 9-Service Transaction Banking Architecture",
    version="5.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Engine Singletons
payout_engine = PayoutPipeline()
escrow_engine = EscrowEngine(payout_pipeline=payout_engine)
sweep_engine = LiquiditySweepEngine()
cross_border_engine = CrossBorderRailEngine()
sec_gateway = SecurityGateway()
mcp_bridge = MCPToolBridge(escrow_engine, sweep_engine, sec_gateway)
bulk_engine = BulkPayoutEngine()
receivables_engine = ReceivablesEngine()
treasury_pnl = TreasuryPnLEngine()
nach_engine = NACHClearingEngine()
pg_engine = PaymentGatewayRouter()
erp_engine = ERPCompatibilityEngine()
agent_router = FinancialAgentRouter()

IP_WHITELIST_SUBNETS = [
    ipaddress.ip_network("127.0.0.1/32"),
    ipaddress.ip_network("10.0.0.0/8")
]

def verify_ip_allowlist(client_ip: str):
    try:
        ip = ipaddress.ip_address(client_ip)
        if not any(ip in subnet for subnet in IP_WHITELIST_SUBNETS):
            raise HTTPException(status_code=403, detail="Forbidden: Source IP is not in TBG Callback Whitelist")
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Source IP format")

# --- SCHEMAS (Anti-Mass Assignment) ---
class ClientProblemQuery(BaseModel):
    client_problem_statement: str
    model_config = {"extra": "forbid"}

class MilestoneSchema(BaseModel):
    milestone_id: str
    description: str
    target_amount: float = Field(gt=0)
    model_config = {"extra": "forbid"}

class CreateEscrowSchema(BaseModel):
    depositor: str
    beneficiary: str
    trustee: str
    total_amount: float = Field(gt=0)
    milestones: List[MilestoneSchema]
    model_config = {"extra": "forbid"}

class DepositSchema(BaseModel):
    virtual_account_no: str
    amount: float = Field(gt=0)
    model_config = {"extra": "forbid"}

class ReleaseSchema(BaseModel):
    contract_id: str
    milestone_id: str
    trustee_signature: str
    callback_url: Optional[str] = None
    model_config = {"extra": "forbid"}

class BulkPayoutItemSchema(BaseModel):
    item_id: str
    account_number: str
    ifsc: str
    amount: float = Field(gt=0)
    model_config = {"extra": "forbid"}

class BulkPayoutBatchSchema(BaseModel):
    batch_id: str
    debit_account: str
    items: List[BulkPayoutItemSchema]
    model_config = {"extra": "forbid"}

class CreateInvoiceSchema(BaseModel):
    debtor_name: str
    debtor_pan: str
    amount: float = Field(gt=0)
    due_date: str
    product_code: str = "RECEIVABLES"
    model_config = {"extra": "forbid"}

class RemittanceSchema(BaseModel):
    debtor_account: str
    foreign_beneficiary_iban: str
    currency: str
    inr_amount: float = Field(gt=0)
    purpose_code: str = "S0101"
    model_config = {"extra": "forbid"}

class MCPInvocationSchema(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    model_config = {"extra": "forbid"}

class RegisterENachSchema(BaseModel):
    debtor_name: str
    debtor_account: str
    ifsc: str
    max_amount: float = Field(gt=0)
    auth_mode: str = "NET_BANKING"
    model_config = {"extra": "forbid"}

class PresentNachSchema(BaseModel):
    umrn: str
    amount: float = Field(gt=0)
    settlement_date: str
    model_config = {"extra": "forbid"}

class CreatePGOrderSchema(BaseModel):
    merchant_order_id: str
    amount: float = Field(gt=0)
    customer_identifier: str
    preferred_rail: Optional[str] = None
    model_config = {"extra": "forbid"}

class ERPCheckSchema(BaseModel):
    erp_source: str
    gl_code: str
    cost_center: str
    currency: str
    idempotency_reference: str

# ==================== 0. VISUAL TAILWIND DASHBOARD ====================
@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
async def serve_visual_dashboard():
    return \"\"\"<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>TBG-CORE Enterprise Workbench</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 font-sans min-h-screen">
  <header class="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 px-6 py-4 flex items-center justify-between">
    <div class="flex items-center space-x-3">
      <div class="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></div>
      <h1 class="text-xl font-bold tracking-tight text-white">THE UNIFIED TBG-CORE <span class="text-xs bg-emerald-950 text-emerald-400 border border-emerald-800 px-2 py-0.5 rounded ml-2">9 SERVICES ACTIVE</span></h1>
    </div>
    <a href="/docs" class="text-sm bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded border border-slate-700">Open API Specs (/docs)</a>
  </header>

  <main class="max-w-7xl mx-auto p-6 space-y-6">
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
      <div class="p-3 bg-slate-900 border border-slate-800 rounded">
        <p class="text-xs text-slate-400 uppercase font-semibold">1. Digital Escrow</p>
        <p class="text-sm font-bold text-white mt-1">Multi-Sig Vault</p>
      </div>
      <div class="p-3 bg-slate-900 border border-slate-800 rounded">
        <p class="text-xs text-slate-400 uppercase font-semibold">2. Payout Rails</p>
        <p class="text-sm font-bold text-white mt-1">Idempotent Disbursal</p>
      </div>
      <div class="p-3 bg-slate-900 border border-slate-800 rounded">
        <p class="text-xs text-slate-400 uppercase font-semibold">3. Bulk Batches</p>
        <p class="text-sm font-bold text-white mt-1">Automated Clearing</p>
      </div>
      <div class="p-3 bg-slate-900 border border-slate-800 rounded">
        <p class="text-xs text-slate-400 uppercase font-semibold">4. Receivables</p>
        <p class="text-sm font-bold text-white mt-1">Virtual Ledger Map</p>
      </div>
      <div class="p-3 bg-slate-900 border border-slate-800 rounded">
        <p class="text-xs text-slate-400 uppercase font-semibold">5. Liquidity Sweep</p>
        <p class="text-sm font-bold text-white mt-1">Two-Way Pooling</p>
      </div>
      <div class="p-3 bg-slate-900 border border-slate-800 rounded">
        <p class="text-xs text-slate-400 uppercase font-semibold">6. Cross-Border FX</p>
        <p class="text-sm font-bold text-white mt-1">SWIFT MT103 Rail</p>
      </div>
      <div class="p-3 bg-slate-900 border border-slate-800 rounded">
        <p class="text-xs text-slate-400 uppercase font-semibold">7. Mandate Clearing</p>
        <p class="text-sm font-bold text-white mt-1">NPCI e-NACH / ACH</p>
      </div>
      <div class="p-3 bg-slate-900 border border-slate-800 rounded">
        <p class="text-xs text-slate-400 uppercase font-semibold">8. PG Aggregator</p>
        <p class="text-sm font-bold text-white mt-1">Fallback Routing</p>
      </div>
      <div class="p-3 bg-slate-900 border border-slate-800 rounded">
        <p class="text-xs text-slate-400 uppercase font-semibold">9. Treasury Ledger</p>
        <p class="text-sm font-bold text-white mt-1">Product P&L Calci</p>
      </div>
      <div class="p-3 bg-indigo-950/40 border border-indigo-800/50 rounded">
        <p class="text-xs text-indigo-400 uppercase font-semibold">Intelligence</p>
        <p class="text-sm font-bold text-white mt-1">LangSmith Router</p>
      </div>
    </div>

    <section class="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
      <h2 class="text-lg font-semibold text-white">AI Agent Rail Routing Console</h2>
      <div class="flex gap-3">
        <input id="agentQuery" class="flex-1 bg-slate-950 border border-slate-700 rounded px-4 py-2 text-sm text-slate-200" value="Client needs to debit 10000 loan EMI every month on 5th via bank mandate" />
        <button onclick="resolveQuery()" class="bg-emerald-600 hover:bg-emerald-500 font-semibold px-4 py-2 rounded text-sm text-white">Route Query</button>
      </div>
      <pre id="outputLog" class="p-4 bg-slate-950 border border-slate-800 rounded text-xs text-emerald-400 font-mono overflow-auto max-h-56">Ready for query resolution...</pre>
    </section>
  </main>

  <script>
    async function resolveQuery() {
      const q = document.getElementById('agentQuery').value;
      const log = document.getElementById('outputLog');
      log.innerText = 'Routing via LangSmith agent...';
      try {
        const res = await fetch('/api/v1/agent/solve-problem', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({client_problem_statement: q})
        });
        const data = await res.json();
        log.innerText = JSON.stringify(data, null, 2);
      } catch (err) {
        log.innerText = 'Execution error: ' + err;
      }
    }
  </script>
</body>
</html>\"\"\"

# ==================== ROUTE DISPATCHER ====================
@app.post("/api/v1/agent/solve-problem", tags=["0. AI Agent Financial Router"])
async def route_client_problem(req: ClientProblemQuery):
    return agent_router.route_client_problem(req.client_problem_statement)

# 1. DIGITAL ESCROW
@app.post("/api/v1/escrow/create", tags=["1. Digital Escrow"])
async def create_deal(req: CreateEscrowSchema):
    contract = escrow_engine.create_contract(req.depositor, req.beneficiary, req.trustee, req.total_amount, [m.model_dump() for m in req.milestones])
    treasury_pnl.record_revenue("ESCROW", 2500.0, contract.contract_id)
    return {"message": "Escrow created", "contract": contract}

@app.post("/api/v1/escrow/inflow-webhook", tags=["1. Digital Escrow"])
async def nodal_deposit_webhook(req: DepositSchema):
    try:
        updated = escrow_engine.deposit_inflow(req.virtual_account_no, req.amount)
        return {"message": "Funds locked in nodal vault", "contract": updated}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/v1/escrow/contracts", tags=["1. Digital Escrow"])
async def list_contracts():
    return escrow_engine.contracts

# 2. PAYOUT RAILS & SECURITY
@app.post("/api/v1/escrow/release-payout", tags=["2. Payout Rails & Security"])
async def release_milestone(req: ReleaseSchema, background_tasks: BackgroundTasks, x_tenant_id: str = Header(...), x_sender_signature: str = Header(...)):
    contract = escrow_engine.contracts.get(req.contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    sec_gateway.verify_sender_and_tenant(x_tenant_id, contract.trustee, x_sender_signature)
    try:
        result = await escrow_engine.approve_and_release(req.contract_id, req.milestone_id, req.trustee_signature)
        if req.callback_url:
            WebhookCallbackEngine.queue_async_callback(background_tasks, req.callback_url, "ESCROW_DISBURSED", result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# 3. BULK PAYOUTS
@app.post("/api/v1/bulk-payout/dispatch", tags=["3. Bulk Payouts"])
async def dispatch_bulk_batch(req: BulkPayoutBatchSchema, x_sender_signature: str = Header(...)):
    if not x_sender_signature or len(x_sender_signature) < 8:
        raise HTTPException(status_code=401, detail="Ghost Sender blocked on Bulk Payout rail.")
    result = bulk_engine.process_batch(req.batch_id, req.debit_account, [i.model_dump() for i in req.items])
    treasury_pnl.record_revenue("BULK_PAYOUT", result["batch"]["total_fees_collected"], req.batch_id)
    return result

# 4. RECEIVABLES & INVOICING
@app.post("/api/v1/receivables/invoice", tags=["4. Receivables & Invoicing"])
async def create_invoice(req: CreateInvoiceSchema):
    inv = receivables_engine.raise_invoice(req.debtor_name, req.debtor_pan, req.amount, req.due_date, req.product_code)
    treasury_pnl.record_revenue("RECEIVABLES", 50.0, inv["invoice_id"])
    return inv

# 5. LIQUIDITY MANAGEMENT
@app.post("/api/v1/liquidity/auto-sweep", tags=["5. Liquidity & VA Sweep"])
async def trigger_va_auto_sweep(threshold: float = Query(500000.0)):
    result = sweep_engine.execute_auto_sweep(threshold=threshold)
    if result["total_swept"] > 0:
        treasury_pnl.record_revenue("LIQUIDITY_SWEEP", result["total_swept"] * 0.0001, "SWEEP_BATCH")
    return result

@app.get("/api/v1/liquidity/balances", tags=["5. Liquidity & VA Sweep"])
async def get_liquidity_state():
    return {"master_pool": sweep_engine.master_pool_balance, "virtual_accounts": sweep_engine.va_accounts}

# 6. CROSS-BORDER & FX RAILS
@app.post("/api/v1/trade/cross-border-remittance", tags=["6. Cross-Border & FX Rails"])
async def execute_cross_border_payout(req: RemittanceSchema, x_sender_signature: str = Header(...)):
    if not x_sender_signature or len(x_sender_signature) < 8:
        raise HTTPException(status_code=401, detail="Ghost Sender blocked on Cross-Border rail.")
    try:
        res = cross_border_engine.process_outward_remittance(req.debtor_account, req.foreign_beneficiary_iban, req.currency, req.inr_amount, req.purpose_code)
        treasury_pnl.record_revenue("FX_REMITTANCE", req.inr_amount * 0.0035, res["swift_msg_id"])
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# 7. NACH & e-MANDATE CLEARING
@app.post("/api/v1/clearing/enach/register", tags=["7. NACH & e-Mandate Clearing"])
async def register_mandate(req: RegisterENachSchema):
    mandate = nach_engine.register_enach_mandate(req.debtor_name, req.debtor_account, req.ifsc, req.max_amount, req.auth_mode)
    treasury_pnl.record_revenue("ENACH_MANDATE", 50.0, mandate["umrn"])
    return mandate

@app.post("/api/v1/clearing/nach/present-debit", tags=["7. NACH & e-Mandate Clearing"])
async def execute_nach_presentation(req: PresentNachSchema):
    try:
        return nach_engine.present_nach_debit(req.umrn, req.amount, req.settlement_date)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

# 8. PAYMENT GATEWAY AGGREGATOR
@app.post("/api/v1/pg/order/create", tags=["8. Payment Gateway Aggregator"])
async def create_pg_order(req: CreatePGOrderSchema):
    order = pg_engine.create_collection_order(req.merchant_order_id, req.amount, req.customer_identifier, req.preferred_rail)
    treasury_pnl.record_revenue("PAYMENT_GATEWAY", req.amount * 0.012, order["tbg_order_id"])
    return order

# 9. TREASURY PnL CALCULATOR & ERP
@app.get("/api/v1/treasury/pnl-calculator", tags=["9. Treasury & Product PnL"])
async def get_treasury_pnl():
    return treasury_pnl.compute_product_pnl()

@app.get("/api/v1/erp/compatibility-matrix", tags=["9. Treasury & Product PnL"])
async def get_erp_checklist(erp_system: str = Query("SAP_S4_HANA")):
    return erp_engine.get_erp_system_checklist(erp_system)

# MCP & HEALTH
@app.post("/api/v1/mcp/invoke", tags=["MCP Gateway"])
async def invoke_mcp_tool(req: MCPInvocationSchema, x_tenant_id: str = Header(default="TRUSTEE_DESK_TENANT")):
    return await mcp_bridge.execute_mcp_tool(req.tool_name, req.arguments, x_tenant_id)

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ONLINE", "suite": "ALL_9_TBG_SERVICES_ACTIVE"}
"""

pathlib.Path("app.py").write_text(full_app_code, encoding="utf-8")
print("SUCCESS: Full Unified TBG Core rebuilt with all 9 services and UI.")
