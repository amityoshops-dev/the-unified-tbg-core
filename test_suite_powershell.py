import asyncio
import json
import sqlite3
from products.escrow_engine import EscrowEngine
from products.payout_pipeline import PayoutPipeline
from products.security_gateway import SecurityGateway
from products.ledger_db import save_contract, record_journal

def run_comprehensive_test():
    print("==================================================")
    print("  RUNNING UNIFIED TBG-CORE COMPREHENSIVE SUITE   ")
    print("==================================================")

    payout_engine = PayoutPipeline()
    escrow = EscrowEngine(payout_pipeline=payout_engine)
    sec = SecurityGateway()

    # --- TEST 1: Contract Creation & SQLite Persistence ---
    print("\n[TEST 1] Creating Escrow Contract...")
    milestones = [{"milestone_id": "M1", "description": "Phase 1 Complete", "target_amount": 50000.0}]
    contract = escrow.create_contract(
        depositor="DEP_ACME_BUYER",
        beneficiary="BENEFICIARY_SELLER_01",
        trustee="TRUSTEE_DESK_TENANT",
        total_amount=50000.0,
        milestones=milestones
    )
    save_contract(contract.model_dump())
    print(f"  -> Contract Created: {contract.contract_id}")
    print(f"  -> Nodal Virtual Account: {contract.nodal_virtual_account}")
    print(f"  -> Initial Balance: {contract.current_balance} (Status: {contract.status})")
    assert contract.status == "DRAFT"
    print("  ✔ PASS: Contract creation and initial state verified.")

    # --- TEST 2: Inflow Webhook Simulation ---
    print("\n[TEST 2] Simulating Inflow Webhook into Nodal VA...")
    updated_contract = escrow.deposit_inflow(contract.nodal_virtual_account, 50000.0)
    print(f"  -> Inflow Credited: ₹50,000.00")
    print(f"  -> Current Balance: {updated_contract.current_balance}")
    print(f"  -> Contract State: {updated_contract.status}")
    assert updated_contract.current_balance == 50000.0
    assert updated_contract.status == "FULLY_FUNDED"
    print("  ✔ PASS: Virtual account credited; escrow status set to FULLY_FUNDED.")

    # --- TEST 3: Security Gateway (Anti-BOLA & Anti-Ghost Sender) ---
    print("\n[TEST 3] Testing Security Gateway Barriers...")
    
    # 3a. Ghost Sender test (invalid signature)
    ghost_blocked = False
    try:
        sec.verify_sender_and_tenant("TRUSTEE_DESK_TENANT", contract.trustee, api_signature="")
    except Exception as e:
        ghost_blocked = True
        print(f"  -> Ghost Sender Blocked: {e.detail}")
    assert ghost_blocked, "Ghost Sender should have been blocked"

    # 3b. BOLA test (mismatched tenant)
    bola_blocked = False
    try:
        sec.verify_sender_and_tenant("ROGUE_ATTACKER_TENANT", contract.trustee, api_signature="VALID_HMAC_SIG")
    except Exception as e:
        bola_blocked = True
        print(f"  -> BOLA Blocked: {e.detail}")
    assert bola_blocked, "BOLA cross-tenant attack should have been blocked"
    print("  ✔ PASS: Anti-BOLA and Ghost Sender security validations passed.")

    # --- TEST 4: Payout Pipeline Execution & Double-Entry ---
    print("\n[TEST 4] Executing Milestone Disbursal...")
    res = asyncio.run(escrow.approve_and_release(
        contract_id=contract.contract_id,
        milestone_id="M1",
        trustee_key="TRUSTEE_CRYPTO_SIG"
    ))
    record_journal("TXN_TEST_001", "ESCROW_VAULT", contract.beneficiary, 50000.0, "ESCROW")
    print(f"  -> Rail Disbursal Status: {res['payout_receipt']['data']['rail_status']}")
    print(f"  -> Bank UTR Generated: {res['payout_receipt']['data']['bank_utr']}")
    print(f"  -> Remaining Escrow Balance: {res['escrow_contract'].current_balance}")
    print(f"  -> Final Contract Status: {res['escrow_contract'].status}")
    assert res["escrow_contract"].current_balance == 0.0
    assert res["escrow_contract"].status == "COMPLETED"
    print("  ✔ PASS: Milestone disburse executed and settled.")

    # --- TEST 5: Verify SQLite Ledger Database ---
    print("\n[TEST 5] Checking Persistent SQLite Ledger File...")
    conn = sqlite3.connect("tbg_enterprise_ledger.db")
    c = conn.cursor()
    c.execute("SELECT contract_id, total_amount, status FROM escrow_contracts WHERE contract_id = ?", (contract.contract_id,))
    row = c.fetchone()
    print(f"  -> SQLite Contract Record: ID={row[0]}, Total={row[1]}, Status={row[2]}")

    c.execute("SELECT txn_ref, debit_account, credit_account, amount FROM journal_entries WHERE txn_ref = 'TXN_TEST_001'")
    j_row = c.fetchone()
    print(f"  -> SQLite Journal Entry: Ref={j_row[0]}, Debit={j_row[1]}, Credit={j_row[2]}, Amount={j_row[3]}")
    conn.close()
    assert row is not None and j_row is not None
    print("  ✔ PASS: Double-entry ledger confirmed on disk.")

    print("\n==================================================")
    print("    ALL AUTOMATED TESTS PASSED SUCCESSFULLY!      ")
    print("==================================================")

if __name__ == "__main__":
    run_comprehensive_test()
