# Loop Product Record

## Original problem statement
Build Loop, a production-quality mobile-first campus marketplace for one-time skills and underused physical resources, launching at NIT Andhra Pradesh. The core promise is: “Don't buy it. Don't learn it. Find someone who already can.” The MVP must prove onboarding → search → match → trust → hire/rent → mocked UPI payment → contact reveal → completion → review → reputation, plus failed-search requests and provider matching.

## Architecture decisions
- React frontend with a responsive five-area navigation: Home, Explore, Requests, Profile, Insights.
- FastAPI backend under `/api`, using the protected MongoDB environment configuration and deterministic seeded demo data.
- Institutional email OTP is intentionally MOCKED for the prototype with a challenge-bound `123456` code.
- Session authorization uses an HTTP-only cookie with bearer-token fallback for sensitive endpoints including payment, transaction actions, profile verification upload, and `/auth/me`.
- Emergent-managed Google authentication returns through a one-time fragment, exchanges server-side, and persists seven-day sessions in MongoDB.
- UPI/contact reveal is intentionally MOCKED behind the payment endpoint; transaction structure is ready for a regulated provider later.
- Matching is transparent, deterministic, and explanation-first; relevance is weighted over vanity metrics.

## User personas
- Harvey Specter: primary student demo user, Civil Engineering, student verification pending.
- Campus needer: searches for a one-time service or physical resource.
- Campus provider/resource owner: offers skills or underused equipment and builds public provider reputation.
- Lightweight campus operator: uses Insights to see demand and supply gaps.

## Core requirements (static)
- Search first, post second.
- Exactly three marketplace objects: profiles, requests, resource listings.
- NIT AP institutional affiliation, separate email and student verification.
- Services and resources remain mentally separate after a natural-language search.
- Contact data is transaction-specific and revealed only after payment.
- Provider reputation is public; customer reputation is private.
- Only completed transactions create reviews.
- Resource deposits are proportional and refundable on confirmed return.
- Mobile-first responsive experience with five primary navigation areas.

## What’s implemented (2026-03-10)
- Welcome → institutional email → OTP onboarding with NIT AP domain validation and demo code.
- Seeded home experience for Harvey Specter with popular services, resources, request discovery, and adaptive campus language.
- Search API and UI for service/resource results, deterministic match scores, “why this match” explanations, and no-results request creation.
- Provider detail pages with evidence-based trust badges, relevant work, reputation, price, and hire CTA.
- Request creation with budget/deadline/description, provider notification count, FCFS application-ready request model, and immediate request row updates.
- MOCKED UPI payment with secured status, contact reveal response, and resource rental duration/deposit breakdown.
- Transaction action endpoint, review endpoint, pending student-ID upload endpoint, notifications feedback, and Insights metrics/demand chart.
- Auth/session hardening: OTP challenge binding, sensitive endpoint authorization, environment-driven CORS policy.
- Responsive desktop sidebar and mobile bottom navigation, with tested mobile provider hiring and resource rental.

## Authentication update (2026-08-29)
- Added a first-class “Continue with Google” path through Emergent-managed Google authentication without user-managed API credentials.
- Added synchronous callback-fragment detection, backend-only session exchange, institutional-domain enforcement, callback error recovery, and automatic `/auth/me` session restoration.
- Google users are matched by email, assigned/reused stable `user_id` values, and stored with seven-day MongoDB sessions; MongoDB `_id` is excluded from responses.
- OTP fallback now sets the same HTTP-only session cookie and enforces a five-attempt, five-minute lockout that cannot be bypassed by requesting another code.
- Verification completed for the Google redirect entry, invalid callback handling, OTP fallback, cookie restoration, authenticated home load, clean frontend build, and `20/20` backend tests.
- A real institutional Google account was not provided, so the final provider consent-and-return step remains for controlled user verification; no Google password should be stored by Loop.

## Prioritized backlog
- P0: Run one controlled real institutional Google login to verify consent return and persisted Google session data end-to-end.
- P0: Build the FCFS provider application and needer selection flow, then persist requests, applications, transactions, notifications, and reviews in MongoDB with ownership checks.
- P1: Add admin verification workspace to approve/reject student ID submissions and portfolio evidence.
- P1: Add full transaction state UI for provider accepted, payment secured, contact revealed, completion, return confirmation, refund, disputes, and reviews.
- P1: Add persistent file/object storage for student IDs and portfolio evidence with authorization controls.
- P2: Add configurable college registry and matching weights so future campuses can be enabled by configuration.

## Remaining next tasks
1. Verify one real NIT Andhra Pradesh Google Workspace login in the preview app.
2. Build the complete FCFS provider application and needer selection screens for request fulfillment.
3. Persist demo and user-created marketplace state in MongoDB.
4. Add admin approval to transition Harvey from Pending to Student Verified.
5. Replace MOCKED UPI, OTP, and upload integrations with production providers when credentials and compliance requirements are available.