from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Header, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
import os, uuid, re, logging, requests as http_requests

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="Loop API")
api = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)

class OtpRequest(BaseModel): email: str
class OtpVerify(BaseModel): email: str; otp: str
class GoogleSessionRequest(BaseModel): session_id: str
class ProfileUpdate(BaseModel): name: str; college: str; branch: Optional[str] = ""
class RequestCreate(BaseModel): title: str; category: str; deadline: str; budget: int; description: str; recurring: bool = False
class Action(BaseModel): action: str
class PaymentRequest(BaseModel): item_id: str; kind: str; amount: int; deposit: int = 0
class ReviewCreate(BaseModel): transaction_id: str; rating: int; text: str

DEMO_USER = {"id":"user-harvey","email":"harvey@student.nitandhra.ac.in","name":"Harvey Specter","college":"NIT Andhra Pradesh","branch":"Civil Engineering","year":"3rd year","role":"student","email_verified":True,"student_verified":False,"verification_status":"Pending","personalization":"All three"}
PROVIDERS = [
 {"id":"provider-priya","name":"Priya Sharma","college":"NIT Andhra Pradesh","branch":"Civil Engineering","year":"3rd year","skill":"Engineering Mechanics · PPT Design","match":94,"rating":4.8,"gigs":27,"similar":8,"price":300,"availability":"Available today","verified":["Email Verified","Student Verified","Portfolio Verified"],"why":"Engineering Mechanics + PPT Design + 8 similar gigs + available before deadline.","bio":"Turns difficult mechanics concepts into clear, exam-ready decks."},
 {"id":"provider-rahul","name":"Rahul Mehta","college":"NIT Andhra Pradesh","branch":"Computer Science & Engineering","year":"4th year","skill":"PowerPoint · Visual Design","match":72,"rating":4.9,"gigs":41,"similar":3,"price":240,"availability":"Available tomorrow","verified":["Email Verified","Student Verified","Portfolio Verified"],"why":"Strong presentation craft + fast response time, with less Mechanics context.","bio":"Presentation designer for clubs, pitches, and academic work."},
 {"id":"provider-ananya","name":"Ananya Rao","college":"NIT Andhra Pradesh","branch":"Mechanical Engineering","year":"2nd year","skill":"Tutoring · CAD","match":67,"rating":4.7,"gigs":18,"similar":4,"price":250,"availability":"Available this week","verified":["Email Verified","Student Verified"],"why":"Mechanical background + relevant academic support experience.","bio":"Patient peer tutor who makes technical subjects less intimidating."},
]
RESOURCES = [
 {"id":"resource-casio","name":"Casio fx-991CW","price":20,"availability":"Available Sep 1–4","location":"Campus pickup","condition":"Good condition","owner":"Ishaan Kapoor","rating":4.9,"deposit":0,"emoji":"⌗"},
 {"id":"resource-drafter","name":"Drafter","price":20,"availability":"Available tomorrow","location":"Civil block pickup","condition":"Clean · lightly used","owner":"Meera Nair","rating":4.8,"deposit":300,"emoji":"⌁"},
 {"id":"resource-camera","name":"Sony Alpha camera","price":450,"availability":"Available this weekend","location":"Hostel C pickup","condition":"Excellent condition","owner":"Rohan Das","rating":4.9,"deposit":1500,"emoji":"◉"},
]
REQUESTS = [{"id":"req-1","title":"Engineering Mechanics PPT","budget":300,"deadline":"Due tomorrow","notified":3,"applied":2,"status":"2 applications","category":"Academic"},{"id":"req-2","title":"Need a LinkedIn photo","budget":200,"deadline":"Due Friday","notified":5,"applied":1,"status":"1 application","category":"Photography"}]
TRANSACTIONS = []
OTP_CHALLENGES = {}
SESSIONS = {}
OTP_MAX_ATTEMPTS = 5
OTP_LOCK_MINUTES = 5

def valid_email(email): return bool(re.match(r"^[^@\s]+@(student\.)?nitandhra\.ac\.in$", email.lower()))

@api.get("/")
async def root(): return {"message":"Loop API ready"}

@api.post("/auth/send-otp")
async def send_otp(payload: OtpRequest):
    email = payload.email.lower()
    if not valid_email(email): raise HTTPException(400, "Use a NIT Andhra Pradesh institutional email.")
    existing = OTP_CHALLENGES.get(email, {})
    locked_until = existing.get("locked_until")
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
        raise HTTPException(429, "Too many attempts. Try again in 5 minutes.", headers={"Retry-After":"300"})
    OTP_CHALLENGES[email] = {"otp":"123456","created_at":datetime.now(timezone.utc).isoformat(),"failed_attempts":0,"locked_until":None}
    return {"sent":True,"demo_otp":"123456","email":email,"role":"student" if "@student." in email else "faculty"}

@api.post("/auth/verify-otp")
async def verify_otp(payload: OtpVerify, response: Response):
    email = payload.email.lower()
    challenge = OTP_CHALLENGES.get(email)
    if not valid_email(email) or not challenge: raise HTTPException(400, "That OTP is not correct or has not been requested for this email.")
    locked_until = challenge.get("locked_until")
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
        raise HTTPException(429, "Too many attempts. Try again in 5 minutes.", headers={"Retry-After":"300"})
    if payload.otp != challenge["otp"]:
        challenge["failed_attempts"] = challenge.get("failed_attempts", 0) + 1
        if challenge["failed_attempts"] >= OTP_MAX_ATTEMPTS:
            challenge["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=OTP_LOCK_MINUTES)).isoformat()
            raise HTTPException(429, "Too many attempts. Try again in 5 minutes.", headers={"Retry-After":"300"})
        raise HTTPException(400, "That OTP is not correct or has not been requested for this email.")
    OTP_CHALLENGES.pop(email, None)
    SESSIONS["loop-demo-session"] = DEMO_USER
    response.set_cookie("session_token", "loop-demo-session", httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    return {"token":"loop-demo-session","user":DEMO_USER}

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
    existing = await db.users.find_one({"email":email},{"_id":0})
    user_id = (existing or {}).get("user_id") or (existing or {}).get("id") or f"user_{uuid.uuid4().hex[:12]}"
    user = {"user_id":user_id,"id":user_id,"email":email,"name":google.get("name") or email.split("@")[0],"picture":google.get("picture", ""),"college":"NIT Andhra Pradesh","branch":(existing or {}).get("branch", ""),"year":(existing or {}).get("year", ""),"role":"student" if "@student." in email else "faculty","email_verified":True,"student_verified":(existing or {}).get("student_verified", False),"verification_status":(existing or {}).get("verification_status", "Pending"),"personalization":(existing or {}).get("personalization", "All three")}
    await db.users.update_one({"email":email},{"$set":user,"$setOnInsert":{"created_at":datetime.now(timezone.utc).isoformat()}},upsert=True)
    session_token = google.get("session_token")
    if not session_token: raise HTTPException(401, "Google did not return a session token.")
    now = datetime.now(timezone.utc)
    await db.user_sessions.update_one({"session_token":session_token},{"$set":{"user_id":user_id,"session_token":session_token,"created_at":now.isoformat(),"expires_at":(now + timedelta(days=7)).isoformat()}},upsert=True)
    response.set_cookie("session_token", session_token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    return user

async def require_session(request: Request, authorization: Optional[str] = Header(default=None)):
    token = request.cookies.get("session_token") or (authorization.replace("Bearer ", "", 1) if authorization and authorization.startswith("Bearer ") else None)
    if token in SESSIONS: return SESSIONS[token]
    if not token: raise HTTPException(401, "Authentication required.")
    session = await db.user_sessions.find_one({"session_token":token},{"_id":0})
    if not session: raise HTTPException(401, "Authentication required.")
    expires_at = session.get("expires_at")
    if isinstance(expires_at, str): expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None: expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc): raise HTTPException(401, "Session expired.")
    user = await db.users.find_one({"user_id":session["user_id"]},{"_id":0})
    if not user: raise HTTPException(401, "User not found.")
    return user

@api.get("/auth/me")
async def me(user=Depends(require_session)): return user

@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        SESSIONS.pop(token, None)
        await db.user_sessions.delete_one({"session_token":token})
    response.delete_cookie("session_token", path="/", secure=True, samesite="none")
    return {"ok":True}

@api.get("/home")
async def home(): return {"user":DEMO_USER,"providers":PROVIDERS,"resources":RESOURCES,"requests":REQUESTS,"transactions":TRANSACTIONS}

@api.get("/search")
async def search(q: str = ""):
    term=q.lower().strip()
    services=[p for p in PROVIDERS if not term or any(x in (p["skill"]+p["name"]+p["bio"]).lower() for x in term.split())]
    resources=[r for r in RESOURCES if not term or any(x in (r["name"]+r["condition"]+r["location"]).lower() for x in term.split())]
    if "drone" in term: services=[]; resources=[]
    return {"query":q,"services":services,"resources":resources,"intent":"NEED","explanation":"We looked across services and resources, then ranked by relevance and availability."}

@api.get("/providers/{provider_id}")
async def provider(provider_id: str):
    match=next((p for p in PROVIDERS if p["id"]==provider_id),None)
    if not match: raise HTTPException(404,"Provider not found")
    return match

@api.post("/requests")
async def create_request(payload: RequestCreate):
    item={"id":"req-"+uuid.uuid4().hex[:6],**payload.model_dump(),"notified":3,"applied":0,"status":"Waiting for applications"}
    REQUESTS.insert(0,item)
    return item

@api.get("/requests")
async def requests(): return REQUESTS

@api.post("/requests/{request_id}/apply")
async def apply(request_id: str):
    for item in REQUESTS:
        if item["id"]==request_id: item["applied"]+=1; item["status"]=f"{item['applied']} application" + ("s" if item["applied"] != 1 else ""); return {"ok":True,"application_number":item["applied"]}
    raise HTTPException(404,"Request not found")

@api.post("/payments")
async def payment(payload: PaymentRequest, user=Depends(require_session)):
    tx={"id":"tx-"+uuid.uuid4().hex[:8],"item_id":payload.item_id,"kind":payload.kind,"amount":payload.amount,"deposit":payload.deposit,"status":"PAYMENT_SECURED","contact_revealed":True,"created_at":datetime.now(timezone.utc).isoformat()}
    TRANSACTIONS.insert(0,tx); return {**tx,"contacts":{"provider":"+91 98765 43210","needer":"+91 91234 56789"}}

@api.post("/transactions/{tx_id}/action")
async def tx_action(tx_id: str, payload: Action, user=Depends(require_session)):
    tx=next((x for x in TRANSACTIONS if x["id"]==tx_id),None)
    if not tx: raise HTTPException(404,"Transaction not found")
    tx["status"]={"complete":"PROVIDER_COMPLETED","confirm":"COMPLETED","return":"RETURN_CONFIRMED","refund":"DEPOSIT_REFUNDED"}.get(payload.action,payload.action.upper()); return tx

@api.post("/reviews")
async def review(payload: ReviewCreate): return {"ok":True,"message":"Review saved. Reputation updated for relevant work."}

@api.post("/verification/upload")
async def upload(file: UploadFile = File(...), user=Depends(require_session)): return {"status":"Pending","filename":file.filename}

@api.get("/insights")
async def insights(): return {"metrics":[{"label":"Active students","value":"184"},{"label":"Completed transactions","value":"96"},{"label":"Fulfillment rate","value":"78%"},{"label":"Supply gap","value":"12 searches"}],"demand":[["PPT Design",42],["Laptop Help",31],["Photography",26],["Mechanics tutoring",19]],"resources":[["fx-991CW",87],["Drafters",54],["Cameras",28]]}

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origin_regex=r"https?://(localhost(:\d+)?|[^/]+\.preview\.emergentagent\.com)", allow_origins=os.environ["CORS_ORIGINS"].split(","), allow_methods=["*"], allow_headers=["*"])

@app.on_event("shutdown")
async def shutdown(): client.close()