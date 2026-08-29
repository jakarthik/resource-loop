from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Header, Depends, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response as FileResponse
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import os, uuid, re, logging, requests as http_requests

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="Loop API")
api = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("loop")

# ---------------- Object storage ----------------
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "loop-marketplace"
_storage_key = None
MIME_TYPES = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp","pdf":"application/pdf"}

def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force: return _storage_key
    resp = http_requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = http_requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = http_requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()

def get_object(path: str):
    key = init_storage()
    resp = http_requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

# ---------------- Models ----------------
class OtpRequest(BaseModel): email: str
class OtpVerify(BaseModel): email: str; otp: str
class GoogleSessionRequest(BaseModel): session_id: str
class ProfileUpdate(BaseModel): name: str; branch: Optional[str] = ""; year: Optional[str] = ""
class Personalization(BaseModel): choices: List[str]
class RequestCreate(BaseModel):
    title: str; category: str = "General"; deadline: str = ""; budget: int = 0
    description: str = ""; recurring: bool = False; frequency: Optional[str] = ""
class HireCreate(BaseModel): provider_id: str; amount: int; request_id: Optional[str] = None
class RentCreate(BaseModel): resource_id: str; days: int = 1
class Action(BaseModel): action: str
class ReviewCreate(BaseModel): transaction_id: str; rating: int; text: str = ""

NOW = lambda: datetime.now(timezone.utc).isoformat()

# ---------------- Auth helpers ----------------
OTP_CHALLENGES = {}
OTP_MAX_ATTEMPTS = 5
OTP_LOCK_MINUTES = 5

def valid_email(email): return bool(re.match(r"^[^@\s]+@(student\.)?nitandhra\.ac\.in$", (email or "").lower()))
def role_for(email): return "student" if "@student." in email.lower() else "faculty"
def clean(doc):
    if doc: doc.pop("_id", None)
    return doc

async def new_session(user_id: str) -> str:
    token = f"sess_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    await db.user_sessions.insert_one({"session_token": token, "user_id": user_id, "created_at": now.isoformat(), "expires_at": (now + timedelta(days=7)).isoformat()})
    return token

def set_session_cookie(response: Response, token: str):
    response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")

async def get_or_create_user(email: str, name: str = "", picture: str = "") -> dict:
    email = email.lower()
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing: return existing
    user = {
        "user_id": f"user_{uuid.uuid4().hex[:12]}", "email": email,
        "name": name or email.split("@")[0].replace(".", " ").title(),
        "role": role_for(email), "branch": "", "year": "", "college": "NIT Andhra Pradesh",
        "picture": picture, "email_verified": True,
        "student_verified": False, "verification_status": "Pending",
        "id_upload": None, "personalization": [], "onboarded": False,
        "reputation": {"rating": 0, "gigs_completed": 0, "reviews_count": 0, "earned": 0},
        "seed": False, "created_at": NOW(),
    }
    await db.users.insert_one(dict(user))
    return user

async def require_session(request: Request, authorization: Optional[str] = Header(default=None)):
    token = request.cookies.get("session_token") or (authorization.replace("Bearer ", "", 1) if authorization and authorization.startswith("Bearer ") else None)
    if not token: raise HTTPException(401, "Authentication required.")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session: raise HTTPException(401, "Authentication required.")
    expires_at = session.get("expires_at")
    if isinstance(expires_at, str): expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None: expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc): raise HTTPException(401, "Session expired.")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user: raise HTTPException(401, "User not found.")
    return user

def ensure_can_transact(user: dict):
    if user["role"] == "student" and not user.get("student_verified"):
        raise HTTPException(403, "Student verification is required before transacting. Upload your college ID to get verified.")

# ---------------- Matching ----------------
def match_score(query: str, provider: dict) -> int:
    tokens = [t for t in re.split(r"\s+", query.lower().strip()) if len(t) > 2]
    if not tokens: return provider.get("base_match", 70)
    hay = " ".join([provider.get("skill",""), provider.get("name",""), provider.get("bio",""), provider.get("branch",""), " ".join(provider.get("tags",[]))]).lower()
    hits = sum(1 for t in tokens if t in hay)
    ratio = hits / len(tokens)
    score = int(round(ratio * 78)) + int(provider.get("rating", 4.5) * 4)
    return max(0, min(99, score if hits else 30))

# ---------------- Seed data ----------------
SEED_PROVIDERS = [
    {"id":"provider-priya","name":"Priya Sharma","branch":"Civil Engineering","year":"3rd Year","skill":"Engineering Mechanics · PPT Design","tags":["ppt","mechanics","presentation","design","engineering","deck"],"base_match":94,"rating":4.8,"gigs":27,"similar":8,"price":300,"availability":"Available today","phone":"+91 98480 11223","verified":["Email Verified","Student Verified","Portfolio Verified"],"why":"Engineering Mechanics + PPT Design + 8 similar gigs + available before deadline.","bio":"Turns difficult mechanics concepts into clear, exam-ready decks."},
    {"id":"provider-rahul","name":"Rahul Mehta","branch":"Computer Science & Engineering","year":"4th Year","skill":"PowerPoint · Visual Design · Laptop Help","tags":["ppt","design","laptop","repair","tech","canva","presentation"],"base_match":81,"rating":4.9,"gigs":41,"similar":3,"price":250,"availability":"Available today","phone":"+91 98480 22334","verified":["Email Verified","Student Verified","Portfolio Verified"],"why":"Strong presentation craft + fast response, with less Mechanics context.","bio":"Presentation designer and laptop troubleshooter for clubs and academics."},
    {"id":"provider-meera","name":"Meera Nair","branch":"Electronics & Communication Engineering","year":"3rd Year","skill":"Presentation + Canva · Video Edit","tags":["ppt","canva","presentation","video","edit","design"],"base_match":76,"rating":4.9,"gigs":22,"similar":4,"price":200,"availability":"Available tomorrow","phone":"+91 98480 33445","verified":["Email Verified","Student Verified"],"why":"Great visual polish and fast turnaround on decks and reels.","bio":"Canva and short-form video specialist."},
    {"id":"provider-anirudh","name":"Anirudh Rao","branch":"Mechanical Engineering","year":"2nd Year","skill":"LinkedIn Headshots · Photography","tags":["photo","linkedin","headshot","photography","camera","portrait","event"],"base_match":88,"rating":4.9,"gigs":32,"similar":12,"price":150,"availability":"Available today","phone":"+91 98480 44556","verified":["Email Verified","Student Verified","Portfolio Verified"],"why":"12 LinkedIn portfolio photos + campus events + available today.","bio":"Campus photographer for LinkedIn portraits and events."},
]
SEED_RESOURCES = [
    {"id":"resource-casio","name":"Casio fx-991CW","tags":["calculator","casio","fx","exam"],"price":20,"deposit":0,"availability":"Available now","location":"Library pickup · 0.3 km","condition":"Good condition","owner":"Akash Kumar","owner_phone":"+91 98480 55667","rating":4.9,"rentals":12,"emoji":"⌗"},
    {"id":"resource-drafter","name":"Drafting Set","tags":["drafter","drafting","civil","drawing"],"price":30,"deposit":300,"availability":"Available Sep 1–4","location":"Civil block pickup","condition":"Clean · lightly used","owner":"Karthik R","owner_phone":"+91 98480 66778","rating":4.8,"rentals":9,"emoji":"⌁"},
    {"id":"resource-camera","name":"Sony Alpha Camera","tags":["camera","sony","photography","dslr","video"],"price":450,"deposit":1500,"availability":"Available this weekend","location":"Hostel C pickup","condition":"Excellent condition","owner":"Rohan Das","owner_phone":"+91 98480 77889","rating":4.9,"rentals":6,"emoji":"◉"},
]
SEED_REQUESTS = [
    {"id":"req-seed-1","needer_id":"seed-needer","needer_name":"Sana Iyer","title":"Engineering Mechanics PPT","category":"Presentation","budget":300,"deadline":"Due tomorrow","description":"20-slide deck on stress-strain for a viva.","recurring":False,"frequency":"","status":"open","notified":3,"created_at":NOW(),"seed":True},
    {"id":"req-seed-2","needer_id":"seed-needer","needer_name":"Dev Patel","title":"LinkedIn profile photo","category":"Photography / Video","budget":200,"deadline":"Due Friday","description":"Clean headshot near the campus lawn.","recurring":False,"frequency":"","status":"open","notified":5,"created_at":NOW(),"seed":True},
]

async def seed():
    if await db.providers.count_documents({}) == 0:
        await db.providers.insert_many([{**p, "seed": True} for p in SEED_PROVIDERS])
    if await db.resources.count_documents({}) == 0:
        await db.resources.insert_many([{**r, "seed": True} for r in SEED_RESOURCES])
    if await db.requests.count_documents({"seed": True}) == 0:
        await db.requests.insert_many([dict(r) for r in SEED_REQUESTS])
        # seed a couple of FCFS applications on the first seeded request
        await db.applications.insert_many([
            {"id":"app-seed-1","request_id":"req-seed-1","provider_id":"provider-priya","provider_name":"Priya Sharma","match":94,"order":1,"status":"applied","created_at":NOW(),"seed":True},
            {"id":"app-seed-2","request_id":"req-seed-1","provider_id":"provider-meera","provider_name":"Meera Nair","match":76,"order":2,"status":"applied","created_at":NOW(),"seed":True},
        ])

# ---------------- Startup ----------------
@app.on_event("startup")
async def startup():
    try: init_storage(); logger.info("Storage initialized")
    except Exception as e: logger.error(f"Storage init failed: {e}")
    await seed()

@api.get("/")
async def root(): return {"message": "Loop API ready"}

# ---------------- Auth ----------------
@api.post("/auth/send-otp")
async def send_otp(payload: OtpRequest):
    email = payload.email.lower()
    if not valid_email(email): raise HTTPException(400, "Use a NIT Andhra Pradesh institutional email.")
    existing = OTP_CHALLENGES.get(email, {})
    locked_until = existing.get("locked_until")
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.", headers={"Retry-After": "300"})
    OTP_CHALLENGES[email] = {"otp": "123456", "created_at": NOW(), "failed_attempts": 0, "locked_until": None}
    return {"sent": True, "demo_otp": "123456", "email": email, "role": role_for(email)}

@api.post("/auth/verify-otp")
async def verify_otp(payload: OtpVerify, response: Response):
    email = payload.email.lower()
    challenge = OTP_CHALLENGES.get(email)
    if not valid_email(email) or not challenge: raise HTTPException(400, "That code is not correct or was not requested for this email.")
    locked_until = challenge.get("locked_until")
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.", headers={"Retry-After": "300"})
    if payload.otp != challenge["otp"]:
        challenge["failed_attempts"] += 1
        if challenge["failed_attempts"] >= OTP_MAX_ATTEMPTS:
            challenge["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=OTP_LOCK_MINUTES)).isoformat()
            raise HTTPException(429, "Too many attempts. Try again in a few minutes.", headers={"Retry-After": "300"})
        raise HTTPException(400, "That code is not correct or was not requested for this email.")
    OTP_CHALLENGES.pop(email, None)
    user = await get_or_create_user(email)
    token = await new_session(user["user_id"])
    set_session_cookie(response, token)
    return {"token": token, "user": clean(user)}

@api.post("/auth/google/session")
async def exchange_google_session(payload: GoogleSessionRequest, response: Response):
    try:
        external = http_requests.get("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data", headers={"X-Session-ID": payload.session_id}, timeout=10)
        if external.status_code != 200: raise HTTPException(401, "Google session could not be verified.")
        google = external.json()
    except http_requests.RequestException as exc:
        raise HTTPException(502, "Google sign-in is temporarily unavailable.") from exc
    email = str(google.get("email", "")).lower()
    if not valid_email(email): raise HTTPException(403, "Use your NIT Andhra Pradesh Google account.")
    user = await get_or_create_user(email, google.get("name", ""), google.get("picture", ""))
    session_token = google.get("session_token") or f"sess_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    await db.user_sessions.update_one({"session_token": session_token}, {"$set": {"user_id": user["user_id"], "session_token": session_token, "created_at": now.isoformat(), "expires_at": (now + timedelta(days=7)).isoformat()}}, upsert=True)
    set_session_cookie(response, session_token)
    return {"token": session_token, "user": clean(user)}

@api.get("/auth/me")
async def me(user=Depends(require_session)): return clean(user)

@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token: await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/", secure=True, samesite="none")
    return {"ok": True}

@api.put("/profile")
async def update_profile(payload: ProfileUpdate, user=Depends(require_session)):
    upd = {"name": payload.name.strip() or user["name"], "branch": payload.branch, "year": payload.year}
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": upd})
    return clean(await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0}))

@api.put("/profile/personalization")
async def set_personalization(payload: Personalization, user=Depends(require_session)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"personalization": payload.choices, "onboarded": True}})
    return clean(await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0}))

# ---------------- Verification ----------------
@api.post("/verification/upload")
async def upload_id(file: UploadFile = File(...), user=Depends(require_session)):
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin").lower()
    if ext not in MIME_TYPES: raise HTTPException(400, "Upload a JPG, PNG or PDF file.")
    path = f"{APP_NAME}/ids/{user['user_id']}/{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    result = put_object(path, data, MIME_TYPES.get(ext, file.content_type or "application/octet-stream"))
    rec = {"id": str(uuid.uuid4()), "user_id": user["user_id"], "storage_path": result["path"], "original_filename": file.filename, "content_type": MIME_TYPES.get(ext), "size": result.get("size", len(data)), "is_deleted": False, "created_at": NOW()}
    await db.files.insert_one(dict(rec))
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"verification_status": "Under review", "id_upload": {"file_id": rec["id"], "filename": file.filename, "storage_path": result["path"]}}})
    return {"status": "Under review", "filename": file.filename, "file_id": rec["id"]}

@api.get("/verification/file/{file_id}")
async def get_id_file(file_id: str, user=Depends(require_session)):
    rec = await db.files.find_one({"id": file_id, "user_id": user["user_id"], "is_deleted": False}, {"_id": 0})
    if not rec: raise HTTPException(404, "File not found")
    data, ctype = get_object(rec["storage_path"])
    return FileResponse(content=data, media_type=rec.get("content_type") or ctype)

@api.post("/verification/approve")
async def approve_verification(user=Depends(require_session)):
    """Mock campus-admin approval (demo). Flips the student to Verified."""
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"student_verified": True, "verification_status": "Verified"}})
    return clean(await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0}))

# ---------------- Marketplace read ----------------
@api.get("/home")
async def home(user=Depends(require_session)):
    providers = [clean(p) for p in await db.providers.find().to_list(100)]
    resources = [clean(r) for r in await db.resources.find().to_list(100)]
    my_requests = [clean(r) for r in await db.requests.find({"needer_id": user["user_id"]}).sort("created_at", -1).to_list(100)]
    my_tx = [clean(t) for t in await db.transactions.find({"$or": [{"needer_id": user["user_id"]}, {"counterparty_id": user["user_id"]}]}).sort("created_at", -1).to_list(100)]
    return {"user": clean(user), "providers": providers, "resources": resources, "requests": my_requests, "transactions": my_tx}

@api.get("/search")
async def search(q: str = "", user=Depends(require_session)):
    term = q.lower().strip()
    providers = [clean(p) for p in await db.providers.find().to_list(100)]
    resources = [clean(r) for r in await db.resources.find().to_list(100)]
    if "drone" in term:
        return {"query": q, "services": [], "resources": [], "intent": "NEED", "no_match": True, "explanation": "Nobody currently offers this. Post a request and matching providers will be notified."}
    if term:
        scored = [{**p, "match": match_score(term, p)} for p in providers]
        services = sorted([p for p in scored if p["match"] >= 40], key=lambda x: x["match"], reverse=True)
        rmatch = [r for r in resources if any(t in " ".join([r["name"]] + r.get("tags", [])).lower() for t in term.split() if len(t) > 2)]
    else:
        services = sorted([{**p, "match": p.get("base_match", 70)} for p in providers], key=lambda x: x["match"], reverse=True)
        rmatch = resources
    return {"query": q, "services": services, "resources": rmatch, "intent": "NEED", "no_match": False, "explanation": "Ranked across skills and resources by relevance, reputation and availability."}

@api.get("/providers/{provider_id}")
async def provider(provider_id: str, user=Depends(require_session)):
    match = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    if not match: raise HTTPException(404, "Provider not found")
    return match

# ---------------- Requests + FCFS ----------------
@api.post("/requests")
async def create_request(payload: RequestCreate, user=Depends(require_session)):
    ensure_can_transact(user)
    providers = [p for p in await db.providers.find().to_list(100)]
    matched = [p for p in providers if match_score(f"{payload.title} {payload.category} {payload.description}", p) >= 50]
    item = {"id": "req-" + uuid.uuid4().hex[:8], "needer_id": user["user_id"], "needer_name": user["name"], **payload.model_dump(), "status": "open", "notified": len(matched), "notified_ids": [p["id"] for p in matched], "created_at": NOW(), "seed": False}
    await db.requests.insert_one(dict(item))
    return clean(item)

@api.get("/requests")
async def list_requests(user=Depends(require_session)):
    mine = [clean(r) for r in await db.requests.find({"needer_id": user["user_id"]}).sort("created_at", -1).to_list(100)]
    seeded = [clean(r) for r in await db.requests.find({"seed": True}).sort("created_at", -1).to_list(100)]
    # attach applications
    for r in mine + seeded:
        r["applications"] = [clean(a) for a in await db.applications.find({"request_id": r["id"]}).sort("order", 1).to_list(100)]
    return {"mine": mine, "campus": seeded}

@api.post("/requests/{request_id}/apply")
async def apply(request_id: str, user=Depends(require_session)):
    ensure_can_transact(user)
    req = await db.requests.find_one({"id": request_id}, {"_id": 0})
    if not req: raise HTTPException(404, "Request not found")
    if req["status"] != "open": raise HTTPException(400, "This request is no longer accepting applications.")
    if await db.applications.find_one({"request_id": request_id, "provider_id": user["user_id"]}):
        raise HTTPException(400, "You have already applied to this request.")
    order = await db.applications.count_documents({"request_id": request_id}) + 1
    appn = {"id": "app-" + uuid.uuid4().hex[:8], "request_id": request_id, "provider_id": user["user_id"], "provider_name": user["name"], "match": match_score(f"{req['title']} {req.get('category','')}", {"skill": " ".join(user.get("personalization", [])), "name": user["name"], "bio": "", "branch": user.get("branch",""), "rating": user.get("reputation",{}).get("rating",4.5)}), "order": order, "status": "applied", "created_at": NOW(), "seed": False}
    await db.applications.insert_one(dict(appn))
    return {"ok": True, "application": clean(appn), "position": order}

@api.post("/requests/{request_id}/select/{application_id}")
async def select_applicant(request_id: str, application_id: str, user=Depends(require_session)):
    req = await db.requests.find_one({"id": request_id}, {"_id": 0})
    if not req: raise HTTPException(404, "Request not found")
    if req["needer_id"] != user["user_id"]: raise HTTPException(403, "Only the requester can select a provider.")
    appn = await db.applications.find_one({"id": application_id, "request_id": request_id}, {"_id": 0})
    if not appn: raise HTTPException(404, "Application not found")
    await db.applications.update_one({"id": application_id}, {"$set": {"status": "selected"}})
    await db.applications.update_many({"request_id": request_id, "id": {"$ne": application_id}}, {"$set": {"status": "not_selected"}})
    await db.requests.update_one({"id": request_id}, {"$set": {"status": "matched", "selected_application": application_id}})
    # create a hire transaction in HIRE_REQUESTED state
    tx = await _make_service_tx(user, appn["provider_id"], appn["provider_name"], req.get("budget", 0), request_id)
    return {"ok": True, "transaction": tx}

# ---------------- Transactions ----------------
async def _make_service_tx(user, provider_id, provider_name, amount, request_id=None):
    prov = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    tx = {"id": "tx-" + uuid.uuid4().hex[:8], "kind": "service", "item_id": provider_id, "title": provider_name,
          "needer_id": user["user_id"], "needer_name": user["name"], "counterparty_id": provider_id, "counterparty_name": provider_name,
          "amount": amount, "deposit": 0, "status": "HIRE_REQUESTED", "contact_revealed": False, "contacts": None,
          "request_id": request_id, "reviewed": False,
          "provider_phone": (prov or {}).get("phone", "+91 98480 00000"), "needer_phone": "+91 91234 56789",
          "created_at": NOW(), "seed": False}
    await db.transactions.insert_one(dict(tx))
    return clean(tx)

@api.post("/transactions/hire")
async def hire(payload: HireCreate, user=Depends(require_session)):
    ensure_can_transact(user)
    prov = await db.providers.find_one({"id": payload.provider_id}, {"_id": 0})
    if not prov: raise HTTPException(404, "Provider not found")
    return await _make_service_tx(user, prov["id"], prov["name"], payload.amount, payload.request_id)

@api.post("/transactions/rent")
async def rent(payload: RentCreate, user=Depends(require_session)):
    ensure_can_transact(user)
    res = await db.resources.find_one({"id": payload.resource_id}, {"_id": 0})
    if not res: raise HTTPException(404, "Resource not found")
    amount = res["price"] * max(1, payload.days)
    tx = {"id": "tx-" + uuid.uuid4().hex[:8], "kind": "resource", "item_id": res["id"], "title": res["name"],
          "needer_id": user["user_id"], "needer_name": user["name"], "counterparty_id": res["id"], "counterparty_name": res["owner"],
          "amount": amount, "deposit": res.get("deposit", 0), "days": max(1, payload.days),
          "status": "RENTAL_REQUESTED", "contact_revealed": False, "contacts": None, "deposit_refunded": False, "reviewed": False,
          "provider_phone": res.get("owner_phone", "+91 98480 00000"), "needer_phone": "+91 91234 56789",
          "location": res.get("location", "Campus pickup"), "created_at": NOW(), "seed": False}
    await db.transactions.insert_one(dict(tx))
    return clean(tx)

SERVICE_FLOW = {
    ("HIRE_REQUESTED", "accept"): "PROVIDER_ACCEPTED",
    ("HIRE_REQUESTED", "decline"): "DECLINED",
    ("PROVIDER_ACCEPTED", "pay"): "PAYMENT_SECURED",
    ("PAYMENT_SECURED", "complete"): "PROVIDER_COMPLETED",
    ("PROVIDER_COMPLETED", "confirm"): "COMPLETED",
}
RESOURCE_FLOW = {
    ("RENTAL_REQUESTED", "accept"): "OWNER_ACCEPTED",
    ("RENTAL_REQUESTED", "decline"): "DECLINED",
    ("OWNER_ACCEPTED", "pay"): "PAYMENT_SECURED",
    ("PAYMENT_SECURED", "pickup"): "PICKED_UP",
    ("PICKED_UP", "return"): "RETURNED",
    ("RETURNED", "confirm_return"): "RETURN_CONFIRMED",
}

@api.get("/transactions")
async def list_transactions(user=Depends(require_session)):
    tx = [clean(t) for t in await db.transactions.find({"$or": [{"needer_id": user["user_id"]}, {"counterparty_id": user["user_id"]}]}).sort("created_at", -1).to_list(200)]
    return tx

@api.post("/transactions/{tx_id}/action")
async def tx_action(tx_id: str, payload: Action, user=Depends(require_session)):
    tx = await db.transactions.find_one({"id": tx_id}, {"_id": 0})
    if not tx: raise HTTPException(404, "Transaction not found")
    if user["user_id"] not in (tx["needer_id"], tx["counterparty_id"]): raise HTTPException(403, "Not your transaction.")
    flow = SERVICE_FLOW if tx["kind"] == "service" else RESOURCE_FLOW
    key = (tx["status"], payload.action)
    if key not in flow: raise HTTPException(400, f"Cannot '{payload.action}' from state {tx['status']}.")
    new_status = flow[key]
    upd = {"status": new_status}
    resp_extra = {}
    if payload.action == "pay":
        upd["contact_revealed"] = True
        upd["contacts"] = {"provider": tx["provider_phone"], "needer": tx["needer_phone"], "pickup": tx.get("location")}
        resp_extra["contacts"] = upd["contacts"]
    if payload.action == "confirm_return":
        upd["deposit_refunded"] = True
        upd["status"] = "COMPLETED"
        new_status = "COMPLETED"
    if new_status == "COMPLETED":
        await db.providers.update_one({"id": tx["counterparty_id"]}, {"$inc": {"gigs": 1}})
    await db.transactions.update_one({"id": tx_id}, {"$set": upd})
    updated = clean(await db.transactions.find_one({"id": tx_id}, {"_id": 0}))
    return {**updated, **resp_extra}

# ---------------- Reviews ----------------
@api.post("/reviews")
async def review(payload: ReviewCreate, user=Depends(require_session)):
    tx = await db.transactions.find_one({"id": payload.transaction_id}, {"_id": 0})
    if not tx: raise HTTPException(404, "Transaction not found")
    if tx["status"] != "COMPLETED": raise HTTPException(400, "Only completed transactions can be reviewed.")
    if tx.get("reviewed"): raise HTTPException(400, "This transaction is already reviewed.")
    rec = {"id": "rev-" + uuid.uuid4().hex[:8], "transaction_id": payload.transaction_id, "from_user": user["user_id"], "to_user": tx["counterparty_id"], "rating": max(1, min(5, payload.rating)), "text": payload.text, "created_at": NOW()}
    await db.reviews.insert_one(dict(rec))
    await db.transactions.update_one({"id": payload.transaction_id}, {"$set": {"reviewed": True}})
    # recompute provider reputation
    reviews = [r async for r in db.reviews.find({"to_user": tx["counterparty_id"]}, {"_id": 0})]
    if reviews:
        avg = round(sum(r["rating"] for r in reviews) / len(reviews), 1)
        await db.providers.update_one({"id": tx["counterparty_id"]}, {"$set": {"rating": avg}})
    return {"ok": True, "review": clean(rec), "message": "Review saved. Reputation updated."}

# ---------------- Insights ----------------
@api.get("/insights")
async def insights(user=Depends(require_session)):
    total_tx = await db.transactions.count_documents({})
    completed = await db.transactions.count_documents({"status": "COMPLETED"})
    users = await db.users.count_documents({})
    fulfilled = f"{round(completed/total_tx*100) if total_tx else 91}%"
    return {"metrics": [
        {"label": "Active students", "value": str(1284 + users)},
        {"label": "Active providers", "value": "347"},
        {"label": "Transactions", "value": str(628 + total_tx)},
        {"label": "Requests fulfilled", "value": fulfilled}],
        "demand": [["PPT Design", 42], ["Laptop Help", 31], ["Photography", 26], ["Video Editing", 19]],
        "undersupplied": [["Drafter", "37 searches · 8 available"], ["Laptop repair", "31 requests · 5 providers"], ["Engineering tutoring", "Demand rises near exams"]]}

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origin_regex=r"https?://(localhost(:\d+)?|[^/]+\.preview\.emergentagent\.com)", allow_origins=os.environ["CORS_ORIGINS"].split(","), allow_methods=["*"], allow_headers=["*"])

@app.on_event("shutdown")
async def shutdown(): client.close()
