# TBG-CORE Working PRD

## 1. Product
Institutional Payment & Ledger Orchestration Workbench.

## 2. Objective
Translate a business payment requirement into a deterministic, auditable transaction plan and demonstrate the complete banking execution lifecycle in simulation/sandbox mode.

## 3. Core execution lifecycle
1. Business requirement capture
2. Requirement normalization
3. AI / rules interpretation
4. Intent classification
5. Candidate rail discovery
6. Rail selection
7. Eligibility validation
8. Compliance / policy checks
9. Mandate / beneficiary / account validation
10. Idempotency validation
11. Risk and limit checks
12. Liquidity / pool availability
13. Transaction initiation
14. Message construction
15. Rail adapter submission
16. Provider acknowledgement
17. State transition
18. Ledger impact
19. Pool movement / reservation
20. Settlement simulation
21. Reconciliation
22. Exception / retry handling
23. Webhook / event processing
24. Final transaction state
25. Audit trail
26. Operational metrics

## 4. Design principle
LLM interprets intent; deterministic TBG-CORE rules control eligibility, state changes and simulated financial postings.

## 5. Non-goals
No real customer funds, no production banking credentials, no autonomous money movement.

## 6. Acceptance criteria
A user can enter a business requirement and observe the complete lifecycle, inspect the selected rail, ledger entries, pool movement, reconciliation result, API request/response and audit events.
