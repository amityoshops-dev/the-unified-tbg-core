import pathlib
from decimal import Decimal
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core_engine import (
    JournalBatch,
    RERAInwardPayment,
    TransactionEntry,
    engine_instance,
)
from mcp_server import MCP_TOOLS_MANIFEST, dispatch_mcp_tool

app = FastAPI(
    title="YES Bank TBG-Core Enterprise Platform",
    version="2026.4",
    description="Transaction Banking Group Core: Ledger, Escrow, Liquidity, & MCP Integration",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------
# STATIC ASSETS MOUNTING
# ---------------------------------------------------------------------
if pathlib.Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

if pathlib.Path("static/assets").exists():
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")


# ---------------------------------------------------------------------
# REST ROUTERS (CORE PLATFORM)
# ---------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_root_dashboard():
    dashboard_path = pathlib.Path("static/index.html")
    if dashboard_path.exists():
        return FileResponse(dashboard_path)
    return HTMLResponse(
        """
        <body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;padding:40px;">
            <h2>TBG-CORE ENGINE ONLINE</h2>
            <p>UI static bundle not built. Direct API and MCP endpoints are fully operational.</p>
            <ul>
                <li><a style="color:#38bdf8;" href="/docs">Swagger API Reference</a></li>
                <li><a style="color:#38bdf8;" href="/api/v1/ledger/balances">Live GL Balances</a></li>
                <li><a style="color:#38bdf8;" href="/mcp/tools">MCP Tool Discovery</a></li>
            </ul>
        </body>
        """
    )


@app.get("/api/v1/ledger/balances")
async def get_ledger_balances():
    return {
        "status": "SUCCESS",
        "timestamp": pathlib.os.sys.version,
        "balances": {acc: str(bal) for acc, bal in engine_instance.accounts.items()},
    }


class RERAPostRequest(BaseModel):
    project_id: str
    payer_van: str
    buyer_ref: str
    gross_amount: float


@app.post("/api/v1/escrow/rera-inward")
async def post_rera_collection(req: RERAPostRequest):
    try:
        payload = RERAInwardPayment(
            project_id=req.project_id,
            payer_van=req.payer_van,
            buyer_ref=req.buyer_ref,
            gross_amount=Decimal(str(req.gross_amount)),
        )
        return engine_instance.process_rera_70_30_split(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class UDINDisbursementRequest(BaseModel):
    udin: str
    amount: float
    beneficiary: str


@app.post("/api/v1/escrow/milestone-disbursement")
async def post_udin_disbursement(req: UDINDisbursementRequest):
    try:
        return engine_instance.verify_ca_udin_disbursement(
            udin=req.udin,
            amount=Decimal(str(req.amount)),
            beneficiary=req.beneficiary,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/liquidity/eod-sweep")
async def post_liquidity_sweep():
    return engine_instance.execute_liquidity_sweep()


# ---------------------------------------------------------------------
# MCP (MODEL CONTEXT PROTOCOL) RPC LAYER
# ---------------------------------------------------------------------
@app.get("/mcp/tools")
async def get_mcp_tools():
    """Discovery endpoint for LLMs, agentic workers, and Copilot tools."""
    return {"tools": MCP_TOOLS_MANIFEST}


@app.post("/mcp/rpc")
async def handle_mcp_rpc(request: Request):
    """JSON-RPC 2.0 interface compliant with MCP specification."""
    try:
        body = await request.json()
        req_id = body.get("id")
        method = body.get("method")
        params = body.get("params", {})

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOLS_MANIFEST}}

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            res = dispatch_mcp_tool(name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": str(res)}]},
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }
    except Exception as err:
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32000, "message": str(err)},
        }