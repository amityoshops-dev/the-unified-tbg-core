from fastapi import HTTPException
import re

class SecurityGateway:
    # 1. Double Allowlist: Allowed Commands + Allowed Argument Whitelist
    ALLOWED_COMMAND_BINARIES = {"check_balance", "auto_sweep", "disburse_escrow"}
    ALLOWED_ARGUMENT_PATTERNS = {
        "tenant_id": r"^[A-Z0-9_-]{3,20}$",
        "account_id": r"^[A-Z0-9_-]{3,30}$",
        "milestone_id": r"^[A-Z0-9_-]{3,20}$"
    }

    @staticmethod
    def verify_sender_and_tenant(caller_tenant: str, target_object_tenant: str, api_signature: str):
        """Guard against Ghost Sender (missing signature) and BOLA (mismatched tenant)"""
        if not api_signature or api_signature == "null" or len(api_signature) < 8:
            raise HTTPException(status_code=401, detail="SecurityAlert: Ghost Sender detected. Missing or invalid signature.")

        if caller_tenant != target_object_tenant:
            raise HTTPException(status_code=403, detail="SecurityAlert: BOLA violation detected. Cross-tenant access blocked.")

    @classmethod
    def double_whitelist_check(cls, command: str, arguments: dict):
        """Enforces Binary + Argument signature allowlists to block Shell Injections and halts"""
        if command not in cls.ALLOWED_COMMAND_BINARIES:
            raise HTTPException(status_code=400, detail=f"ExecutionHalted: Command '{command}' not in binary allowlist.")

        for key, val in arguments.items():
            if key in cls.ALLOWED_ARGUMENT_PATTERNS:
                pattern = cls.ALLOWED_ARGUMENT_PATTERNS[key]
                if not re.match(pattern, str(val)):
                    raise HTTPException(
                        status_code=400, 
                        detail=f"SecurityAlert: MCP Argument Injection blocked. Argument '{key}' failed signature whitelist."
                    )
        return True
