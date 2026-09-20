import hmac
import hashlib
import time
import httpx
from fastapi import BackgroundTasks

WEBHOOK_SIGNING_SECRET = "tbg_enterprise_hmac_secret_2026"

class WebhookCallbackEngine:
    @staticmethod
    def sign_payload(payload_bytes: bytes) -> str:
        return hmac.new(WEBHOOK_SIGNING_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()

    @classmethod
    async def _dispatch(cls, client_url: str, event_type: str, data: dict):
        import json
        payload_str = json.dumps({"event": event_type, "timestamp": time.time(), "data": data})
        signature = cls.sign_payload(payload_str.encode())
        headers = {
            "Content-Type": "application/json",
            "X-TBG-Signature": signature,
            "X-TBG-Delivery-Time": str(time.time())
        }
        try:
            # 2.5s maximum timeout prevents upstream thread halts
            async with httpx.AsyncClient(timeout=2.5) as client:
                await client.post(client_url, content=payload_str, headers=headers)
        except Exception:
            pass  # Failsafe non-blocking execution

    @classmethod
    def queue_async_callback(cls, background_tasks: BackgroundTasks, client_url: str, event_type: str, data: dict):
        background_tasks.add_task(cls._dispatch, client_url, event_type, data)
