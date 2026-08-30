"""Regression tests for the friction-reduction feature batch (Jan 2026):
- NL intent parsing (need vs provide, category, days, location, missing)
- /provides listings (service + resource) with reverse-discovery notifications
- /opportunities (reverse discovery)
- /suggestions (proactive resources)
- Request lifecycle: renew/cancel + auth
- In-context messaging threads (canned auto-reply from seeded personas)
- Request create returns matches (proactive inline matches)
- Transaction inline rating (review after complete)
"""
import os, uuid, requests, pytest
from pathlib import Path

BASE = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE = line.split("=", 1)[1].strip()
API = f"{BASE.rstrip('/')}/api"


def unique_email(prefix="qa"):
    return f"{prefix}.{uuid.uuid4().hex[:10]}@student.nitandhra.ac.in"


def onboard(sess, verify=True, faculty=False):
    email = f"prof.{uuid.uuid4().hex[:8]}@nitandhra.ac.in" if faculty else unique_email()
    assert sess.post(f"{API}/auth/send-otp", json={"email": email}).status_code == 200
    r = sess.post(f"{API}/auth/verify-otp", json={"email": email, "otp": "123456"})
    assert r.status_code == 200
    sess.put(f"{API}/profile", json={"name": "QA User", "branch": "CSE", "year": "3rd Year"})
    if verify and not faculty:
        assert sess.post(f"{API}/verification/approve").status_code == 200
    sess.put(f"{API}/profile/personalization", json={"choices": ["need", "skill", "resource"]})
    return email, r.json()["user"]


@pytest.fixture
def s():
    return requests.Session()


# ---------- NL Intent parsing ----------
class TestIntentParse:
    def test_need_service_with_days_and_location(self, s):
        onboard(s)
        r = s.post(f"{API}/intent/parse", json={"text": "Need a drafter for 3 days near Civil Block"})
        assert r.status_code == 200
        d = r.json()
        assert d["intent"] == "need"
        # drafter is a resource hint
        assert d["kind"] == "resource"
        assert d["category"] == "Physical Resource"
        assert d["days"] == 3
        assert "Civil Block" in d["location"]
        assert "Need" in d["confirm"] and "Civil Block" in d["confirm"]

    def test_provide_intent_ppt(self, s):
        onboard(s)
        r = s.post(f"{API}/intent/parse", json={"text": "I can do PPT design and presentations"})
        assert r.status_code == 200
        d = r.json()
        assert d["intent"] == "provide"
        assert d["category"] == "Presentation"
        assert d["kind"] == "service"

    def test_missing_location_flag(self, s):
        onboard(s)
        r = s.post(f"{API}/intent/parse", json={"text": "Need a laptop repair"})
        d = r.json()
        assert d["intent"] == "need"
        # no location parsed and user has no learned locations
        assert "location" in d["missing"]


# ---------- /provides + reverse-discovery notified count ----------
class TestProvides:
    def test_create_service_provide_notifies_matching_request(self, s):
        # requester posts a need
        req_sess = requests.Session(); onboard(req_sess)
        r = req_sess.post(f"{API}/requests", json={"title": "Need Engineering Mechanics PPT deck", "category": "Presentation", "budget": 300, "description": "mechanics ppt"})
        assert r.status_code == 200

        # provider lists a matching service
        prov_sess = requests.Session(); onboard(prov_sess)
        r = prov_sess.post(f"{API}/provides", json={"kind": "service", "category": "Presentation", "name": "PPT design and presentations", "price": 250, "text": "I can do PPT design"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["listing"]["id"].startswith("provider-")
        assert d["notified"] >= 1
        assert any("PPT" in n["title"] or "ppt" in n["title"].lower() for n in d["notified_requests"])

    def test_create_resource_provide(self, s):
        onboard(s)
        r = s.post(f"{API}/provides", json={"kind": "resource", "category": "Physical Resource", "name": "Casio calculator", "price": 20, "deposit": 100, "location": "Library"})
        assert r.status_code == 200
        assert r.json()["listing"]["id"].startswith("resource-")

    def test_provide_blocked_without_verification(self, s):
        onboard(s, verify=False)
        r = s.post(f"{API}/provides", json={"kind": "service", "category": "Design", "name": "Poster design"})
        assert r.status_code == 403


# ---------- /opportunities reverse discovery ----------
class TestOpportunities:
    def test_opportunities_returns_matching_open_needs(self, s):
        # requester posts a need
        req_sess = requests.Session(); onboard(req_sess)
        req_sess.post(f"{API}/requests", json={"title": "Need LinkedIn headshot photography", "category": "Photography / Video", "budget": 200, "description": "linkedin portrait"})

        # provider lists photography service
        prov = requests.Session(); onboard(prov)
        prov.post(f"{API}/provides", json={"kind": "service", "category": "Photography / Video", "name": "LinkedIn Headshots photography"})
        r = prov.get(f"{API}/opportunities")
        assert r.status_code == 200
        d = r.json()
        assert d["has_signal"] is True
        # at least one opportunity with a match% and applied bool
        assert isinstance(d["opportunities"], list)
        if d["opportunities"]:
            o = d["opportunities"][0]
            assert "match" in o and "applied" in o and "id" in o


# ---------- /suggestions ----------
class TestSuggestions:
    def test_suggestions_returns_resources(self, s):
        onboard(s)
        r = s.get(f"{API}/suggestions")
        assert r.status_code == 200
        d = r.json()
        assert "resources" in d and isinstance(d["resources"], list)


# ---------- Request lifecycle: renew / cancel ----------
class TestRequestLifecycle:
    def test_cancel_request_sets_status_and_lifecycle(self, s):
        onboard(s)
        r = s.post(f"{API}/requests", json={"title": "cancel-me", "category": "Design", "budget": 100})
        rid = r.json()["id"]
        r = s.post(f"{API}/requests/{rid}/cancel")
        assert r.status_code == 200
        r = s.get(f"{API}/requests")
        mine = r.json()["mine"]
        found = next(x for x in mine if x["id"] == rid)
        assert found["status"] == "cancelled"
        assert found["lifecycle"] == "Cancelled"

    def test_renew_request_reopens(self, s):
        onboard(s)
        r = s.post(f"{API}/requests", json={"title": "renew-me", "category": "Design", "budget": 100})
        rid = r.json()["id"]
        s.post(f"{API}/requests/{rid}/cancel")
        r = s.post(f"{API}/requests/{rid}/renew")
        assert r.status_code == 200 and r.json()["status"] == "open"
        r = s.get(f"{API}/requests")
        found = next(x for x in r.json()["mine"] if x["id"] == rid)
        assert found["status"] == "open"
        assert found["lifecycle"] == "Open"

    def test_cancel_other_users_request_forbidden(self, s):
        owner = requests.Session(); onboard(owner)
        rid = owner.post(f"{API}/requests", json={"title": "not-yours", "category": "Design", "budget": 100}).json()["id"]
        other = requests.Session(); onboard(other)
        r = other.post(f"{API}/requests/{rid}/cancel")
        assert r.status_code == 403


# ---------- Proactive inline matches on create ----------
class TestProactiveMatches:
    def test_create_request_returns_matches(self, s):
        onboard(s)
        r = s.post(f"{API}/requests", json={"title": "Engineering Mechanics PPT", "category": "Presentation", "budget": 300, "description": "mechanics deck"})
        assert r.status_code == 200
        d = r.json()
        assert "matches" in d
        # priya should be top service match
        svc_ids = [x["id"] for x in d["matches"]["services"]]
        assert "provider-priya" in svc_ids


# ---------- Messaging threads ----------
class TestMessaging:
    def test_thread_on_request_gets_canned_auto_reply(self, s):
        onboard(s)
        # message a seeded campus request (seeded needer -> not a real user, so auto-reply triggers)
        ref = "req-seed-1"
        r = s.get(f"{API}/threads/{ref}")
        assert r.status_code == 200
        d = r.json()
        assert d["ref"] == ref and "with" in d and "title" in d
        r = s.post(f"{API}/threads/{ref}", json={"text": "Hi, still open?"})
        assert r.status_code == 200
        msgs = r.json()["messages"]
        # my message + canned auto-reply from seeded persona
        assert any(m["text"] == "Hi, still open?" for m in msgs)
        assert len(msgs) >= 2  # at least the auto-reply too
        # persisted
        r = s.get(f"{API}/threads/{ref}")
        assert len(r.json()["messages"]) >= 2

    def test_thread_on_transaction(self, s):
        onboard(s)
        tx = s.post(f"{API}/transactions/hire", json={"provider_id": "provider-priya", "amount": 300}).json()
        ref = tx["id"]
        r = s.get(f"{API}/threads/{ref}")
        assert r.status_code == 200
        r = s.post(f"{API}/threads/{ref}", json={"text": "hey"})
        assert r.status_code == 200
        assert any(m["text"] == "hey" for m in r.json()["messages"])

    def test_thread_unknown_ref_404(self, s):
        onboard(s)
        r = s.get(f"{API}/threads/does-not-exist")
        assert r.status_code == 404


# ---------- Inline rating (review on transaction) ----------
class TestInlineRating:
    def test_rate_after_complete(self, s):
        onboard(s)
        tx_id = s.post(f"{API}/transactions/hire", json={"provider_id": "provider-priya", "amount": 300}).json()["id"]
        for a in ["accept", "pay", "complete", "confirm"]:
            r = s.post(f"{API}/transactions/{tx_id}/action", json={"action": a})
            assert r.status_code == 200
        r = s.post(f"{API}/reviews", json={"transaction_id": tx_id, "rating": 4, "text": ""})
        assert r.status_code == 200
        # verify transaction now marked reviewed
        r = s.get(f"{API}/transactions")
        found = next(t for t in r.json() if t["id"] == tx_id)
        assert found["reviewed"] is True

    def test_cannot_rate_before_complete(self, s):
        onboard(s)
        tx_id = s.post(f"{API}/transactions/hire", json={"provider_id": "provider-priya", "amount": 300}).json()["id"]
        r = s.post(f"{API}/reviews", json={"transaction_id": tx_id, "rating": 5})
        assert r.status_code == 400
