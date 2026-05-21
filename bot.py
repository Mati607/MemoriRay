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
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path
import importlib.util
from dataclasses import dataclass
from typing import List, Dict
from collections import defaultdict

from database import (
    init_db, create_user, authenticate_user, save_mood_entry, get_mood_history,
    add_therapy_exercise, get_user_exercises, get_exercise_templates,
    add_mood_insight, get_user_insights, save_weekly_report, get_latest_weekly_report,
    create_exercise_template
)
from analytics_service import MoodAnalytics, TherapyRecommender, InsightGenerator
from goal_tracking import GoalTracker, MilestoneTracker
from wellness_recommender import WellnessRecommender, CopingStrategyAdvisor
from export_service import MoodDataExporter, ProgressReportGenerator
from journal_models import init_journal_models
from journal_api import router as journal_router

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


class MoodEntryOut(BaseModel):
    timestamp: str
    mood_score: float
    sentiment_text: str
    message_snippet: str


class MoodHistoryResponse(BaseModel):
    entries: List[MoodEntryOut]
    total: int


# ── Sentiment → numeric mood score (0–10) ──────────────────────────────────
_POSITIVE_KEYWORDS: Dict[str, float] = {
    "happy": 8.0, "joyful": 9.0, "grateful": 8.0, "hopeful": 7.5,
    "calm": 7.0, "peaceful": 7.5, "excited": 8.5, "motivated": 8.0,
    "positive": 7.5, "better": 6.5, "good": 7.0, "great": 8.0,
    "wonderful": 9.0, "content": 7.0, "relieved": 6.5, "loved": 8.5,
    "energetic": 8.0, "confident": 8.0, "optimistic": 7.5, "proud": 8.0,
    "cheerful": 8.0, "safe": 7.0, "improving": 6.5, "healing": 7.0,
    "connected": 7.5, "supported": 7.5, "balanced": 7.0, "refreshed": 7.5,
}

_NEGATIVE_KEYWORDS: Dict[str, float] = {
    "sad": 3.0, "anxious": 2.5, "depressed": 1.5, "hopeless": 1.0,
    "alone": 2.0, "scared": 2.0, "worried": 3.0, "stressed": 3.0,
    "overwhelmed": 2.0, "lost": 2.5, "exhausted": 2.5, "angry": 3.0,
    "frustrated": 3.5, "upset": 3.0, "guilty": 3.0, "shame": 2.0,
    "fear": 2.5, "numb": 2.0, "empty": 1.5, "crying": 2.5, "pain": 2.0,
    "hurt": 2.5, "crisis": 1.0, "desperate": 1.5, "helpless": 1.5,
    "worthless": 1.0, "terrible": 2.0, "horrible": 1.5, "miserable": 1.5,
    "grief": 2.0, "trauma": 2.0, "isolated": 2.0, "struggling": 3.0,
}


def score_sentiment(sentiment_text: str) -> float:
    text = (sentiment_text or "").lower()
    scores: List[float] = []
    for word, score in _POSITIVE_KEYWORDS.items():
        if word in text:
            scores.append(score)
    for word, score in _NEGATIVE_KEYWORDS.items():
        if word in text:
            scores.append(score)
    if not scores:
        return 5.0
    return round(sum(scores) / len(scores), 2)


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
        init_journal_models()
    except Exception as e:
        print(f"⚠️ Journal model init failed: {e}")
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

app.include_router(journal_router)

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

    try:
        mood_score = score_sentiment(str(sentiment))
        save_mood_entry(
            user_id=user_id,
            sentiment_text=str(sentiment)[:1000],
            mood_score=mood_score,
            message_snippet=req.message[:300],
        )
    except Exception as e:
        print(f"⚠️ Could not save mood entry: {e}")

    return ChatResponse(reply=reply_text, images=image_list)

@app.get("/mood_history/{user_id}", response_model=MoodHistoryResponse)
def mood_history(user_id: int, limit: int = 90):
    """Return persisted mood entries for a user, newest first."""
    raw = get_mood_history(user_id, limit=limit)
    entries = [
        MoodEntryOut(
            timestamp=e["timestamp"],
            mood_score=float(e["mood_score"] or 5.0),
            sentiment_text=e["sentiment_text"] or "",
            message_snippet=e["message_snippet"] or "",
        )
        for e in raw
    ]
    return MoodHistoryResponse(entries=entries, total=len(entries))


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


# ── Analytics & Therapy Exercises ──────────────────────────────────────────
class MoodStatsRequest(BaseModel):
    user_id: int
    days: int = 30

class MoodStatisticsResponse(BaseModel):
    avg_mood: float | None
    min_mood: float | None
    max_mood: float | None
    volatility: float | None
    total_entries: int

@app.post("/analytics/mood_stats", response_model=MoodStatisticsResponse)
def get_mood_stats(req: MoodStatsRequest):
    """Get mood statistics for a user over N days."""
    stats = MoodAnalytics.get_mood_statistics(req.user_id, days=req.days)
    return MoodStatisticsResponse(**stats)

class MoodPatternsResponse(BaseModel):
    daily_averages: Dict[str, float]
    best_day: str | None
    worst_day: str | None
    dominant_emotions: List[str]
    emotion_distribution: Dict[str, int]

@app.post("/analytics/patterns", response_model=MoodPatternsResponse)
def get_patterns(req: MoodStatsRequest):
    """Identify mood patterns in user data."""
    patterns = MoodAnalytics.identify_mood_patterns(req.user_id, days=req.days)
    return MoodPatternsResponse(**patterns)

class TriggerResponse(BaseModel):
    trigger: str
    frequency: int
    impact: str

@app.post("/analytics/triggers", response_model=List[TriggerResponse])
def get_triggers(req: MoodStatsRequest):
    """Detect mood triggers from user history."""
    triggers = MoodAnalytics.detect_mood_triggers(req.user_id, days=req.days)
    return [TriggerResponse(**t) for t in triggers]

class WeeklySummaryResponse(BaseModel):
    week_start: str
    week_end: str
    avg_mood_score: float | None
    volatility: float | None
    best_day: str | None
    worst_day: str | None
    dominant_emotions: List[str]
    exercises_completed: int
    avg_exercise_effectiveness: float | None
    total_entries: int

@app.post("/analytics/weekly_summary", response_model=WeeklySummaryResponse)
def get_weekly_summary(req: MoodStatsRequest):
    """Generate a summary of the user's week."""
    summary = MoodAnalytics.generate_weekly_summary(req.user_id)
    return WeeklySummaryResponse(**summary)

class ImprovementSuggestionsResponse(BaseModel):
    suggestions: List[str]

@app.post("/analytics/suggestions", response_model=ImprovementSuggestionsResponse)
def get_improvement_suggestions(req: MoodStatsRequest):
    """Get personalized improvement suggestions."""
    suggestions = MoodAnalytics.generate_improvement_suggestions(req.user_id)
    return ImprovementSuggestionsResponse(suggestions=suggestions)

class ExerciseRecommendationResponse(BaseModel):
    exercise_type: str
    name: str
    description: str
    reason: str

class RecommendExercisesResponse(BaseModel):
    recommendations: List[ExerciseRecommendationResponse]

@app.post("/therapy/recommend", response_model=RecommendExercisesResponse)
def recommend_exercises(req: MoodStatsRequest):
    """Get therapy exercise recommendations based on mood patterns."""
    recommendations = TherapyRecommender.recommend_exercises(req.user_id, top_n=3)
    return RecommendExercisesResponse(
        recommendations=[ExerciseRecommendationResponse(**r) for r in recommendations]
    )

class CompleteExerciseRequest(BaseModel):
    user_id: int
    exercise_type: str
    name: str
    description: str
    category: str
    duration_minutes: int | None = None
    effectiveness_rating: float | None = None
    notes: str | None = None

@app.post("/therapy/complete_exercise")
def complete_exercise(req: CompleteExerciseRequest):
    """Log a completed therapy exercise."""
    add_therapy_exercise(
        user_id=req.user_id,
        exercise_type=req.exercise_type,
        name=req.name,
        description=req.description,
        category=req.category,
        duration_minutes=req.duration_minutes,
        effectiveness_rating=req.effectiveness_rating,
        notes=req.notes,
    )
    return {"status": "success", "message": "Exercise logged successfully"}

class UserExercisesResponse(BaseModel):
    exercises: List[Dict]
    total: int

@app.post("/therapy/history", response_model=UserExercisesResponse)
def get_exercise_history(req: MoodStatsRequest):
    """Get user's therapy exercise history."""
    exercises = get_user_exercises(req.user_id, limit=50)
    return UserExercisesResponse(exercises=exercises, total=len(exercises))

class InsightResponse(BaseModel):
    type: str
    title: str
    description: str
    confidence: float

class InsightsResponse(BaseModel):
    insights: List[InsightResponse]

@app.post("/analytics/insights", response_model=InsightsResponse)
def get_insights(req: MoodStatsRequest):
    """Get AI-generated insights from mood data."""
    insights = InsightGenerator.generate_all_insights(req.user_id)
    return InsightsResponse(
        insights=[InsightResponse(**i) for i in insights]
    )

class UserInsightsResponse(BaseModel):
    insights: List[Dict]
    total: int

@app.post("/analytics/insight_history", response_model=UserInsightsResponse)
def get_insight_history(req: MoodStatsRequest):
    """Get previously generated insights for a user."""
    insights = get_user_insights(req.user_id, limit=20)
    return UserInsightsResponse(insights=insights, total=len(insights))

class WeeklyReportResponse(BaseModel):
    week_start: str
    week_end: str
    avg_mood_score: float | None
    best_day: str | None
    worst_day: str | None
    mood_volatility: float | None
    dominant_emotions: str | None
    exercises_completed: int
    key_improvements: str | None
    recommendations: str | None
    generated_at: str

@app.post("/analytics/latest_report", response_model=WeeklyReportResponse | None)
def get_latest_report(req: MoodStatsRequest):
    """Get the latest weekly report for a user."""
    report = get_latest_weekly_report(req.user_id)
    return WeeklyReportResponse(**report) if report else None

class GenerateWeeklyReportRequest(BaseModel):
    user_id: int

@app.post("/analytics/generate_report")
def generate_weekly_report_endpoint(req: GenerateWeeklyReportRequest):
    """Generate and save a new weekly report."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=7)

    summary = MoodAnalytics.generate_weekly_summary(req.user_id)
    patterns = MoodAnalytics.identify_mood_patterns(req.user_id, days=7)
    suggestions = MoodAnalytics.generate_improvement_suggestions(req.user_id)

    dominant_emotions_str = ", ".join(patterns.get("dominant_emotions", []))
    key_improvements_str = "\n".join(suggestions[:2]) if suggestions else "Continue monitoring mood trends."
    recommendations_str = "\n".join(suggestions[2:]) if len(suggestions) > 2 else ""

    save_weekly_report(
        user_id=req.user_id,
        week_start=week_start,
        week_end=week_end,
        avg_mood_score=summary.get("avg_mood_score"),
        best_day=summary.get("best_day"),
        worst_day=summary.get("worst_day"),
        mood_volatility=summary.get("volatility"),
        dominant_emotions=dominant_emotions_str,
        exercises_completed=summary.get("exercises_completed", 0),
        key_improvements=key_improvements_str,
        recommendations=recommendations_str,
    )

    return {
        "status": "success",
        "message": "Weekly report generated and saved",
        "summary": summary,
    }

class ExerciseTemplateResponse(BaseModel):
    id: int
    exercise_type: str
    name: str
    description: str
    instructions: str
    category: str
    estimated_duration: int
    difficulty_level: str

class ListExerciseTemplatesResponse(BaseModel):
    templates: List[ExerciseTemplateResponse]
    total: int

@app.get("/therapy/templates", response_model=ListExerciseTemplatesResponse)
def list_exercise_templates(category: str = None):
    """Get available therapy exercise templates."""
    templates = get_exercise_templates(category=category)
    return ListExerciseTemplatesResponse(templates=templates, total=len(templates))

class RecordMoodRequest(BaseModel):
    user_id: int
    mood_score: float
    sentiment_text: str = ""
    emotion_category: str = ""
    intensity: float = 5.0
    triggers: str = ""
    message_snippet: str = ""

@app.post("/mood/record")
def record_mood(req: RecordMoodRequest):
    """Record a mood entry with emotions, intensity, and triggers."""
    from database import SessionLocal, MoodEntry
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        entry = MoodEntry(
            user_id=req.user_id,
            mood_score=req.mood_score,
            sentiment_text=req.sentiment_text,
            emotion_category=req.emotion_category,
            intensity=req.intensity,
            triggers=req.triggers,
            message_snippet=req.message_snippet[:300] if req.message_snippet else "",
            timestamp=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.commit()
    finally:
        db.close()

    return {
        "status": "success",
        "message": "Mood entry recorded",
        "mood_score": req.mood_score,
        "emotion": req.emotion_category,
    }

class GetMoodDataResponse(BaseModel):
    dates: List[str]
    scores: List[float]
    emotions: List[str]
    intensity: List[float]

@app.post("/mood/data", response_model=GetMoodDataResponse)
def get_mood_data(req: MoodStatsRequest):
    """Get mood data for charting and visualization."""
    db = SessionLocal()
    try:
        from datetime import timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=req.days)
        entries = (
            db.query(MoodEntry)
            .filter(MoodEntry.user_id == req.user_id, MoodEntry.timestamp >= cutoff)
            .order_by(MoodEntry.timestamp.asc())
            .all()
        )

        return GetMoodDataResponse(
            dates=[e.timestamp.isoformat() for e in entries],
            scores=[e.mood_score or 0 for e in entries],
            emotions=[e.emotion_category or "unknown" for e in entries],
            intensity=[e.intensity or 5.0 for e in entries],
        )
    finally:
        db.close()


# ── Wellness & Goals ──────────────────────────────────────────────────────
class GoalResponse(BaseModel):
    id: int
    title: str
    goal_type: str
    target_value: float
    current_value: float
    progress_percent: float
    is_completed: bool
    days_remaining: int | None
    unit: str

class GoalsListResponse(BaseModel):
    goals: List[GoalResponse]
    total: int

@app.post("/wellness/goals", response_model=GoalsListResponse)
def get_goals(req: MoodStatsRequest):
    """Get user's wellness goals."""
    goals = GoalTracker.get_user_goals(req.user_id, include_completed=False)
    return GoalsListResponse(goals=goals, total=len(goals))

class CreateGoalRequest(BaseModel):
    user_id: int
    title: str
    goal_type: str
    target_value: float
    target_date: str
    description: str = ""

@app.post("/wellness/create_goal")
def create_goal(req: CreateGoalRequest):
    """Create a new wellness goal."""
    from datetime import datetime as dt
    target_dt = dt.fromisoformat(req.target_date)
    goal_id = GoalTracker.create_goal(
        user_id=req.user_id,
        title=req.title,
        goal_type=req.goal_type,
        target_value=req.target_value,
        target_date=target_dt,
        description=req.description,
    )
    return {"status": "success", "goal_id": goal_id}

class UpdateGoalProgressRequest(BaseModel):
    goal_id: int
    user_id: int
    value: float
    notes: str = ""

@app.post("/wellness/update_progress")
def update_goal_progress(req: UpdateGoalProgressRequest):
    """Update progress on a goal."""
    GoalTracker.record_progress(
        goal_id=req.goal_id,
        user_id=req.user_id,
        value=req.value,
        notes=req.notes,
    )
    return {"status": "success", "message": "Progress recorded"}

@app.post("/wellness/suggest_goals", response_model=dict)
def suggest_goals(req: MoodStatsRequest):
    """Get goal suggestions based on user data."""
    suggestions = GoalTracker.suggest_goals_for_user(req.user_id)
    return {"suggestions": suggestions}

class WellnessRecommendationResponse(BaseModel):
    type: str
    title: str
    description: str
    actions: List[str]
    priority: str
    emoji: str

class RecommendationsResponse(BaseModel):
    recommendations: List[WellnessRecommendationResponse]

@app.post("/wellness/recommendations", response_model=RecommendationsResponse)
def get_wellness_recommendations(req: MoodStatsRequest):
    """Get personalized wellness recommendations."""
    recommendations = WellnessRecommender.generate_recommendations(req.user_id)
    return RecommendationsResponse(
        recommendations=[WellnessRecommendationResponse(**r) for r in recommendations]
    )

class ActionPlanResponse(BaseModel):
    duration_days: int
    priority_actions: List[Dict]
    daily_schedule: List[Dict]

@app.post("/wellness/action_plan", response_model=dict)
def get_action_plan(req: MoodStatsRequest):
    """Get personalized action plan."""
    plan = WellnessRecommender.get_action_plan(req.user_id, days=7)
    return {"plan": plan}

class MilestoneResponse(BaseModel):
    id: str
    name: str
    description: str
    icon: str

class MilestonesResponse(BaseModel):
    milestones: List[MilestoneResponse]

@app.post("/wellness/milestones", response_model=MilestonesResponse)
def get_milestones(req: MoodStatsRequest):
    """Get achieved milestones."""
    milestones = MilestoneTracker.check_milestones(req.user_id)
    return MilestonesResponse(milestones=[MilestoneResponse(**m) for m in milestones])

class CopingStrategyRequest(BaseModel):
    emotion: str
    urgency: str = "immediate"

class CopingStrategyResponse(BaseModel):
    emotion: str
    urgency: str
    strategies: List[str]

@app.post("/wellness/coping_strategies", response_model=CopingStrategyResponse)
def get_coping_strategies(req: CopingStrategyRequest):
    """Get coping strategies for an emotion."""
    strategies = CopingStrategyAdvisor.get_strategy_for_emotion(req.emotion, req.urgency)
    return CopingStrategyResponse(
        emotion=req.emotion,
        urgency=req.urgency,
        strategies=strategies,
    )

class ExportRequest(BaseModel):
    user_id: int
    format: str = "csv"

@app.post("/export/mood_data")
def export_mood_data(req: ExportRequest):
    """Export mood data as CSV."""
    csv_data = MoodDataExporter.export_to_csv(req.user_id, days=90)
    return {
        "status": "success",
        "data": csv_data,
        "filename": f"mood_data_{req.user_id}.csv",
    }

@app.post("/export/exercises")
def export_exercises(req: ExportRequest):
    """Export exercise history as CSV."""
    csv_data = MoodDataExporter.export_exercises_to_csv(req.user_id, days=90)
    return {
        "status": "success",
        "data": csv_data,
        "filename": f"exercises_{req.user_id}.csv",
    }

@app.post("/export/weekly_reports")
def export_reports(req: ExportRequest):
    """Export weekly reports as CSV."""
    csv_data = MoodDataExporter.export_weekly_report_to_csv(req.user_id)
    return {
        "status": "success",
        "data": csv_data,
        "filename": f"reports_{req.user_id}.csv",
    }

@app.get("/health/status")
def get_health_status():
    """Get overall health status."""
    return {
        "status": "healthy",
        "services": {
            "database": "ok",
            "genai": "ok",
            "analytics": "ok",
        },
    }


# Initialize exercise templates on startup
_exercise_templates_initialized = False

@app.on_event("startup")
def initialize_templates():
    """Populate exercise templates on app startup."""
    global _exercise_templates_initialized
    if _exercise_templates_initialized:
        return

    try:
        existing = get_exercise_templates()
        if existing:
            _exercise_templates_initialized = True
            return
    except Exception:
        pass

    templates = [
        {
            "exercise_type": "breathing",
            "name": "Box Breathing",
            "description": "A calming breathing technique to reduce anxiety and stress",
            "instructions": "1. Breathe in for 4 counts\n2. Hold for 4 counts\n3. Exhale for 4 counts\n4. Hold for 4 counts\n5. Repeat 5-10 times",
            "category": "anxiety",
            "estimated_duration": 5,
            "difficulty_level": "beginner",
        },
        {
            "exercise_type": "grounding",
            "name": "5-4-3-2-1 Grounding",
            "description": "Sensory grounding technique to stay present and reduce dissociation",
            "instructions": "Notice: 5 things you see, 4 things you touch, 3 things you hear, 2 things you smell, 1 thing you taste",
            "category": "anxiety",
            "estimated_duration": 10,
            "difficulty_level": "beginner",
        },
        {
            "exercise_type": "body_scan",
            "name": "Progressive Body Scan",
            "description": "Mindfulness exercise for body awareness and tension release",
            "instructions": "Lie down and systematically notice sensations in each body part from toes to head",
            "category": "stress",
            "estimated_duration": 15,
            "difficulty_level": "beginner",
        },
        {
            "exercise_type": "gratitude",
            "name": "Gratitude Reflection",
            "description": "Write down things you're grateful for to boost positive mood",
            "instructions": "Write down 3-5 specific things you're grateful for today, no matter how small",
            "category": "depression",
            "estimated_duration": 10,
            "difficulty_level": "beginner",
        },
        {
            "exercise_type": "journaling",
            "name": "Emotion Journal",
            "description": "Write freely about your feelings and experiences",
            "instructions": "Spend 15-20 minutes writing whatever comes to mind about your emotions",
            "category": "stress",
            "estimated_duration": 20,
            "difficulty_level": "beginner",
        },
        {
            "exercise_type": "cognitive_reframing",
            "name": "Thought Challenge",
            "description": "Identify and reframe negative thought patterns using CBT techniques",
            "instructions": "Write a negative thought, identify evidence for/against it, write a more balanced thought",
            "category": "depression",
            "estimated_duration": 15,
            "difficulty_level": "intermediate",
        },
        {
            "exercise_type": "physical_activity",
            "name": "Movement Break",
            "description": "5-10 minute physical activity or stretch to boost mood",
            "instructions": "Go for a short walk, do yoga, stretch, or any movement that feels good",
            "category": "depression",
            "estimated_duration": 10,
            "difficulty_level": "beginner",
        },
        {
            "exercise_type": "self_compassion",
            "name": "Self-Compassion Practice",
            "description": "Speak to yourself with kindness and understanding",
            "instructions": "Place hand on heart, breathe deeply, repeat: 'This is difficult, I am doing my best'",
            "category": "shame",
            "estimated_duration": 5,
            "difficulty_level": "beginner",
        },
    ]

    for template in templates:
        try:
            create_exercise_template(**template)
        except Exception:
            pass

    _exercise_templates_initialized = True