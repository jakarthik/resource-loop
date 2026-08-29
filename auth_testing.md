# Loop Auth Testing Playbook

Loop supports two login paths that both create a backend session (httpOnly cookie + bearer fallback):
1. Mock institutional-email OTP (demo code `123456`).
2. Emergent-managed Google Sign-in.

## Test User & Session (MongoDB)
```
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'harvey.test.' + Date.now() + '@student.nitandhra.ac.in',
  name: 'Harvey Specter',
  role: 'student',
  branch: 'Civil Engineering',
  year: '3rd Year',
  college: 'NIT Andhra Pradesh',
  email_verified: true,
  student_verified: true,
  verification_status: 'Verified',
  personalization: ['need','skill','resource'],
  onboarded: true,
  reputation: { rating: 0, gigs_completed: 0, reviews_count: 0 },
  seed: false,
  created_at: new Date().toISOString()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now()+7*24*60*60*1000).toISOString(),
  created_at: new Date().toISOString()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

## Backend API
```
curl -X GET  "$URL/api/auth/me" -H "Authorization: Bearer $TOKEN"
curl -X POST "$URL/api/auth/send-otp"   -H "Content-Type: application/json" -d '{"email":"harvey@student.nitandhra.ac.in"}'
curl -X POST "$URL/api/auth/verify-otp" -H "Content-Type: application/json" -d '{"email":"harvey@student.nitandhra.ac.in","otp":"123456"}'
```

## Browser (cookie) testing
```
await page.context.add_cookies([{ "name":"session_token","value":TOKEN,"domain":DOMAIN,"path":"/","httpOnly":true,"secure":true,"sameSite":"None"}])
```

## Rules
- user_id is a custom UUID; MongoDB _id is always excluded with `{"_id":0}`.
- Sessions are 7-day, timezone-aware.
- OTP: fixed demo code `123456`, 5-attempt / 5-minute lockout (HTTP 429).
- Google: session-data exchange is backend-only; no Google password stored.
- Institutional domain enforced: `@student.nitandhra.ac.in` (student) / `@nitandhra.ac.in` (faculty).
