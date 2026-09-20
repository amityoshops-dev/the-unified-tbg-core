import uuid
from typing import Dict, Any

class PaymentGatewayRouter:
    def __init__(self):
        self.active_gateways = ["RAIL_HDFC_SMARTGATEWAY", "RAIL_AXIS_DIRECT", "RAIL_RAZORPAY_ENTERPRISE"]

    def create_collection_order(self, order_id: str, amount: float, customer_vpa_or_card: str, preferred_rail: str = None):
        selected_rail = preferred_rail if preferred_rail in self.active_gateways else self.active_gateways[0]
        
        # Simulates dynamic fallback routing
        return {
            "tbg_order_id": f"ORD_{uuid.uuid4().hex[:10].upper()}",
            "merchant_order_id": order_id,
            "order_amount": amount,
            "routed_rail": selected_rail,
            "payment_methods_enabled": ["UPI_INTENT", "NETBANKING", "CARDS", "EMI"],
            "status": "AWAITING_CUSTOMER_ACTION",
            "checkout_url": f"https://pay.tbgcore.internal/checkout/{order_id}"
        }
