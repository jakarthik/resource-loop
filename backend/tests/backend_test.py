"""Regression coverage for Loop's public API and mocked marketplace flows."""
import os
import uuid

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def api():
    if not BASE_URL:
        pytest.fail("REACT_APP_BACKEND_URL is required")
    return requests.Session()


@pytest.fixture(scope="module")
def authenticated_api(api):
    """Session established through the mocked institutional OTP flow."""
    session = requests.Session()
    sent = session.post(f"{BASE_URL}/api/auth/send-otp", json={
        "email": "harvey@student.nitandhra.ac.in"
    })
    assert sent.status_code == 200
    verified = session.post(f"{BASE_URL}/api/auth/verify-otp", json={
        "email": "harvey@student.nitandhra.ac.in", "otp": "123456"
    })
    assert verified.status_code == 200
    session.headers.update({"Authorization": f"Bearer {verified.json()['token']}"})
    return session


def test_api_root(api):
    response = api.get(f"{BASE_URL}/api/")
    assert response.status_code == 200
    assert response.json()["message"] == "Loop API ready"


def test_send_otp_student_and_faculty(api):
    for email, role in [("harvey@student.nitandhra.ac.in", "student"),
                        ("faculty@nitandhra.ac.in", "faculty")]:
        response = api.post(f"{BASE_URL}/api/auth/send-otp", json={"email": email})
        assert response.status_code == 200
        assert response.json()["role"] == role
        assert response.json()["demo_otp"] == "123456"


def test_send_otp_rejects_non_institutional_email(api):
    response = api.post(f"{BASE_URL}/api/auth/send-otp", json={"email": "person@gmail.com"})
    assert response.status_code == 400
    assert "institutional" in response.json()["detail"].lower()


def test_verify_otp_demo_user(api):
    response = api.post(f"{BASE_URL}/api/auth/verify-otp", json={
        "email": "harvey@student.nitandhra.ac.in", "otp": "123456"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["name"] == "Harvey Specter"
    assert data["user"]["verification_status"] == "Pending"
    assert isinstance(data["token"], str) and data["token"]


def test_verify_otp_rejects_wrong_code(api):
    response = api.post(f"{BASE_URL}/api/auth/verify-otp", json={
        "email": "harvey@student.nitandhra.ac.in", "otp": "000000"
    })
    assert response.status_code == 400


def test_home_contains_seeded_marketplace_data(api):
    response = api.get(f"{BASE_URL}/api/home")
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "harvey@student.nitandhra.ac.in"
    assert any(p["name"] == "Priya Sharma" for p in data["providers"])
    assert any(r["name"] == "Casio fx-991CW" for r in data["resources"])
    assert len(data["requests"]) >= 2


def test_search_services_and_resources(api):
    mechanics = api.get(f"{BASE_URL}/api/search", params={"q": "Engineering Mechanics PPT"})
    assert mechanics.status_code == 200
    assert mechanics.json()["services"][0]["name"] == "Priya Sharma"
    resource = api.get(f"{BASE_URL}/api/search", params={"q": "fx-991CW"})
    assert resource.status_code == 200
    assert resource.json()["resources"][0]["name"] == "Casio fx-991CW"


def test_search_drone_is_empty(api):
    response = api.get(f"{BASE_URL}/api/search", params={"q": "drone filming"})
    assert response.status_code == 200
    assert response.json()["services"] == [] and response.json()["resources"] == []


def test_request_create_get_and_apply(api):
    title = f"TEST_{uuid.uuid4().hex[:8]} campus help"
    payload = {"title": title, "category": "Academic", "deadline": "Tomorrow",
               "budget": 300, "description": "Regression request", "recurring": False}
    created = api.post(f"{BASE_URL}/api/requests", json=payload)
    assert created.status_code == 200
    item = created.json()
    assert item["title"] == title and item["applied"] == 0
    listed = api.get(f"{BASE_URL}/api/requests")
    assert any(row["id"] == item["id"] for row in listed.json())
    applied = api.post(f"{BASE_URL}/api/requests/{item['id']}/apply")
    assert applied.status_code == 200 and applied.json()["application_number"] == 1


def test_payment_and_transaction_action(authenticated_api):
    payment = authenticated_api.post(f"{BASE_URL}/api/payments", json={
        "item_id": "provider-priya", "kind": "service", "amount": 300
    })
    assert payment.status_code == 200
    tx = payment.json()
    assert tx["status"] == "PAYMENT_SECURED" and tx["contact_revealed"] is True
    assert tx["contacts"]["provider"]
    action = authenticated_api.post(f"{BASE_URL}/api/transactions/{tx['id']}/action", json={"action": "complete"})
    assert action.status_code == 200 and action.json()["status"] == "PROVIDER_COMPLETED"


def test_insights_and_verification_upload(authenticated_api):
    insights = authenticated_api.get(f"{BASE_URL}/api/insights")
    assert insights.status_code == 200
    assert any(metric["label"] == "Active students" for metric in insights.json()["metrics"])
    upload = authenticated_api.post(f"{BASE_URL}/api/verification/upload", files={"file": ("TEST_id.txt", b"demo")})
    assert upload.status_code == 200 and upload.json()["status"] == "Pending"


def test_payment_requires_authenticated_session(api):
    response = api.post(f"{BASE_URL}/api/payments", json={
        "item_id": "provider-priya", "kind": "service", "amount": 300
    })
    assert response.status_code in (401, 403)


def test_auth_me_requires_authenticated_session(api):
    response = api.get(f"{BASE_URL}/api/auth/me")
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("method,path,kwargs", [
    ("post", "/api/payments", {"json": {"item_id": "x", "kind": "service", "amount": 1}}),
    ("post", "/api/transactions/no-such/action", {"json": {"action": "confirm"}}),
    ("post", "/api/verification/upload", {"files": {"file": ("TEST_id.txt", b"demo")}}),
])
def test_sensitive_endpoints_require_authenticated_session(api, method, path, kwargs):
    response = getattr(api, method)(f"{BASE_URL}{path}", **kwargs)
    assert response.status_code in (401, 403)


def test_verify_otp_rejects_mismatched_email(api):
    response = api.post(f"{BASE_URL}/api/auth/verify-otp", json={
        "email": "person@gmail.com", "otp": "123456"
    })
    assert response.status_code == 400