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

## 2026-06 — HIGH PRIORITY friction-reduction (NRIAdda brief)
Focused, additive changes (no rebuild) to reduce button-click friction on the core need/provide/match/transaction loop. All existing Loop rules preserved (verification gate, FCFS, mock UPI, contact-reveal-after-payment, seed vs real records).

Backend (`server.py`, additive):
- `POST /intent/parse` — natural-language parsing infers intent (need/provide), category, kind, duration (days), and location from one line (e.g. "Need a drafter for 3 days near Civil Block").
- `POST /requests` now learns the user's need category/location, sets a 14-day `expires_at`, and returns proactive `matches` (services + resources ≥50%).
- `POST /provides` — real users publish a service (→providers) or resource (→resources) listing; matching open needs are counted/notified; provide category + location learned.
- `GET /opportunities` — reverse discovery: open needs (not mine) matching what I provide, with match% + applied flag. `GET /suggestions` — resources I may need based on learned need categories.
- In-context messaging: `GET/POST /threads/{ref}` attached to a request or transaction, with a canned auto-reply from seeded personas.
- Lifecycle + expiry: request lifecycle label (Open/Matched/Accepted/In progress/Completed/Cancelled/Expired), `POST /requests/{id}/renew`, `POST /requests/{id}/cancel`, lazy expiry on read.
- Location-aware + category-bonus matching in `match_score`; automatic profile learning via `learn()` ($addToSet user.learned.{need_categories, provide_categories, locations}).

Frontend (`App.js` + `App.css`, additive):
- Home rebuilt around two obvious intents ("I Need Something" / "I Can Provide Something") + a single smart composer: describe → confirm (editable category/days/location/budget chips) → post. Posting a need shows instant match cards inline (Hire / View).
- Reverse-discovery section "People who need what you provide" (Offer to Provide = FCFS apply, + Message) and "Resources you may need"; contextual prompt banner (add location / N strong matches).
- Slide-in Message drawer from opportunity cards, transaction cards, and applicant/campus rows.
- Requests: lifecycle badges + Cancel/Renew; Activity transaction cards gained inline quick-rating (1-tap stars) and Message.

Verification: backend endpoints curl-verified end-to-end (parse, matches, provides+notify, opportunities, messaging+auto-reply, renew/cancel/lifecycle); frontend compiles clean and the onboarding→home→composer flow ran with no React runtime errors. Full frontend E2E by the testing agent not run this pass (budget-constrained); recommend a UI pass before shipping.
