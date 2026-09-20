from typing import Dict, Any, List

class ERPCompatibilityEngine:
    @staticmethod
    def get_erp_system_checklist(erp_name: str) -> Dict[str, Any]:
        """Provides enterprise client with pre-requisite integration parameters"""
        checklists = {
            "SAP_S4_HANA": {
                "connection_protocols": ["SAP IDoc (PEXR2002)", "RFC Gateway", "RESTful MTLS API"],
                "required_master_data": ["House Bank ID (FI-BL)", "Account ID", "EDI Partner Profile (WE20)"],
                "supported_clearing_formats": ["ISO 20022 camt.053", "ISO 20022 pain.001.001.03", "MT940 Flat File"],
                "reconciliation_latency": "Sub-second webhook or 30-min scheduled batch sync",
                "recommended_security": "Mutual TLS (mTLS) + IP Subnet Whitelist"
            },
            "ORACLE_NETSUITE": {
                "connection_protocols": ["SuiteTalk REST Web Services", "SuiteScript 2.1 Hooks"],
                "required_master_data": ["Subsidiary ID", "Bank Account GL Code", "Entity Internal ID"],
                "supported_clearing_formats": ["Custom TBG JSON Payload", "BAI2 File Specification"],
                "reconciliation_latency": "Asynchronous event-driven webhook execution",
                "recommended_security": "OAuth 1.0 / 2.0 Client Credentials with HMAC SHA256 Signature"
            },
            "MICROSOFT_DYNAMICS_365": {
                "connection_protocols": ["Dataverse Web API", "Azure Service Bus Integration"],
                "required_master_data": ["Legal Entity Code (DAT)", "Vendor Bank Account", "Cash and Bank Module Map"],
                "supported_clearing_formats": ["ISO 20022 XML", "TBG Standard Webhook Payload"],
                "reconciliation_latency": "Near real-time via Azure Event Grid",
                "recommended_security": "Azure Active Directory Bearer JWT + Tenant Key"
            }
        }
        return checklists.get(
            erp_name.upper(),
            {"error": "Unsupported ERP type. Standard JSON/MT940 available."}
        )

    @staticmethod
    def validate_erp_readiness(client_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Checks if enterprise payload has necessary accounting metadata before processing"""
        missing_fields = []
        required = ["erp_source", "gl_code", "cost_center", "currency", "idempotency_reference"]
        for field in required:
            if field not in client_payload:
                missing_fields.append(field)

        return {
            "is_compatible": len(missing_fields) == 0,
            "missing_prerequisites": missing_fields,
            "engine_support": "READY" if len(missing_fields) == 0 else "ACTION_REQUIRED"
        }
