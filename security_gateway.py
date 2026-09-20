import base64
import time
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate
from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader

app = FastAPI(title="YES Bank TBG API Gateway", version="2026.3.0")

# Approved egress IP ranges for corporate client datacenter
ALLOWED_CIDR_GATEWAYS = {"103.14.120.45", "103.14.120.46", "127.0.0.1"}

SIGNATURE_HEADER = APIKeyHeader(name="X-Bank-PKI-Signature", auto_error=True)
TIMESTAMP_HEADER = APIKeyHeader(name="X-Bank-Timestamp", auto_error=True)
CLIENT_ID_HEADER = APIKeyHeader(name="X-Bank-Client-ID", auto_error=True)

# Loaded at boot from HSM or Keycloak Certificate TrustStore
with open("certs/client_corp_cert.pem", "rb") as cert_file:
    CLIENT_PUBLIC_CERT = load_pem_x509_certificate(cert_file.read())

async def enforce_rbi_cyber_perimeter(
    request: Request,
    signature: str = Security(SIGNATURE_HEADER),
    req_timestamp: str = Security(TIMESTAMP_HEADER),
    client_id: str = Security(CLIENT_ID_HEADER)
):
    # Gate 1: Static IP CIDR Whitelist Check
    client_ip = request.client.host
    if client_ip not in ALLOWED_CIDR_GATEWAYS:
        raise HTTPException(status_code=403, detail="ERR_TBG_IP_NOT_WHITELISTED")

    # Gate 2: Replay-Attack Prevention (300-second drift limit)
    current_time = int(time.time())
    try:
        sent_time = int(req_timestamp)
        if abs(current_time - sent_time) > 300:
            raise HTTPException(status_code=401, detail="ERR_TBG_TIMESTAMP_DRIFT_EXCEEDED")
    except ValueError:
        raise HTTPException(status_code=400, detail="ERR_TBG_INVALID_TIMESTAMP")

    # Gate 3: RSA-SHA256 PKI Payload Signature Verification
    payload_body = await request.body()
    # Canonical string: client_id + "." + timestamp + "." + body
    canonical_data = f"{client_id}.{req_timestamp}.".encode("utf-8") + payload_body
    
    try:
        raw_sig = base64.b64decode(signature)
        public_key = CLIENT_PUBLIC_CERT.public_key()
        public_key.verify(
            raw_sig,
            canonical_data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
    except Exception:
        raise HTTPException(status_code=401, detail="ERR_TBG_CRYPTOGRAPHIC_SIGNATURE_INVALID")

    return True