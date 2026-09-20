import os
from typing import Dict, Any
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# 1. Define Hardened TBG Tools for the Agent
@tool
def trigger_enach_onboarding(debtor_name: str, debtor_account: str, max_amount: float) -> str:
    """Use when the client needs to setup recurring debits, EMI collection, or bank mandates."""
    return f"e-NACH Mandate generated successfully for {debtor_name}. Route: /api/v1/clearing/enach/register"

@tool
def lock_escrow_milestone(depositor: str, beneficiary: str, amount: float) -> str:
    """Use when transactions require multi-party conditional holding, RERA compliance, or milestone releases."""
    return f"Digital Escrow contract initialized for amount {amount}. Route: /api/v1/escrow/create"

@tool
def execute_liquidity_sweep(threshold: float) -> str:
    """Use when client wants to pool cash, eliminate idle branch balances, or auto-sweep virtual accounts."""
    return f"Liquidity Sweep protocol initiated with floor threshold {threshold}. Route: /api/v1/liquidity/auto-sweep"

# 2. Build the ReAct Agent
tools = [trigger_enach_onboarding, lock_escrow_milestone, execute_liquidity_sweep]
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# LangGraph agent automatically streams traces to LangSmith when environment variables are set
tbg_agent_executor = create_react_agent(model, tools)

async def run_traced_client_resolution(query: str) -> Dict[str, Any]:
    inputs = {"messages": [("user", query)]}
    result = await tbg_agent_executor.ainvoke(inputs)
    final_message = result["messages"][-1].content
    return {
        "resolution": final_message,
        "trace_logged": os.getenv("LANGCHAIN_TRACING_V2") == "true"
    }
