from decimal import Decimal
from typing import Any, Dict
from core_engine import core_processor, erp_adapter, PayoutBatchItem

MCP_TOOLS_MANIFEST = [
    {
        "name": "get_live_gl_balances",
        "description": "Inspect all double-entry general ledger balances across escrow, virtual accounts, and treasury.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "process_rera_escrow_deposit",
        "description": "Applies statutory 70:30 allocation on incoming collection to designated escrow accounts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "payer_van": {"type": "string"},
                "buyer_ref": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["project_id", "payer_van", "buyer_ref", "amount"],
        },
    },
    {
        "name": "disburse_contractor_via_udin",
        "description": "Validates ICAI UDIN and releases milestones from 70% Escrow Account.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "udin": {"type": "string", "description": "18-digit ICAI UDIN certificate number"},
                "amount": {"type": "number"},
                "contractor": {"type": "string"},
            },
            "required": ["udin", "amount", "contractor"],
        },
    },
    {
        "name": "run_concentrated_liquidity_sweep",
        "description": "Sweeps balances from regional sub-pools into corporate master treasury.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "sync_to_erp_systems",
        "description": "Broadcasts a committed transaction voucher to Frappe/ERPNext and Zoho Books.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tx_id": {"type": "string"},
                "erp_target": {"type": "string", "enum": ["FRAPPE", "ZOHO", "ALL"]},
            },
            "required": ["tx_id", "erp_target"],
        },
    },
]


async def dispatch_mcp_call(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name == "get_live_gl_balances":
        return {"balances": {k: str(v) for k, v in core_processor.accounts.items()}}

    elif tool_name == "process_rera_escrow_deposit":
        return core_processor.process_rera_waterfall(
            project_id=args["project_id"],
            payer_van=args["payer_van"],
            buyer_ref=args["buyer_ref"],
            gross_amount=Decimal(str(args["amount"])),
        )

    elif tool_name == "disburse_contractor_via_udin":
        return core_processor.verify_ca_udin_disbursement(
            udin=args["udin"],
            amount=Decimal(str(args["amount"])),
            contractor=args["contractor"],
        )

    elif tool_name == "run_concentrated_liquidity_sweep":
        return core_processor.execute_liquidity_sweep()

    elif tool_name == "sync_to_erp_systems":
        target = args["erp_target"]
        tx_id = args["tx_id"]
        record = next((item for item in core_processor.audit_log if item["tx_id"] == tx_id), None)
        if not record:
            return {"error": f"Transaction '{tx_id}' not found in audit logs"}

        results = {}
        if target in ["FRAPPE", "ALL"]:
            results["frappe"] = await erp_adapter.sync_journal_to_frappe(record)
        if target in ["ZOHO", "ALL"]:
            results["zoho"] = await erp_adapter.sync_journal_to_zoho(record)
        return results

    raise ValueError(f"Unknown tool declaration: {tool_name}")