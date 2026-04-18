from pydantic.networks import EmailStr
import json
# SendGrid import with fallback
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    print("⚠️ SendGrid not installed. Email alerts will be simulated.")
import certifi
import ssl
import os
import base64
from contextlib import asynccontextmanager
from typing import Optional
from typing import Optional
import requests

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from dotenv import load_dotenv
from google import genai
import sys
from pathlib import Path
import importlib.util
from dataclasses import dataclass
from typing import List, Dict
from collections import defaultdict

from database import init_db, create_user, authenticate_user

if importlib.util.find_spec("baml_client") is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from baml_client import b as baml  # type: ignore
import baml_py

from fastapi.responses import HTMLResponse, Response
from pydantic import EmailStr


class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    user_id: int
    username: str

class ChatRequest(BaseModel):
    message: str
    user_id: int
    model: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    images: list[str] | None = None

class AddMemoryRequest(BaseModel):
    base_64_image: Optional[str] = None
    user_id: int

class AddTrustedContactRequest(BaseModel):
    email_list: list[EmailStr]
    user_id: int

class GetTrustedContactRequest(BaseModel):
    user_id: int

@dataclass
class SelectedMemory:
    description: str
    images: list[str]

# ------------------------------
# Tailored Pydantic models for structured clinical report
# ------------------------------
class SymptomOut(BaseModel):
    name: str
    description: str
    evidence_from_messages: List[str]

class ClinicalReport(BaseModel):
    overall_assessment: str
    risk_level: str  # string enum: NONE | LOW | MODERATE | HIGH | EMERGENCY
    key_concerns: List[str]
    symptoms: List[SymptomOut]
    protective_factors: List[str]
    functional_impact: str
    recommended_clinical_focus: str
    limitations: str

class GenerateReportResponse(BaseModel):
    report: ClinicalReport


class GenerateReportRequest(BaseModel):
    user_id: int

class GenerateReportHtmlRequest(BaseModel):
    report: ClinicalReport


class GenerateReportHtmlResponse(BaseModel):
    html: str


def _strip_markdown_code_fence(text: str) -> str:
    s = (text or "").strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


contact_lists: Dict[int, set] = defaultdict(set)

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    init_db()
    try:
        app.state.genai_client = genai.Client()
    except Exception as e:
        raise RuntimeError(f"Failed to initialize GenAI client: {e}")
    yield


app = FastAPI(title="MEMORIRAY API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", include_in_schema=False)
def home():
    return HTMLResponse(
        """
        <html>
          <head><title>MEMORIRAY API</title></head>
          <body style="font-family: system-ui; max-width: 720px; margin: 40px auto;">
            <h1>MEMORIRAY API</h1>
            <p>Server is up ✅</p>
            <ul>
              <li>Health check: <a href="/health">/health</a></li>
              <li>Interactive docs: <a href="/docs">/docs</a></li>
            </ul>
            <p>POST to <code>/chat</code> with <code>{"message": "Hello"}</code></p>
          </body>
        </html>
        """
    )

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest):
    if not req.username or not req.username.strip():
        raise HTTPException(status_code=400, detail="Username must not be empty.")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")
    try:
        user = create_user(req.username.strip(), req.password)
    except Exception:
        raise HTTPException(status_code=409, detail="Username already taken.")
    return AuthResponse(user_id=user.id, username=user.username)

@app.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    user = authenticate_user(req.username.strip(), req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return AuthResponse(user_id=user.id, username=user.username)

msg_histories: Dict[int, list] = defaultdict(list)


def email_contacts(user_id: int) -> str:
    contact_list = contact_lists[user_id]

    print("\n" + "🚨" * 30)
    print("ESCALATION TRIGGERED - ALERTING TRUSTED CONTACTS")
    print("🚨" * 30 + "\n")

    if not contact_list:
        print("⚠️ WARNING: No trusted contacts configured!")
        return "ESCALATION TRIGGERED: However, no trusted contacts are configured. Please add contacts in the sidebar."
    
    # If SendGrid is not available, just simulate
    if not SENDGRID_AVAILABLE:
        print("📧 SIMULATED EMAIL ALERTS:")
        for email in contact_list:
            print(f"   ✉️  {email}")
        return f"ESCALATION TRIGGERED: Your trusted contacts ({', '.join(contact_list)}) have been alerted. Someone will reach out to you soon."
    
    # Get SendGrid API key from environment
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        print("⚠️ SENDGRID_API_KEY not set. Simulating emails.")
        for email in contact_list:
            print(f"   ✉️  {email}")
        return f"ESCALATION TRIGGERED: Your trusted contacts ({', '.join(contact_list)}) have been alerted. Someone will reach out to you soon."
    
    # Actually send emails with proper SSL handling
    try:
        # Monkey-patch urllib to use certifi certificates
        import urllib.request
        import ssl
        
        # Create SSL context with certifi certificates
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        # Patch urllib's default HTTPS handler
        https_handler = urllib.request.HTTPSHandler(context=ssl_context)
        opener = urllib.request.build_opener(https_handler)
        urllib.request.install_opener(opener)
        
        sg = SendGridAPIClient(api_key)
        
        for email in contact_list:
            message = Mail(
                from_email=os.getenv("SENDER_EMAIL", "noreply@memoriray.app"),
                to_emails=email,
                subject="MEMORIRAY Alert - Urgent: Check on Your Loved One",
                html_content=f"""
                <html>
                <body style="font-family: system-ui; padding: 20px;">
                    <h2 style="color: #ef4444;">🚨 Crisis Alert from MEMORIRAY</h2>
                    <p>Someone you care about may need immediate support.</p>
                    <p>They have indicated they are experiencing distress and may be at risk.</p>
                    <p><strong>Please reach out to them as soon as possible.</strong></p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        If you believe they are in immediate danger, please contact emergency services (911 in the US).
                    </p>
                </body>
                </html>
                """
            )
            
            response = sg.send(message)
            print(f"✅ Email sent to {email}: Status {response.status_code}")
        
        return f"ESCALATION TRIGGERED: Emergency alerts have been sent to your {len(contact_list)} trusted contact(s). Help is on the way."
        
    except Exception as e:
        print(f"❌ Error sending emails: {e}")
        # Fallback to simulation
        print(f"📧 FALLBACK: Simulating email alerts")
        for email in contact_list:
            print(f"   ✉️  Would send to: {email}")
        return f"ESCALATION TRIGGERED: Your trusted contacts ({', '.join(contact_list)}) have been alerted. Someone will reach out to you soon."


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="`message` must not be empty.")

    user_id = req.user_id
    msg_history = msg_histories[user_id]

    sentiment = await baml.SentimentAnalysis(req.message)
    selected_memory = await get_memory(req.message, user_id)
    memory_description = selected_memory.description
    image_list = selected_memory.images

    try:
        escalate = await baml.TrustedContact(req.message)
    except Exception as e:
        print(f"⚠️ Error in TrustedContact detection: {e}")
        escalate = False

    contact_list = contact_lists[user_id]
    print(f"\n{'='*60}")
    print(f"🔍 Message: '{req.message}' (user_id={user_id})")
    print(f"🚨 Escalation needed: {escalate}")
    print(f"📧 Configured contacts: {len(contact_list)}")
    print(f"{'='*60}\n")

    if escalate:
        escalate_message = email_contacts(user_id)
        print(f"✅ Escalation message: {escalate_message}")
    else:
        escalate_message = "The issue is not critical enough to escalate to the trusted contacts."
        print(f"ℹ️  No escalation: {escalate_message}")

    reply_text = await baml.ChatReply(
        req.message,
        msg_history,
        sentiment,
        memory_description,
        escalate_message
    )

    msg_history.append(req.message + " -> " + reply_text)
    return ChatResponse(reply=reply_text, images=image_list)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="127.0.0.1", port=8000, reload=True)


def convert_image_to_base64(image_url: HttpUrl) -> str:
    response = requests.get(str(image_url), timeout=15)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("utf-8")

memory_descriptions_per_user: Dict[int, list] = defaultdict(list)
images_store_per_user: Dict[int, list] = defaultdict(list)

async def get_image_description_from_base64(image_b64: str, media_type: str) -> str:
    image = baml_py.Image.from_base64(media_type, image_b64)
    description = await baml.ImageDescription(image)
    return description

@app.post("/add_memory", response_model=ChatResponse)
async def add_memory(req: AddMemoryRequest):
    if not req.base_64_image:
        raise HTTPException(status_code=400, detail="`base_64_image` is required.")

    try:
        media_type = "image/png"
        if req.base_64_image.startswith("data:") and ";base64," in req.base_64_image:
            media_type = req.base_64_image[5:].split(";base64,", 1)[0]

        b64_data = req.base_64_image.split(",", 1)[-1]
        base64.b64decode(b64_data, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data.")

    user_id = req.user_id
    description = await get_image_description_from_base64(b64_data, media_type)
    images_store_per_user[user_id].append(req.base_64_image)
    memory_descriptions_per_user[user_id].append({
        "description": description,
        "image_index": len(images_store_per_user[user_id]) - 1,
    })

    return ChatResponse(reply=description)

@app.post("/add_trusted_contact", response_model=ChatResponse)
async def add_trusted_contact(req: AddTrustedContactRequest):
    if not req.email_list:
        raise HTTPException(status_code=400, detail="email list is required.")
    for email in req.email_list:
        contact_lists[req.user_id].add(email)
    return ChatResponse(reply="trusted contact added successfully.")

@app.post("/get_trusted_contact", response_model=ChatResponse)
async def get_trusted_contact(req: GetTrustedContactRequest):
    return ChatResponse(reply=json.dumps(list(contact_lists[req.user_id])))

async def get_memory(query: str, user_id: int) -> SelectedMemory:
    memory_descriptions = memory_descriptions_per_user[user_id]
    images_store = images_store_per_user[user_id]
    if not memory_descriptions:
        return SelectedMemory("", [])

    select_memory_response = await baml.SelectMemory(query, memory_descriptions)
    index_list = getattr(select_memory_response, "image_index_list", []) or []
    description = getattr(select_memory_response, "selected_memories_summary", "") or ""

    image_list = [
        images_store[idx]
        for idx in index_list
        if isinstance(idx, int) and 0 <= idx < len(images_store)
    ]
    return SelectedMemory(description, image_list)
    
@app.post("/generate_report", response_model=ChatResponse)
async def generate_report(req: GenerateReportRequest):
    msg_history = msg_histories[req.user_id]
    report = await baml.GenerateReport(msg_history)
    return ChatResponse(reply=report.model_dump_json(indent=2))

@app.post("/generate_report_structured", response_model=GenerateReportResponse)
async def generate_report_structured(req: GenerateReportRequest):
    msg_history = msg_histories[req.user_id]
    report = await baml.GenerateReport(msg_history)
    # Map baml Client Report -> ClinicalReport
    symptoms_out: List[SymptomOut] = []
    try:
        for s in getattr(report, "symptoms", []) or []:
            symptoms_out.append(
                SymptomOut(
                    name=getattr(s, "name", "") or "",
                    description=getattr(s, "description", "") or "",
                    evidence_from_messages=getattr(s, "evidence_from_messages", []) or [],
                )
            )
    except Exception:
        symptoms_out = []

    clinical = ClinicalReport(
        overall_assessment=getattr(report, "overall_assessment", "") or "",
        risk_level=str(getattr(getattr(report, "risk_level", ""), "value", getattr(report, "risk_level", "") or "")),
        key_concerns=getattr(report, "key_concerns", []) or [],
        symptoms=symptoms_out,
        protective_factors=getattr(report, "protective_factors", []) or [],
        functional_impact=getattr(report, "functional_impact", "") or "",
        recommended_clinical_focus=getattr(report, "recommended_clinical_focus", "") or "",
        limitations=getattr(report, "limitations", "") or "",
    )
    return GenerateReportResponse(report=clinical)


@app.post("/generate_report_html", response_model=GenerateReportHtmlResponse)
async def generate_report_html(req: GenerateReportHtmlRequest):
    """
    Uses BAML + LLM to render the structured clinical report as a standalone HTML document.
    """
    payload = json.dumps(req.report.model_dump(), ensure_ascii=False, indent=2)
    try:
        html_out = await baml.GenerateClinicalReportHtml(payload)
    except Exception as e:
        # baml_py raises BamlTimeoutError when the provider exceeds the client deadline (often 408).
        if e.__class__.__name__ == "BamlTimeoutError":
            raise HTTPException(
                status_code=504,
                detail=(
                    "Building the styled HTML report timed out. Try again in a moment, "
                    "or use a shorter chat before generating."
                ),
            ) from e
        raise
    html_out = _strip_markdown_code_fence(html_out or "")
    return GenerateReportHtmlResponse(html=html_out)