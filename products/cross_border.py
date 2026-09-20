import uuid
from typing import Dict

class CrossBorderRailEngine:
    def __init__(self):
        self.fx_rates = {
            "USD_INR": 86.40,
            "EUR_INR": 93.20,
            "GBP_INR": 109.80
        }
        self.nostro_accounts = {
            "NOSTRO_JPM_USD": 2500000.0,
            "NOSTRO_DB_EUR": 1800000.0
        }

    def process_outward_remittance(self, debtor_acc: str, foreign_bene_iban: str, currency: str, inr_amount: float, purpose_code: str):
        pair = f"{currency}_INR"
        if pair not in self.fx_rates:
            raise ValueError(f"Unsupported currency pair: {pair}")
        
        fx_rate = self.fx_rates[pair]
        target_fx_amount = round(inr_amount / fx_rate, 2)

        nostro_key = f"NOSTRO_JPM_{currency}" if currency == "USD" else f"NOSTRO_DB_{currency}"
        if nostro_key in self.nostro_accounts:
            self.nostro_accounts[nostro_key] -= target_fx_amount

        return {
            "swift_msg_id": f"MT103_{uuid.uuid4().hex[:10].upper()}",
            "purpose_code": purpose_code,
            "inr_debited": inr_amount,
            "fx_rate_applied": fx_rate,
            "target_currency": currency,
            "disbursed_to_iban": foreign_bene_iban,
            "settlement_rail": "CROSS_BORDER_NOSTRO_SETTLEMENT",
            "status": "DISPATCHED_TO_SWIFT"
        }
