import pathlib

app_code = """import os
from fastapi import FastAPI, Header, HTTPException, Query, Request
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
from products.nach_ach_engine import NACHClearingEngine
from products.pg_aggregator import PaymentGatewayRouter
from products.erp_engine import ERPCompatibilityEngine
from products.agent_router import FinancialAgentRouter

app = FastAPI(
    title="Unified TBG Core Enterprise Engine",
    description="Automated Transaction Banking & Financial Rail Engine",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class ClientProblemQuery(BaseModel):
    client_problem_statement: str
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
      <h1 class="text-xl font-bold tracking-tight text-white">THE UNIFIED TBG-CORE <span class="text-xs bg-emerald-950 text-emerald-400 border border-emerald-800 px-2 py-0.5 rounded ml-2">PROD LIVE</span></h1>
    </div>
    <a href="/docs" class="text-sm bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded border border-slate-700">Interactive Swagger UI</a>
  </header>

  <main class="max-w-7xl mx-auto p-6 space-y-6">
    <section class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="p-4 bg-slate-900 border border-slate-800 rounded-lg">
        <p class="text-xs uppercase text-slate-400 font-semibold tracking-wider">Active Clearing</p>
        <p class="text-2xl font-bold text-white mt-1">NPCI e-NACH</p>
        <span class="text-xs text-emerald-400">Direct APBS Engine</span>
      </div>
      <div class="p-4 bg-slate-900 border border-slate-800 rounded-lg">
        <p class="text-xs uppercase text-slate-400 font-semibold tracking-wider">Vault Mode</p>
        <p class="text-2xl font-bold text-white mt-1">Digital Escrow</p>
        <span class="text-xs text-emerald-400">Tripartite Multi-Sig</span>
      </div>
      <div class="p-4 bg-slate-900 border border-slate-800 rounded-lg">
        <p class="text-xs uppercase text-slate-400 font-semibold tracking-wider">Security Layer</p>
        <p class="text-2xl font-bold text-white mt-1">Anti-BOLA</p>
        <span class="text-xs text-emerald-400">Tenant Whitelisted</span>
      </div>
      <div class="p-4 bg-slate-900 border border-slate-800 rounded-lg">
        <p class="text-xs uppercase text-slate-400 font-semibold tracking-wider">Intelligence</p>
        <p class="text-2xl font-bold text-white mt-1">LangSmith</p>
        <span class="text-xs text-indigo-400">Traced Router Active</span>
      </div>
    </section>

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

@app.post("/api/v1/agent/solve-problem", tags=["0. AI Agent Financial Router"])
async def route_client_problem(req: ClientProblemQuery):
    return agent_router.route_client_problem(req.client_problem_statement)

@app.post("/api/v1/clearing/enach/register", tags=["1. NACH & e-Mandate Clearing"])
async def register_mandate(req: RegisterENachSchema):
    return nach_engine.register_enach_mandate(
        debtor_name=req.debtor_name,
        debtor_account=req.debtor_account,
        ifsc=req.ifsc,
        max_amount=req.max_amount,
        auth_mode=req.auth_mode
    )

@app.post("/api/v1/clearing/nach/present-debit", tags=["1. NACH & e-Mandate Clearing"])
async def execute_nach_presentation(req: PresentNachSchema):
    return nach_engine.present_nach_debit(req.umrn, req.amount, req.settlement_date)

@app.get("/api/v1/erp/compatibility-matrix", tags=["3. ERP Integration Engine"])
async def get_erp_checklist(erp_system: str = Query("SAP_S4_HANA")):
    return erp_engine.get_erp_system_checklist(erp_system)

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ONLINE", "suite": "UNIFIED_TBG_ENTERPRISE_V4"}
"""

test_code = """import sys
from products.agent_router import FinancialAgentRouter
from products.nach_ach_engine import NACHClearingEngine

def run_tests():
    print("Testing TBG Architecture...")
    router = FinancialAgentRouter()
    nach = NACHClearingEngine()

    query = "Client requires recurring pull of funds or batch debit authority under NPCI or FedACH frameworks."
    route = router.route_client_problem(query)
    assert route["target_endpoint"] == "/api/v1/clearing/enach/register"
    print("[PASS] AI Agent correctly mapped query to e-NACH Rail")

    mandate = nach.register_enach_mandate("Acme Client", "9876543210", "HDFC0000060", 10000.0, "NET_BANKING")
    assert mandate["status"] == "REGISTERED"
    print(f"[PASS] e-NACH Mandate generated: {mandate['umrn']}")

    clr = nach.present_nach_debit(mandate["umrn"], 2500.0, "2026-09-25")
    assert clr["status"] == "SETTLED"
    print(f"[PASS] Debit presented and settled: {clr['clearing_ref']}")
    print("--- ALL TEST CHECKS PASSED SUCCESSFULLY ---")

if __name__ == "__main__":
    run_tests()
"""

pathlib.Path("app.py").write_text(app_code, encoding="utf-8")
pathlib.Path("test_execution.py").write_text(test_code, encoding="utf-8")
print("SUCCESS: app.py (with visual Tailwind engine) and test_execution.py written.")
