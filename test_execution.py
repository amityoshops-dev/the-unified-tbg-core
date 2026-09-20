import sys
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
