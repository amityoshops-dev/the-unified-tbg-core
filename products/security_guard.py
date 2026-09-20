from fastapi import HTTPException

class SecurityGuard:
    @staticmethod
    def verify_tenant(contract_tenant: str, incoming_tenant: str):
        if contract_tenant != incoming_tenant:
            raise HTTPException(
                status_code=403, 
                detail="SecurityAlert: BOLA violation detected. Unauthorized tenant access."
            )
