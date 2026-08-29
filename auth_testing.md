# Loop authentication testing
- Institutional email validation: `POST /api/auth/send-otp`
- Demo email: `harvey@student.nitandhra.ac.in`
- Demo OTP: `123456`
- Verification: `POST /api/auth/verify-otp`
- Demo session response is returned for the prototype; no real email provider is connected.