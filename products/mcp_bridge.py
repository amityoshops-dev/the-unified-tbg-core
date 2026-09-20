class MCPToolBridge:
    """Implements Model Context Protocol (MCP) tool exposure with schema validation"""
    def __init__(self, escrow_engine, sweep_engine, security_guard):
        self.escrow = escrow_engine
        self.sweep = sweep_engine
        self.sec = security_guard

    def list_mcp_tools(self):
        return [
            {
                "name": "check_balance",
                "description": "Inspects active balance of an escrow contract safely.",
                "input_schema": {
                    "type": "object",
                    "properties": {"tenant_id": {"type": "string"}, "account_id": {"type": "string"}},
                    "required": ["tenant_id", "account_id"]
                }
            },
            {
                "name": "auto_sweep",
                "description": "Executes liquidity pooling across virtual accounts.",
                "input_schema": {
                    "type": "object",
                    "properties": {"tenant_id": {"type": "string"}},
                    "required": ["tenant_id"]
                }
            }
        ]

    async def execute_mcp_tool(self, tool_name: str, arguments: dict, tenant_id: str):
        # Enforce Double Whitelisting Check
        self.sec.double_whitelist_check(tool_name, arguments)
        
        if tool_name == "check_balance":
            acc_id = arguments.get("account_id")
            contract = self.escrow.contracts.get(acc_id)
            if not contract:
                return {"error": "Account not found"}
            self.sec.verify_sender_and_tenant(tenant_id, contract.trustee, "VALID_MCP_SIG")
            return {"account_id": acc_id, "balance": contract.current_balance, "status": contract.status}
        
        elif tool_name == "auto_sweep":
            return self.sweep.execute_auto_sweep()
        
        return {"error": "Unknown tool"}
