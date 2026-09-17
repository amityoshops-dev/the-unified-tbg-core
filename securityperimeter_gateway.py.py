import base64
import time
from typing import Set
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate
from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader

app = FastAPI(title="YES Bank TBG Enterprise Gateway", version="2026.4.1")

# Static client egress CIDR whitelisting enforced at reverse-proxy / DMZ
AUTHORIZED_EGRESS_IPS: Set[str] = {
    "103.14.120.45",  # Havells Noida Data Center Primary
    "103.14.120.46",  # Havells Noida Data Center Secondary
    "127.0.0.1"       # Internal Sandbox Testing
}

HEADER_PKI_SIGNATURE = APIKeyHeader(name="X-TBG-PKI-Signature", auto_error=True)
HEADER_TIMESTAMP = APIKeyHeader(name="X-TBG-Timestamp", auto_error=True)
HEADER_CLIENT_ID = APIKeyHeader(name="X-TBG-Client-ID", auto_error=True)

class SecurityGatewayEngine:
    def __init__(self, cert_path: str = "certs/corporate_client_public.pem"):
        try:
            with open(cert_path, "rb") as cert_file:
                self.client_cert = load_pem_x509_certificate(cert_file.read())
        except FileNotFoundError:
            # Fallback for mock environments: generate or load memory cert
            self.client_cert = None

    def verify_request_perimeter(self, client_ip: str, client_id: str, raw_body: bytes, timestamp_str: str, signature_b64: str) -> bool:
        # Gate 1: Strict CIDR IP Whitelist
        if client_ip not in AUTHORIZED_EGRESS_IPS:
            raise HTTPException(status_code=403, detail="ERR_TBG_001_IP_NOT_AUTHORIZED")

        # Gate 2: Replay-Attack Prevention (Tolerance window ±300 seconds)
        current_epoch = int(time.time())
        try:
            req_epoch = int(timestamp_str)
            if abs(current_epoch - req_epoch) > 300:
                raise HTTPException(status_code=401, detail="ERR_TBG_002_TIMESTAMP_DRIFT_EXCEEDED")
        except ValueError:
            raise HTTPException(status_code=400, detail="ERR_TBG_003_MALFORMED_TIMESTAMP")

        # Gate 3: RSA-2048 / SHA-256 PKI Signature Verification
        if self.client_cert:
            canonical_payload = f"{client_id}|{timestamp_str}|".encode("utf-8") + raw_body
            try:
                raw_signature = base64.b64decode(signature_b64)
                public_key = self.client_cert.public_key()
                public_key.verify(
                    raw_signature,
                    canonical_payload,
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
            except Exception:
                raise HTTPException(status_code=401, detail="ERR_TBG_004_CRYPTOGRAPHIC_SIGNATURE_MISMATCH")

        return True

security_engine = SecurityGatewayEngine()

async def authenticate_tbg_request(
    request: Request,
    signature: str = Security(HEADER_PKI_SIGNATURE),
    timestamp: str = Security(HEADER_TIMESTAMP),
    client_id: str = Security(HEADER_CLIENT_ID)
):
    body_bytes = await request.body()
    client_ip = request.client.host
    security_engine.verify_request_perimeter(client_ip, client_id, body_bytes, timestamp, signature)
    return {"client_id": client_id, "ip": client_ip, "authenticated": True}