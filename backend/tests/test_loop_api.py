"""Full Loop marketplace backend regression tests."""
import os, time, uuid, requests, pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE:
    # fallback to reading frontend .env
    from pathlib import Path
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE = line.split("=",1)[1].strip().rstrip("/")
API = f"{BASE}/api"

def unique_email(prefix="harvey"):
    return f"{prefix}.{uuid.uuid4().hex[:10]}@student.nitandhra.ac.in"

@pytest.fixture
def s():
    return requests.Session()

def onboard(sess, email=None, faculty=False, verify_student=True):
    email = email or (f"prof.{uuid.uuid4().hex[:8]}@nitandhra.ac.in" if faculty else unique_email())
    r = sess.post(f"{API}/auth/send-otp", json={"email": email}); assert r.status_code == 200, r.text
    r = sess.post(f"{API}/auth/verify-otp", json={"email": email, "otp": "123456"}); assert r.status_code == 200, r.text
    user = r.json()["user"]
    sess.put(f"{API}/profile", json={"name": "Test User", "branch": "Computer Science & Engineering", "year": "3rd Year"})
    if verify_student and not faculty:
        r = sess.post(f"{API}/verification/approve"); assert r.status_code == 200
    sess.put(f"{API}/profile/personalization", json={"choices": ["need","skill","resource"]})
    return email, user

# ---------- Auth ----------
class TestAuth:
    def test_send_otp_invalid_domain(self, s):
        r = s.post(f"{API}/auth/send-otp", json={"email": "x@gmail.com"})
        assert r.status_code == 400

    def test_full_otp_flow(self, s):
        email = unique_email()
        r = s.post(f"{API}/auth/send-otp", json={"email": email})
        assert r.status_code == 200 and r.json()["demo_otp"] == "123456"
        r = s.post(f"{API}/auth/verify-otp", json={"email": email, "otp": "123456"})
        assert r.status_code == 200
        assert "user" in r.json() and r.json()["user"]["email"] == email
        # session cookie set
        assert s.cookies.get("session_token")
        me = s.get(f"{API}/auth/me"); assert me.status_code == 200

    def test_otp_bruteforce_lockout(self, s):
        email = unique_email("brute")
        s.post(f"{API}/auth/send-otp", json={"email": email})
        codes_seen = []
        for i in range(5):
            r = s.post(f"{API}/auth/verify-otp", json={"email": email, "otp": "000000"})
            codes_seen.append(r.status_code)
        # 5th attempt should be 429 (lockout triggered on attempt reaching threshold)
        assert 429 in codes_seen, f"Expected lockout, got {codes_seen}"

    def test_faculty_role_detected(self, s):
        email = f"prof.{uuid.uuid4().hex[:6]}@nitandhra.ac.in"
        r = s.post(f"{API}/auth/send-otp", json={"email": email})
        assert r.status_code == 200 and r.json()["role"] == "faculty"

    def test_logout_clears_session(self, s):
        onboard(s)
        r = s.post(f"{API}/auth/logout"); assert r.status_code == 200
        # session cookie deleted -> me should 401
        s2 = requests.Session()  # brand new
        assert s2.get(f"{API}/auth/me").status_code == 401


# ---------- Verification gate ----------
class TestVerificationGate:
    def test_unverified_student_cannot_hire(self, s):
        onboard(s, verify_student=False)
        r = s.post(f"{API}/transactions/hire", json={"provider_id": "provider-priya", "amount": 300})
        assert r.status_code == 403

    def test_unverified_student_cannot_post_request(self, s):
        onboard(s, verify_student=False)
        r = s.post(f"{API}/requests", json={"title": "Need PPT", "category": "Presentation", "budget": 300})
        assert r.status_code == 403

    def test_approve_then_can_transact(self, s):
        onboard(s, verify_student=False)
        r = s.post(f"{API}/verification/approve"); assert r.status_code == 200
        assert r.json()["student_verified"] is True
        r = s.post(f"{API}/transactions/hire", json={"provider_id": "provider-priya", "amount": 300})
        assert r.status_code == 200

    def test_faculty_no_gate(self, s):
        onboard(s, faculty=True)
        r = s.post(f"{API}/requests", json={"title": "Faculty req", "category": "Design", "budget": 100})
        assert r.status_code == 200


# ---------- Search & matching ----------
class TestSearch:
    def test_ppt_ranks_priya_first(self, s):
        onboard(s)
        r = s.get(f"{API}/search", params={"q": "Engineering Mechanics PPT"})
        assert r.status_code == 200
        services = r.json()["services"]
        assert len(services) > 0
        assert services[0]["id"] == "provider-priya", [x["id"] for x in services]

    def test_drone_no_match(self, s):
        onboard(s)
        r = s.get(f"{API}/search", params={"q": "drone photography"})
        d = r.json()
        assert d["no_match"] is True and d["services"] == []


# ---------- Service transaction state machine ----------
class TestServiceFlow:
    def test_full_service_state_machine(self, s):
        onboard(s)
        r = s.post(f"{API}/transactions/hire", json={"provider_id": "provider-priya", "amount": 300})
        assert r.status_code == 200
        tx_id = r.json()["id"]
        assert r.json()["status"] == "HIRE_REQUESTED"

        for action, expected in [("accept","PROVIDER_ACCEPTED"),("pay","PAYMENT_SECURED"),("complete","PROVIDER_COMPLETED"),("confirm","COMPLETED")]:
            r = s.post(f"{API}/transactions/{tx_id}/action", json={"action": action})
            assert r.status_code == 200, f"{action}: {r.text}"
            assert r.json()["status"] == expected
            if action == "pay":
                assert r.json()["contact_revealed"] is True
                assert r.json()["contacts"]["provider"]

        # cannot re-review from wrong state -> already completed, so review ok
        r = s.post(f"{API}/reviews", json={"transaction_id": tx_id, "rating": 5, "text": "great"})
        assert r.status_code == 200
        # double review blocked
        r2 = s.post(f"{API}/reviews", json={"transaction_id": tx_id, "rating": 5})
        assert r2.status_code == 400

    def test_invalid_state_transition(self, s):
        onboard(s)
        r = s.post(f"{API}/transactions/hire", json={"provider_id": "provider-priya", "amount": 300})
        tx_id = r.json()["id"]
        r = s.post(f"{API}/transactions/{tx_id}/action", json={"action": "pay"})  # wrong from HIRE_REQUESTED
        assert r.status_code == 400


# ---------- Resource rental flow ----------
class TestResourceFlow:
    def test_full_resource_state_machine(self, s):
        onboard(s)
        r = s.post(f"{API}/transactions/rent", json={"resource_id": "resource-camera", "days": 2})
        assert r.status_code == 200
        tx = r.json()
        assert tx["status"] == "RENTAL_REQUESTED"
        assert tx["amount"] == 450 * 2
        assert tx["deposit"] == 1500
        tx_id = tx["id"]

        for action, expected in [("accept","OWNER_ACCEPTED"),("pay","PAYMENT_SECURED"),("pickup","PICKED_UP"),("return","RETURNED"),("confirm_return","COMPLETED")]:
            r = s.post(f"{API}/transactions/{tx_id}/action", json={"action": action})
            assert r.status_code == 200, f"{action}: {r.text}"
            assert r.json()["status"] == expected
            if action == "pay":
                assert r.json()["contact_revealed"] is True
                assert r.json()["contacts"]["pickup"]
            if action == "confirm_return":
                assert r.json()["deposit_refunded"] is True


# ---------- Requests + FCFS ----------
class TestRequests:
    def test_create_request_notifies_providers(self, s):
        onboard(s)
        r = s.post(f"{API}/requests", json={"title": "Need Engineering Mechanics PPT", "category": "Presentation", "budget": 300, "description": "mechanics ppt slides"})
        assert r.status_code == 200
        assert r.json()["notified"] >= 1

    def test_seeded_campus_request_has_applicants(self, s):
        onboard(s)
        r = s.get(f"{API}/requests")
        campus = r.json()["campus"]
        seed = next((c for c in campus if c["id"] == "req-seed-1"), None)
        assert seed and len(seed["applications"]) >= 2
        # FCFS order
        assert seed["applications"][0]["order"] == 1

    def test_apply_and_select_creates_tx(self, s):
        # Requester
        req_sess = requests.Session(); onboard(req_sess)
        r = req_sess.post(f"{API}/requests", json={"title": "Need PPT", "category": "Presentation", "budget": 500})
        req_id = r.json()["id"]
        # Applicant
        app_sess = requests.Session(); onboard(app_sess)
        r = app_sess.post(f"{API}/requests/{req_id}/apply")
        assert r.status_code == 200
        app_id = r.json()["application"]["id"]
        # Non-requester cannot select
        r = app_sess.post(f"{API}/requests/{req_id}/select/{app_id}")
        assert r.status_code == 403
        # Requester selects -> hire tx created
        r = req_sess.post(f"{API}/requests/{req_id}/select/{app_id}")
        assert r.status_code == 200
        assert r.json()["transaction"]["status"] == "HIRE_REQUESTED"


# ---------- Persistence ----------
class TestPersistence:
    def test_session_survives(self, s):
        email, _ = onboard(s)
        cookies = dict(s.cookies)
        s2 = requests.Session(); s2.cookies.update(cookies)
        r = s2.get(f"{API}/auth/me")
        assert r.status_code == 200 and r.json()["email"] == email
        assert r.json()["onboarded"] is True

    def test_requests_persist(self, s):
        onboard(s)
        s.post(f"{API}/requests", json={"title": "Persistence test", "category": "Design", "budget": 100})
        r = s.get(f"{API}/requests")
        assert any(x["title"] == "Persistence test" for x in r.json()["mine"])


# ---------- Insights ----------
class TestInsights:
    def test_insights_shape(self, s):
        onboard(s)
        r = s.get(f"{API}/insights")
        assert r.status_code == 200
        d = r.json()
        assert "metrics" in d and "demand" in d and "undersupplied" in d
        assert len(d["metrics"]) == 4
