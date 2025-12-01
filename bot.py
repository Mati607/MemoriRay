from pydantic.networks import EmailStr
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


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

if importlib.util.find_spec("baml_client") is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from baml_client import b as baml  # type: ignore
import baml_py

from fastapi.responses import HTMLResponse, Response
from pydantic import EmailStr


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    images: list[str] | None = None

class AddMemoryRequest(BaseModel):
    base_64_image: Optional[str] = None

class AddTrustedContactRequest(BaseModel):
    email_list: list[EmailStr]

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

contact_list = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
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

msg_history : list[str] = []


def email_contacts() -> str:
    global contact_list
    
    if not contact_list:
        return "No trusted contacts configured."
    
    # Get SendGrid API key from environment
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        print("Warning: SENDGRID_API_KEY not set. Emails not sent.")
        return f"Alert would be sent to: {', '.join(contact_list)}"
    
    try:
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
            print(f"Email sent to {email}: Status {response.status_code}")
        
        return f"Emergency alert sent to {len(contact_list)} trusted contact(s)."
        
    except Exception as e:
        print(f"Error sending emails: {e}")
        return f"Failed to send alerts. Please contact your trusted contacts directly."
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="`message` must not be empty.")

    sentiment = await baml.SentimentAnalysis(req.message)
    selected_memory = await get_memory(req.message)
    memory_description = selected_memory.description
    image_list = selected_memory.images
    escalate = await baml.TrustedContact(req.message)
    if escalate:
        escalate_message = email_contacts()
    else: 
        escalate_message = "The issue is not critical enough to escalate to the trusted contacts."
    reply_text = await baml.ChatReply(req.message, msg_history, sentiment, memory_description,escalate_message)
    msg_history.append(req.message + " -> " + reply_text)
    return ChatResponse(reply=reply_text, images=image_list)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="127.0.0.1", port=8000, reload=True)


def convert_image_to_base64(image_url: HttpUrl) -> str:
    response = requests.get(str(image_url), timeout=15)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("utf-8")

memory_descriptions : list[dict[str, int | str]] = []
images_store : list[str] = []

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

    description = await get_image_description_from_base64(b64_data, media_type)
    images_store.append(req.base_64_image)
    memory_descriptions.append({
        "description": description,
        "image_index": len(images_store) - 1,
    })

    return ChatResponse(reply=description)

@app.post("/add_trusted_contact", response_model=ChatResponse)
async def add_trusted_contact(req: AddTrustedContactRequest):  # Fix parameter type
    global contact_list
    if not req.email_list:
        raise HTTPException(status_code=400, detail="email list is required.")
    for email in req.email_list:
        contact_list.add(email)
    return ChatResponse(reply="trusted contact added successfully.")

@app.post("/get_trusted_contact", response_model=ChatResponse)
async def get_trusted_contact():
    global contact_list
    # Return as JSON string in 'reply' to satisfy ChatResponse schema
    return ChatResponse(reply=json.dumps(list(contact_list)))

async def get_memory(query: str) -> SelectedMemory:
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
    
@app.post("/generate_report",response_model=ChatResponse)
async def generate_report():
    global msg_history
    report = await baml.GenerateReport(msg_history)
    # Serialize the Report pydantic model to JSON string to satisfy ChatResponse schema
    return ChatResponse(reply=report.model_dump_json(indent=2))

@app.post("/generate_report_structured", response_model=GenerateReportResponse)
async def generate_report_structured():
    """
    Returns a structured clinical report with clear fields, decoupled from generated BAML models.
    """
    global msg_history
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