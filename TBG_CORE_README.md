# TBG-CORE â€” Institutional Payment & Ledger Orchestration Workbench

## What this build demonstrates

TBG-CORE translates a business payment requirement into a controlled, auditable banking execution flow.

### Core flow

Business Requirement
â†’ Requirement Normalization
â†’ AI / Rules Interpretation
â†’ Intent Classification
â†’ Candidate Rail Discovery
â†’ Rail Selection
â†’ Eligibility Validation
â†’ Compliance / Policy Checks
â†’ Mandate / Beneficiary / Account Validation
â†’ Idempotency Check
â†’ Risk / Limits Check
â†’ Liquidity / Pool Availability
â†’ Transaction Initiation
â†’ Message Construction
â†’ Rail Adapter Submission
â†’ Provider Acknowledgement
â†’ State Transition
â†’ Ledger Impact
â†’ Pool Movement / Reservation
â†’ Settlement
â†’ Reconciliation
â†’ Exception / Retry
â†’ Final State
â†’ Audit
â†’ Operational Metrics

## Workbench tabs

1. Command Center â€” end-to-end lifecycle
2. Simulator â€” execute a business requirement
3. Products â€” 9 modeled rails
4. Architecture â€” engine and control layers
5. API Lab â€” API contract and sample request
6. API Docs â€” Swagger/OpenAPI endpoints
7. Postman â€” downloadable collection
8. PRD â€” working product requirements
9. LLM Lab â€” provider configuration and routing policy
10. Sandbox â€” simulation/sandbox controls
11. Audit â€” transaction event trail

## Smoke-test example

Requirement:
"Client needs to debit INR 10000 loan EMI every month on the 5th via bank mandate"

Expected:
- Intent: EMI_COLLECTION
- Rail: NACH
- Mode: simulation
- Result: SIMULATED_SUCCESS

## Local execution

```powershell
streamlit run tbg_core_simulator.py
```

API:

```powershell
python -m uvicorn tbg_core_api:app --reload --port 8010
```

Swagger:

```text
http://127.0.0.1:8010/docs
```

OpenAPI:

```text
http://127.0.0.1:8010/openapi.json
```

## Postman

Import:

```text
postman\TBG-CORE.postman_collection.json
```

Run:

1. Health
2. Route Requirement
3. Execute Simulation
4. Copy transaction_id
5. Get Transaction

## LLM control model

The LLM is used for interpretation and candidate suggestions.

It does not directly control simulated financial execution.

```text
LLM
 â†“
Intent / candidate rails
 â†“
Deterministic TBG-CORE rules
 â†“
Eligibility / policy / risk / liquidity
 â†“
Transaction orchestration
 â†“
Ledger / pool / reconciliation / audit
```

## Render architecture

Two services:

- TBG-CORE API â€” FastAPI, Swagger, OpenAPI, Postman
- TBG-CORE Simulator â€” Streamlit workbench

No production banking credentials or real customer funds are used by this demo.
