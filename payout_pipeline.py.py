from datetime import datetime
import uuid

class EscrowPayoutPipeline:
    def __init__(self, db_client, payment_rail_client):
        self.db = db_client
        self.rail = payment_rail_client

    async def execute_automated_payout(self, req: AutoPayoutRequest, tenant_id: str):
        # 1. Verify Idempotency Cache
        existing = self.db.get_payout_by_key(req.idempotency_key)
        if existing:
            return {"status": existing["status"], "utr": existing.get("utr"), "cached": True}

        # 2. Lock & Verify Escrow Contract
        contract = self.db.get_contract_for_update(req.contract_id)
        if contract["balance"] < req.payout_amount:
            raise ValueError("Insufficient escrow locked funds")

        # 3. Double-Entry Pre-Commit (State: RESERVED)
        txn_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"
        self.db.record_ledger_entry(
            txn_id=txn_id,
            source_acc=contract["escrow_account_num"],
            dest_acc=req.beneficiary_account_id,
            amount=req.payout_amount,
            status="IN_FLIGHT",
            idempotency_key=req.idempotency_key
        )
        self.db.decrement_balance(contract["id"], req.payout_amount)

        # 4. Dispatch to Rail with Idempotency Key
        try:
            rail_response = await self.rail.disburse(
                idempotency_key=req.idempotency_key,
                amount=req.payout_amount,
                account=req.beneficiary_account_id
            )
            # Confirmed Success
            self.db.update_status(txn_id, status="SETTLED", utr=rail_response["utr"])
            return {"status": "SETTLED", "utr": rail_response["utr"], "txn_id": txn_id}

        except TimeoutError:
            # Crucial: DO NOT fail or revert balance yet!
            self.db.update_status(txn_id, status="REQUIRES_RECONCILIATION")
            return {"status": "IN_FLIGHT", "message": "Payout pending rail reconciliation", "txn_id": txn_id}

        except Exception as e:
            # Reversible Failure from Rail
            self.db.increment_balance(contract["id"], req.payout_amount)
            self.db.update_status(txn_id, status="FAILED", error=str(e))
            raise e