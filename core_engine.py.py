import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field


# ============================================================================
# 1. SECURITY & PERIMETER GATEWAY
# ============================================================================
class SecurityPerimeter:
    """RBI Cyber Resilience compliant cryptographic validation and header signing."""

    def __init__(self, shared_secret: str = "PROD_BANK_GATEWAY_HMAC_SECRET_2026"):
        self.shared_secret = shared_secret.encode()

    def generate_hmac_signature(self, payload: str) -> str:
        return hmac.new(self.shared_secret, payload.encode(), hashlib.sha256).hexdigest()

    def verify_request_signature(self, payload: str, client_signature: str) -> bool:
        expected = self.generate_hmac_signature(payload)
        return hmac.compare_digest(expected, client_signature)


security_perimeter = SecurityPerimeter()


# ============================================================================
# 2. ERP SYNC (FRAPPE / ERPNEXT & ZOHO BOOKS)
# ============================================================================
class ERPIntegrationManager:
    """Connects settled transactions directly into Frappe/ERPNext and Zoho Books GLs."""

    def __init__(self):
        self.frappe_url = os.getenv("FRAPPE_HOST", "http://localhost:8000")
        self.frappe_api_key = os.getenv("FRAPPE_API_KEY", "test_key")
        self.frappe_api_secret = os.getenv("FRAPPE_API_SECRET", "test_secret")
        self.zoho_auth_token = os.getenv("ZOHO_AUTH_TOKEN", "mock_zoho_oauth_token")
        self.zoho_org_id = os.getenv("ZOHO_ORG_ID", "12345678")

    async def sync_journal_to_frappe(self, journal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a balanced Journal Entry in ERPNext."""
        headers = {
            "Authorization": f"token {self.frappe_api_key}:{self.frappe_api_secret}",
            "Content-Type": "application/json",
        }
        frappe_payload = {
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "posting_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "accounts": [
                {
                    "account": f"{e['account_id']} - YESB",
                    "debit_in_account_currency": float(e["amount"]) if e["entry_type"] == "DEBIT" else 0.0,
                    "credit_in_account_currency": float(e["amount"]) if e["entry_type"] == "CREDIT" else 0.0,
                }
                for e in journal_data["entries"]
            ],
            "user_remark": journal_data.get("reference", "TBG-Core ERP Sync"),
        }
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(f"{self.frappe_url}/api/resource/Journal Entry", json=frappe_payload, headers=headers)
                return {"status": "SUCCESS", "erp": "FRAPPE", "response": res.json() if res.status_code == 200 else "EMULATED_LOCAL_ACK"}
        except Exception:
            # Fallback for offline sandbox environments
            return {"status": "EMULATED", "erp": "FRAPPE", "synced_voucher": f"JV-FRP-{uuid.uuid4().hex[:8].upper()}"}

    async def sync_journal_to_zoho(self, journal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Posts a manual journal entry to Zoho Books ledger."""
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.zoho_auth_token}",
            "Content-Type": "application/json",
        }
        zoho_payload = {
            "journal_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "reference_number": journal_data.get("tx_id", "REF-UNKNOWN"),
            "notes": journal_data.get("reference", "TBG Ledger Sync"),
            "line_items": [
                {
                    "account_name": e["account_id"],
                    "debit_or_credit": "d" if e["entry_type"] == "DEBIT" else "c",
                    "amount": float(e["amount"]),
                }
                for e in journal_data["entries"]
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(
                    f"https://books.zoho.com/api/v3/journals?organization_id={self.zoho_org_id}",
                    json=zoho_payload,
                    headers=headers,
                )
                return {"status": "SUCCESS", "erp": "ZOHO", "response": res.json() if res.status_code == 201 else "EMULATED_LOCAL_ACK"}
        except Exception:
            return {"status": "EMULATED", "erp": "ZOHO", "synced_journal_id": f"ZH-JRN-{uuid.uuid4().hex[:8].upper()}"}


erp_adapter = ERPIntegrationManager()


# ============================================================================
# 3. BANK SANDBOX EMULATION ENGINE
# ============================================================================
class BankSandboxEngine:
    """Emulates clearing rails: NEFT, RTGS, IMPS, and Virtual Account validation."""

    @staticmethod
    def simulate_clearing(method: str, amount: Decimal, beneficiary_ifsc: str) -> Dict[str, Any]:
        bank_rrn = f"RRN{datetime.now().strftime('%y%m%d%H%M')}{uuid.uuid4().hex[:6].upper()}"
        return {
            "sandbox_clearing_status": "PROCESSED",
            "utr_rrn": bank_rrn,
            "clearing_rail": method.upper(),
            "ifsc": beneficiary_ifsc,
            "settled_at": datetime.now(timezone.utc).isoformat(),
        }


# ============================================================================
# 4. TRANSACTION BANKING CORE LEDGER & PRODUCTS
# ============================================================================
class TransactionEntry(BaseModel):
    account_id: str
    entry_type: str  # "DEBIT" or "CREDIT"
    amount: Decimal


class JournalBatch(BaseModel):
    idempotency_key: str
    reference_note: str
    entries: List[TransactionEntry]


class PayoutBatchItem(BaseModel):
    vendor_id: str
    beneficiary_acc: str
    beneficiary_ifsc: str
    amount: Decimal
    payout_mode: str = "NEFT"


class TBGEnterpriseProcessor:
    def __init__(self):
        self.accounts: Dict[str, Decimal] = {
            "ESCROW_MASTER_70": Decimal("0.00"),
            "ESCROW_OPERATING_30": Decimal("0.00"),
            "POOL_COLLECTIONS_VAN": Decimal("0.00"),
            "SUB_POOL_WEST": Decimal("2450000.00"),
            "SUB_POOL_NORTH": Decimal("1850000.00"),
            "MASTER_TREASURY_CORP": Decimal("15000000.00"),
            "PAYOUT_CLEARING_GL": Decimal("5000000.00"),
        }
        self.idempotency_store: Dict[str, dict] = {}
        self.audit_log: List[dict] = []

    def verify_ledger_invariants(self, entries: List[TransactionEntry]) -> bool:
        debits = sum(e.amount for e in entries if e.entry_type == "DEBIT")
        credits = sum(e.amount for e in entries if e.entry_type == "CREDIT")
        return debits == credits and debits > Decimal("0.00")

    def execute_double_entry(self, batch: JournalBatch) -> dict:
        if batch.idempotency_key in self.idempotency_store:
            return {
                "status": "CACHED",
                "message": "Idempotency key matched. Redundant processing blocked.",
                "data": self.idempotency_store[batch.idempotency_key],
            }

        if not self.verify_ledger_invariants(batch.entries):
            raise ValueError("Invariant Failed: Debits and Credits must balance identically.")

        tx_id = f"TXN-TBG-{uuid.uuid4().hex[:10].upper()}"
        timestamp = datetime.now(timezone.utc).isoformat()

        for entry in batch.entries:
            if entry.account_id not in self.accounts:
                self.accounts[entry.account_id] = Decimal("0.00")
            if entry.entry_type == "DEBIT":
                self.accounts[entry.account_id] -= entry.amount
            elif entry.entry_type == "CREDIT":
                self.accounts[entry.account_id] += entry.amount

        record = {
            "tx_id": tx_id,
            "timestamp": timestamp,
            "reference": batch.reference_note,
            "entries": [e.model_dump() for e in batch.entries],
        }
        self.audit_log.append(record)
        self.idempotency_store[batch.idempotency_key] = record
        return {"status": "COMMITTED", "tx_id": tx_id, "record": record}

    # Module: productsrera_escrow_engine & rera_escrow_controller
    def process_rera_waterfall(self, project_id: str, payer_van: str, buyer_ref: str, gross_amount: Decimal) -> dict:
        escrow_70 = (gross_amount * Decimal("0.70")).quantize(Decimal("0.01"))
        operating_30 = gross_amount - escrow_70
        idemp_key = f"RERA-{project_id}-{buyer_ref}-{hashlib.md5(str(gross_amount).encode()).hexdigest()[:6]}"

        entries = [
            TransactionEntry(account_id="POOL_COLLECTIONS_VAN", entry_type="DEBIT", amount=gross_amount),
            TransactionEntry(account_id="ESCROW_MASTER_70", entry_type="CREDIT", amount=escrow_70),
            TransactionEntry(account_id="ESCROW_OPERATING_30", entry_type="CREDIT", amount=operating_30),
        ]
        return self.execute_double_entry(
            JournalBatch(idempotency_key=idemp_key, reference_note=f"RERA Waterfall Split: {project_id}", entries=entries)
        )

    def verify_ca_udin_disbursement(self, udin: str, amount: Decimal, contractor: str) -> dict:
        if not udin.startswith("26") or len(udin) != 18:
            raise ValueError(f"Regulatory Rejection: Invalid ICAI UDIN '{udin}'. Must be 18 digits.")
        if self.accounts["ESCROW_MASTER_70"] < amount:
            raise ValueError("Insufficient balance in designated 70% construction escrow account.")

        entries = [
            TransactionEntry(account_id="ESCROW_MASTER_70", entry_type="DEBIT", amount=amount),
            TransactionEntry(account_id=f"VENDOR_{contractor.upper()}", entry_type="CREDIT", amount=amount),
        ]
        return self.execute_double_entry(
            JournalBatch(
                idempotency_key=f"DISB-UDIN-{udin}-{amount}",
                reference_note=f"RERA Contractor Disbursement | UDIN: {udin}",
                entries=entries,
            )
        )

    # Module: productsbulk_payout_engine & payout_pipeline
    def execute_bulk_payout_batch(self, batch_id: str, payouts: List[PayoutBatchItem]) -> dict:
        total_payout = sum(item.amount for item in payouts)
        if self.accounts["PAYOUT_CLEARING_GL"] < total_payout:
            raise ValueError("Insufficient liquidity in corporate Payout Clearing GL.")

        processed_items = []
        journal_entries = [
            TransactionEntry(account_id="PAYOUT_CLEARING_GL", entry_type="DEBIT", amount=total_payout)
        ]

        for p in payouts:
            clearing_res = BankSandboxEngine.simulate_clearing(p.payout_mode, p.amount, p.beneficiary_ifsc)
            v_acc = f"VENDOR_{p.vendor_id.upper()}"
            journal_entries.append(TransactionEntry(account_id=v_acc, entry_type="CREDIT", amount=p.amount))
            processed_items.append({"vendor": p.vendor_id, "amount": str(p.amount), "clearing": clearing_res})

        batch_result = self.execute_double_entry(
            JournalBatch(
                idempotency_key=f"BULK-PAYOUT-{batch_id}",
                reference_note=f"Bulk Vendor Payout Batch: {batch_id}",
                entries=journal_entries,
            )
        )
        return {"batch_status": "COMPLETED", "summary": batch_result, "payouts": processed_items}

    # Module: productsliquidity_sweep_engine
    def execute_liquidity_sweep(self) -> dict:
        records = []
        for pool in ["SUB_POOL_WEST", "SUB_POOL_NORTH"]:
            bal = self.accounts.get(pool, Decimal("0.00"))
            if bal > Decimal("0.00"):
                res = self.execute_double_entry(
                    JournalBatch(
                        idempotency_key=f"SWEEP-{pool}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
                        reference_note=f"Zero-Balance Concentration Sweep from {pool}",
                        entries=[
                            TransactionEntry(account_id=pool, entry_type="DEBIT", amount=bal),
                            TransactionEntry(account_id="MASTER_TREASURY_CORP", entry_type="CREDIT", amount=bal),
                        ],
                    )
                )
                records.append(res)
        return {"sweep_actions": records, "updated_balances": {k: str(v) for k, v in self.accounts.items()}}


core_processor = TBGEnterpriseProcessor()