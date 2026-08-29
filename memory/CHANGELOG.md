# Loop Changelog

## 2026-06 — Prototype flows made real (dark theme retained)
Recreated the attached `loop_demo.html` / `loop_v2_fixed.html` prototype as a functional app on top of the existing dark/lime theme (per user choice — theme NOT replaced).

Backend (`server.py`) fully rewritten to persist per-user in MongoDB:
- Auth: mock OTP (`123456`) now creates/looks-up a real user + 7-day session; Google sign-in retained; 5-attempt OTP lockout kept.
- Onboarding persistence: `PUT /profile`, `PUT /profile/personalization` (sets `onboarded`).
- Verification: `POST /verification/upload` (Emergent Object Storage), `GET /verification/file/{id}`, `POST /verification/approve` (mock campus-admin). Verification is a **transaction gate** — unverified students get 403 on hire/rent/post/apply.
- Marketplace: `GET /home`, `GET /search` (token-overlap match_score, resource tag match, `drone` => no_match), `GET /providers/{id}`.
- Requests + FCFS: `POST/GET /requests`, `POST /requests/{id}/apply` (ordered FCFS applications), `POST /requests/{id}/select/{appId}` (needer chooses, creates hire tx).
- Transactions: `POST /transactions/hire`, `POST /transactions/rent`, `GET /transactions`, `POST /transactions/{id}/action` with full state machines:
  - Service: HIRE_REQUESTED → PROVIDER_ACCEPTED → PAYMENT_SECURED (contact reveal) → PROVIDER_COMPLETED → COMPLETED.
  - Resource: RENTAL_REQUESTED → OWNER_ACCEPTED → PAYMENT_SECURED (contact/pickup reveal + deposit held) → PICKED_UP → RETURNED → RETURN_CONFIRMED/COMPLETED (deposit refunded).
- Reviews: `POST /reviews` (only COMPLETED tx; recomputes provider rating). Insights: `GET /insights`.
- Seeding: providers/resources/requests/applications seeded with `seed:true` to distinguish demo from real user-created records.

Frontend (`App.js` + `App.css`):
- Dark-themed 5-step split-screen onboarding (welcome/email → OTP → profile → student-ID upload → personalize) + Google button.
- Explore search results with live match %, no-match empty state.
- Requests screen with tabs: My requests (+ FCFS applicant list & select), Campus (apply FCFS), Activity (transaction cards driving the full state machines + review modal).
- Profile with verification callout (upload + demo approve), trust-at-a-glance, reputation stats. Logout on sidebar + mobile header.

Testing: iteration_6 — backend 20/20 pytest pass, frontend E2E pass (100%/100%), no open issues.
