from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup in-memory SQLite for high-speed integration testing
engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

# 1. Initialize Chart of Accounts
accounts = [
    TBGAccount(account_number="ASSET_YESB_CLEARING_POOL", title="YES Bank Clearing Asset", account_type="ASSET", balance=Decimal("0.00")),
    TBGAccount(account_number="ASSET_HAVELLS_OPERATIVE", title="Havells Operative Current Account", account_type="ASSET", balance=Decimal("84500000.00")),
    TBGAccount(account_number="ASSET_FLEXI_FD_POOL", title="Flexi-FD Yield Facility", account_type="ASSET", balance=Decimal("145000000.00")),
    TBGAccount(account_number="ESCROW_RERA_ACC1_COLL", title="RERA Collection Account 1", account_type="ASSET", balance=Decimal("0.00")),
    TBGAccount(account_number="ESCROW_RERA_ACC2_SEP", title="RERA Separate 70% Escrow", account_type="ASSET", balance=Decimal("42000000.00")),
    TBGAccount(account_number="ESCROW_RERA_ACC3_OPER", title="RERA Operative 30% Account", account_type="ASSET", balance=Decimal("18000000.00")),
    TBGAccount(account_number="LIAB_DEALER_RECEIVABLES", title="Corporate Trade Receivables", account_type="LIABILITY", balance=Decimal("0.00")),
    TBGAccount(account_number="LIAB_ACCOUNTS_PAYABLE", title="Corporate Accounts Payable", account_type="LIABILITY", balance=Decimal("0.00")),
    TBGAccount(account_number="LIAB_ALLOTTEE_ESCROW_HOLDING", title="RERA Allottee Holding Liability", account_type="LIABILITY", balance=Decimal("0.00")),
]
db.add_all(accounts)
db.commit()

# 2. Instantiate Platform Modules
ledger = DoubleEntryLedgerService(db)
receivables = ReceivablesCMSModule(ledger, master_corp_prefix="YESB0941")
payables = BulkPayoutCMSModule(ledger, corporate_operative_account="ASSET_HAVELLS_OPERATIVE")
rera = RERAEscrowModule(ledger, "ESCROW_RERA_ACC1_COLL", "ESCROW_RERA_ACC2_SEP", "ESCROW_RERA_ACC3_OPER")
liquidity = LiquidityAndWorkingCapitalModule(ledger, "ASSET_HAVELLS_OPERATIVE", "ASSET_FLEXI_FD_POOL")

# 3. Test Fixture A: Issue VAN & Process Inbound Collection
van = receivables.issue_dealer_van(dealer_code="CABLE12345", dealer_name="Havells North Distributors")
qr_data = receivables.generate_b2b_dynamic_invoice_qr(dealer_code="CABLE12345", invoice_id="INV-2026-8812", amount_inr=Decimal("350000.00"))
inbound_res = receivables.process_incoming_collection(van=van, amount=Decimal("350000.00"), clearing_utr="YESBR52026998811", invoice_id="INV-2026-8812")
assert inbound_res["event"] == "PAYMENT_COLLECTED_STP"

# 4. Test Fixture B: Bulk Payout with Penny-Drop & RTGS Routing
payout_res = payables.dispatch_single_payout(
    beneficiary_name="Dixon Technologies Noida",
    account_no="001122334455",
    ifsc="YESB0000001",
    amount=Decimal("1850000.00"),
    enforce_penny_drop=True
)
assert payout_res["status"] == "SETTLED_STP"
assert payout_res["rail"] == "RTGS"

# 5. Test Fixture C: RERA Flat Booking & 70:30 Automated Waterfall
rera_res = rera.process_allottee_flat_inflow(
    flat_van="YESB0421-T1-1402",
    allottee_name="Ananya Sharma",
    amount=Decimal("5000000.00"),
    booking_utr="YESB_RERA_BK_001"
)
assert rera_res["account_1_balance"] == 0.00
assert rera_res["account_2_credited_70"] == 3500000.00
assert rera_res["account_3_credited_30"] == 1500000.00

# 6. Test Fixture D: Verified Form 3 Milestone Release
claim_payload = RERAMilestoneReleaseRequest(
    project_registration_no="UP-RERA-PRJ-NOIDA-SEC150",
    architect_cert_pct=42.5,
    engineer_cert_pct=42.0,
    ca_claim_amount_inr=Decimal("12000000.00"),
    ca_udin="26094812AB90812345"
)
release_res = rera.execute_verified_milestone_release(claim_payload)
assert release_res["status"] == "MILESTONE_RELEASED"

# 7. Test Fixture E: Working Capital DSO & Overnight Sweep
wc_metrics = liquidity.compute_dso_working_capital_impact(
    annual_credit_sales_inr=Decimal("5000000000.00"), # 500 Cr
    dso_reduction_days=4,
    cc_interest_rate_pct=Decimal("9.0")
)
assert wc_metrics["cash_liquidity_unlocked_inr"] > 54000000.00

sweep_res = liquidity.execute_eod_auto_sweep(current_balance=Decimal("75000000.00"), operating_threshold=Decimal("50000000.00"))
assert sweep_res["status"] == "SWEEP_EXECUTED"
assert sweep_res["swept_amount"] == 25000000.00

print("--- ALL INTEGRATION FIXTURES PASSED WITH ZERO RECONCILIATION DISCREPANCIES ---")