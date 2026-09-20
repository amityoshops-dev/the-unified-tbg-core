from decimal import Decimal
from typing import Dict, Any

class LiquidityAndWorkingCapitalModule:
    def __init__(self, ledger_engine, operative_account: str, flexi_fd_pool: str):
        self.ledger = ledger_engine
        self.operative_account = operative_account
        self.flexi_fd_pool = flexi_fd_pool

    @staticmethod
    def compute_dso_working_capital_impact(annual_credit_sales_inr: Decimal, dso_reduction_days: int, cc_interest_rate_pct: Decimal = Decimal("9.0")) -> Dict[str, Any]:
        """
        DSO = (Accounts Receivable / Total Credit Sales) * 365
        Cash Released = (Delta DSO / 365) * Annual Credit Sales
        Interest Saved = Cash Released * CC Rate
        """
        daily_sales = annual_credit_sales_inr / Decimal("365")
        liquidity_cash_unlocked = daily_sales * Decimal(str(dso_reduction_days))
        annual_interest_savings = liquidity_cash_unlocked * (cc_interest_rate_pct / Decimal("100"))

        return {
            "annual_sales": float(annual_credit_sales_inr),
            "dso_days_saved": dso_reduction_days,
            "cash_liquidity_unlocked_inr": float(liquidity_cash_unlocked.quantize(Decimal("0.01"))),
            "annual_interest_saved_inr": float(annual_interest_savings.quantize(Decimal("0.01"))),
            "effective_roi_summary": f"Reducing DSO by {dso_reduction_days} days unlocks ₹{liquidity_cash_unlocked/Decimal('10000000'):.2f} Cr in liquidity."
        }

    def execute_eod_auto_sweep(self, current_balance: Decimal, operating_threshold: Decimal = Decimal("5000000.00")) -> Dict[str, Any]:
        """Sweeps idle cash above operating threshold into 6.85% overnight Flexi-FD facility"""
        if current_balance <= operating_threshold:
            return {"status": "NO_SWEEP_REQUIRED", "swept_amount": 0.00}

        sweep_amount = current_balance - operating_threshold
        sweep_utr = f"SWEEP_OUT_{uuid.uuid4().hex[:8].upper()}"

        # Debit: Flexi-FD Asset (earning yield)
        # Credit: Operative Current Account
        self.ledger.post_balanced_transaction(
            utr=sweep_utr,
            narration="EOD Automated Sweep into Flexi-FD Liquidity Facility",
            dr_account=self.flexi_fd_pool,
            cr_account=self.operative_account,
            amount=sweep_amount
        )

        return {
            "status": "SWEEP_EXECUTED",
            "swept_amount": float(sweep_amount),
            "operating_balance_retained": float(operating_threshold),
            "yield_rate": "6.85% p.a."
        }