# Loop authentication testing

## Emergent-managed Google sign-in
- OAuth entry: `https://auth.emergentagent.com/?redirect=<current-browser-origin>/`
- Callback: current app URL fragment `#session_id=...`
- Backend exchange: `POST /api/auth/google/session`
- Session check: `GET /api/auth/me` with the `session_token` cookie
- Google accounts must use `@student.nitandhra.ac.in` or `@nitandhra.ac.in`.
- Do not store Google passwords. Record only approved test identities in `memory/test_credentials.md`.

## Prototype OTP fallback
- Demo email: `harvey@student.nitandhra.ac.in`
- Demo OTP: `123456`
- Endpoints: `POST /api/auth/send-otp`, `POST /api/auth/verify-otp`

## Browser checks
1. Click Google sign-in and verify the browser returns to the current app origin.
2. Confirm the URL fragment is consumed and the session cookie is httpOnly.
3. Refresh and confirm `/api/auth/me` restores the signed-in user.
4. Confirm logout clears the cookie and returns to onboarding.