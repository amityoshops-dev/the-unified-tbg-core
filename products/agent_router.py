import os
from typing import Dict, Any
from langsmith import traceable

class FinancialAgentRouter:
    """
    Intelligent TBG Financial Dispatcher.
    Every routing decision and parameter extraction is automatically traced to LangSmith.
    """

    @traceable(name="TBG_Product_Resolution_Agent", run_type="chain")
    def route_client_problem(self, client_query: str) -> Dict[str, Any]:
        query = client_query.lower()

        if any(w in query for w in ["emi", "recurring", "debit borrower", "nach", "enach", "mandate", "ach"]):
            return {
                "identified_product": "NACH / e-NACH Mandate & Clearing Engine",
                "target_endpoint": "/api/v1/clearing/enach/register",
                "clearing_type": "NPCI_MANDATE_BATCH",
                "reasoning": "Client requires recurring pull of funds or batch debit authority under NPCI or FedACH frameworks.",
                "required_onboarding_inputs": ["Debtor Account", "IFSC / Routing Number", "Max Mandate Limit", "Auth Mode"]
            }

        if any(w in query for w in ["hold fund", "milestone", "rera", "builder", "trustee", "escrow", "conditional"]):
            return {
                "identified_product": "Digital Escrow & Multi-Sig Rails",
                "target_endpoint": "/api/v1/escrow/create",
                "clearing_type": "NODAL_ESCROW_VAULT",
                "reasoning": "Client requires conditional fund locking with tripartite trustee approval mechanics.",
                "required_onboarding_inputs": ["Depositor ID", "Beneficiary ID", "Trustee Signature Key", "Milestone Target Breakdown"]
            }

        if any(w in query for w in ["salary", "vendor payout", "bulk", "batch disburse", "thousands of payments"]):
            return {
                "identified_product": "High-Volume Bulk Payout Engine",
                "target_endpoint": "/api/v1/bulk-payout/dispatch",
                "clearing_type": "NEFT_RTGS_IMPS_BATCH",
                "reasoning": "High-concurrency outbound credit rail required with batch-level deduplication and per-line UTR tracing.",
                "required_onboarding_inputs": ["Debit Account", "Beneficiary Array", "Batch Total Pre-funded Amount"]
            }

        if any(w in query for w in ["sweep", "idle cash", "pool money", "branch balances", "virtual account concentration"]):
            return {
                "identified_product": "Two-Way Liquidity Sweep Engine",
                "target_endpoint": "/api/v1/liquidity/auto-sweep",
                "clearing_type": "INTERNAL_TREASURY_TRANSFER",
                "reasoning": "Treasury optimization required to prevent idle funds at branch accounts and maximize yield.",
                "required_onboarding_inputs": ["Master Operating Pool Account", "Virtual Account Register", "Sweep Threshold Floor"]
            }

        if any(w in query for w in ["cross border", "swift", "foreign", "usd", "remittance", "import", "export"]):
            return {
                "identified_product": "Cross-Border FX & Nostro Rail",
                "target_endpoint": "/api/v1/trade/cross-border-remittance",
                "clearing_type": "SWIFT_MT103_NOSTRO",
                "reasoning": "Outward foreign exchange settlement requiring purpose code tagging (RBI FETERS) and SWIFT MT103 generation.",
                "required_onboarding_inputs": ["Debtor INR Account", "Foreign Beneficiary IBAN/SWIFT", "RBI Purpose Code"]
            }

        return {
            "identified_product": "Payment Gateway & Custom Virtual Collections",
            "target_endpoint": "/api/v1/pg/order/create",
            "clearing_type": "MULTI_RAIL_GATEWAY",
            "reasoning": "General inflow requirement detected; falling back to unified multi-rail collection gateway.",
            "required_onboarding_inputs": ["Amount", "Client Reference ID", "Webhook Destination URL"]
        }
