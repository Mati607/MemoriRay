import os
import re
import base64
import time
from typing import Dict, Any, List
import json

import requests
import streamlit as st
import streamlit.components.v1 as components
from io import BytesIO
import textwrap
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
except Exception:
    # Report generation will surface a helpful error if dependency missing
    canvas = None
    letter = None
    colors = None
    SimpleDocTemplate = None
    Paragraph = None
    Spacer = None
    Table = None
    TableStyle = None
    ListFlowable = None
    ListItem = None
    getSampleStyleSheet = None
    ParagraphStyle = None

HISTORY_DIR = os.path.dirname(__file__)

def _history_path(user_id: int) -> str:
    return os.path.join(HISTORY_DIR, f"chat_history_{user_id}.json")

def load_saved_messages(user_id: int) -> List[Dict[str, Any]]:
    try:
        path = _history_path(user_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [m for m in data if isinstance(m, dict) and "role" in m and "content" in m]
    except Exception:
        pass
    return []

def save_messages(user_id: int, messages: List[Dict[str, Any]]) -> None:
    try:
        with open(_history_path(user_id), "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

st.set_page_config(
    page_title="MEMORIRAY - Mental Health Chat",
    page_icon="🌤️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      :root {
        --mh-bg: #FFFBEB;           /* warm, airy yellow (amber-50) */
        --mh-card: #FFF7D6;         /* soft card bg */
        --mh-ink: #3F3D2E;          /* cozy dark text */
        --mh-muted: rgba(63,61,46,.65);
        --mh-accent: #F4D06F;       /* honey yellow */
        --mh-accent-2: #9ED2C6;     /* calming teal */
        --mh-accent-3: #C7E9B0;     /* mint green */
        --mh-ring: rgba(244, 208, 111, .55);
        --mh-border: #F5E6A7;
      }

      html, body, [data-testid="stAppViewContainer"], .stApp {
        background: var(--mh-bg) !important;
        color: var(--mh-ink);
      }

      /* Background aura blobs */
      [data-testid="stAppViewContainer"]::before {
        content: ""; position: fixed; inset: -20% -10% auto -10%; height: 60vh;
        background: radial-gradient(40% 60% at 10% 10%, rgba(244,208,111,.30) 0%, rgba(244,208,111,0) 70%),
                    radial-gradient(40% 60% at 90% 10%, rgba(158,210,198,.28) 0%, rgba(158,210,198,0) 70%);
        pointer-events: none; z-index: 0;
      }

      /* Container width and spacing */
      .main .block-container {
        padding-top: 1.8rem;
        max-width: 760px;
      }

      /* Header */
      .hero {
        display: flex; align-items: center; gap: .8rem; margin-bottom: .25rem;
      }
      .hero .logo {
        width: 36px; height: 36px; border-radius: 10px;
        background: conic-gradient(from 180deg, var(--mh-accent), var(--mh-accent-2), var(--mh-accent));
        box-shadow: 0 6px 20px rgba(244,208,111,.35);
      }
      .app-title {
        font-size: 1.7rem; font-weight: 800; letter-spacing: .2px;
        background: linear-gradient(90deg, var(--mh-accent), var(--mh-accent-2));
        -webkit-background-clip: text; background-clip: text; color: transparent;
      }
      .subtle { color: var(--mh-muted); font-size: .95rem; margin-top: -4px; }

      /* Utility bar (clear/export) */
      .bar { display:flex; justify-content:flex-end; gap:.5rem; margin:.4rem 0 1rem 0; }
      .bar button[kind="secondary"] {
        border-radius: 999px !important;
        border: 1px solid var(--mh-border) !important;
        background: #FFF9D9 !important;
        box-shadow: 0 1px 0 rgba(0,0,0,.03), 0 8px 24px rgba(244,208,111,.12) !important;
      }

      /* Chat bubbles */
      .stChatMessage {
        border: 1px solid var(--mh-border);
        border-radius: 18px !important;
        padding: .75rem .9rem !important;
        background: var(--mh-card);
        box-shadow: 0 4px 14px rgba(0,0,0,.04);
        position: relative;
        z-index: 1;
      }
      .stChatMessage .stMarkdown p { line-height: 1.58 }
      /* user bubble */
      [data-testid="stChatMessage"] .stChatMessage[data-testid="stChatMessageUser"] {
        background: #FFF9D9 !important;
      }
      /* assistant bubble */
      [data-testid="stChatMessage"] .stChatMessage[data-testid="stChatMessageAssistant"] {
        background: #F7FFF9 !important;
      }

      /* Inputs */
      .stChatInputContainer, .stTextArea textarea {
        border-radius: 16px !important;
      }
      [data-testid="stChatInput"] textarea {
        background: #FFFDF3 !important;
        border: 1px solid var(--mh-border) !important;
        border-radius: 14px !important;
        box-shadow: 0 3px 12px rgba(0,0,0,.04);
      }
      [data-testid="stChatInput"] textarea:focus {
        box-shadow: 0 0 0 3px var(--mh-ring) !important;
        border-color: transparent !important;
      }
      [data-testid="stChatInput"] textarea::placeholder {
        color: rgba(63,61,46,.5);
      }

      /* Divider & footer */
      hr, .stDivider { border-color: var(--mh-border) !important; }
      .footer {
        color: var(--mh-muted); font-size: 12px; text-align: center; margin-top: 1rem;
      }

      /* Subtle entrance */
      @keyframes fadeUp { from { opacity: 0; transform: translateY(6px);} to { opacity: 1; transform: translateY(0);} }
      .stChatMessage { animation: fadeUp .25s ease both; }

      /* Scrollbar */
      ::-webkit-scrollbar { width: 10px; }
      ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, var(--mh-accent), var(--mh-accent-2));
        border-radius: 999px; border: 2px solid #fff2b8;
      }
      ::-webkit-scrollbar-track { background: #FFF7D6; }

      /* Auth form styling */
      .auth-container {
        max-width: 400px;
        margin: 2rem auto;
        padding: 2rem;
        background: var(--mh-card);
        border: 1px solid var(--mh-border);
        border-radius: 18px;
        box-shadow: 0 4px 14px rgba(0,0,0,.04);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Helper: get API base URL ───
def _api_base() -> str:
    return os.getenv("CHAT_API_BASE", "http://127.0.0.1:8000").rstrip("/")

def _current_user_id() -> int:
    return st.session_state["user_id"]

# ─── Auth API helpers ───
def call_register(username: str, password: str) -> Dict[str, Any]:
    r = requests.post(f"{_api_base()}/register", json={"username": username, "password": password}, timeout=15)
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(detail)
    return r.json()

def call_login(username: str, password: str) -> Dict[str, Any]:
    r = requests.post(f"{_api_base()}/login", json={"username": username, "password": password}, timeout=15)
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(detail)
    return r.json()

# ─── Chat / memory / contact / report API helpers (all include user_id) ───
def call_chat_api(message: str) -> Dict[str, Any]:
    url = f"{_api_base()}/chat"
    payload = {"message": message, "user_id": _current_user_id()}
    r = requests.post(url, json=payload, timeout=60)
    if not r.ok:
        raise RuntimeError(f"I'm having trouble connecting right now ({r.status_code}).")
    data = r.json()
    return {
        "reply": data.get("reply", "") or "",
        "images": data.get("images") or [],
    }

def call_add_memory(base_64_image: str) -> str:
    url = f"{_api_base()}/add_memory"
    payload = {"base_64_image": base_64_image, "user_id": _current_user_id()}
    r = requests.post(url, json=payload, timeout=60)
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"Upload failed ({r.status_code}). {detail}")
    return r.json().get("reply", "") or ""

def call_add_trusted_contact(emails: List[str]) -> str:
    url = f"{_api_base()}/add_trusted_contact"
    payload = {"email_list": emails, "user_id": _current_user_id()}
    r = requests.post(url, json=payload, timeout=60)
    if r.ok:
        return r.json().get("reply", "") or "Trusted contacts updated."
    raise RuntimeError(f"Add trusted contacts failed. {r.status_code} {r.text}")

def call_get_trusted_contacts() -> List[str]:
    url = f"{_api_base()}/get_trusted_contact"
    payload = {"user_id": _current_user_id()}
    try:
        r = requests.post(url, json=payload, timeout=60)
        if r.ok:
            data = r.json()
            reply = data.get("reply")
            if isinstance(reply, list):
                return [str(x) for x in reply]
            if isinstance(reply, str):
                try:
                    parsed = json.loads(reply)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed]
                except Exception:
                    return [reply]
    except Exception:
        pass
    return []

def call_generate_report() -> str:
    url = f"{_api_base()}/generate_report"
    r = requests.post(url, json={"user_id": _current_user_id()}, timeout=120)
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"Report generation failed ({r.status_code}). {detail}")
    return r.json().get("reply", "") or ""

def call_generate_report_structured() -> Dict[str, Any]:
    url = f"{_api_base()}/generate_report_structured"
    r = requests.post(url, json={"user_id": _current_user_id()}, timeout=120)
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"Report generation failed ({r.status_code}). {detail}")
    data = r.json() or {}
    if not isinstance(data, dict) or "report" not in data:
        raise RuntimeError("Malformed structured report response.")
    return data["report"]


def clinical_report_json_for_styled_html(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)


def normalize_llm_html_document(raw: str) -> str:
    s = (raw or "").strip()
    if not s.startswith("```"):
        return s
    s = re.sub(r"^```(?:html|HTML)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def call_generate_report_html(report: Dict[str, Any]) -> str:
    url = f"{_api_base()}/generate_report_html"
    r = requests.post(url, json={"report": report}, timeout=180)
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"HTML report generation failed ({r.status_code}). {detail}")
    data = r.json() or {}
    html = data.get("html", "")
    if not isinstance(html, str) or not html.strip():
        raise RuntimeError("Malformed HTML report response.")
    return normalize_llm_html_document(html)


def render_report_open_in_new_tab(html_document: str, *, component_key: str) -> None:
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", component_key) or "mr_report"
    b64 = base64.standard_b64encode(html_document.encode("utf-8")).decode("ascii")
    safe_b64 = json.dumps(b64)
    components.html(
        f"""
        <div style="font-family: system-ui, -apple-system, sans-serif; box-sizing:border-box;
          margin:0; padding:10px 10px 14px 10px; min-height:52px;
          border:1px solid rgba(63,61,46,.18); border-radius:12px;
          background:linear-gradient(180deg, rgba(255,253,244,.95), rgba(255,248,220,.6));
          box-shadow:inset 0 1px 0 rgba(255,255,255,.6);">
          <button type="button" id="mrOpen_{safe_id}"
            style="width:100%; box-sizing:border-box; cursor:pointer; border-radius:10px;
            border:1px solid rgba(63,61,46,.22); padding:0.6rem 0.95rem; font-size:0.95rem; font-weight:600;
            background:linear-gradient(180deg,#fff9e6,#fff3cc); color:#3f3d2e;
            box-shadow:0 2px 6px rgba(244,208,111,.22), 0 1px 0 rgba(255,255,255,.8) inset;">
            View report in new tab
          </button>
        </div>
        <script>
        (function() {{
          const b64 = {safe_b64};
          const btn = document.getElementById("mrOpen_{safe_id}");
          if (!btn) return;
          btn.addEventListener("click", function () {{
            try {{
              const bin = atob(b64);
              const bytes = new Uint8Array(bin.length);
              for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
              const blob = new Blob([bytes], {{ type: "text/html;charset=utf-8" }});
              const url = URL.createObjectURL(blob);
              window.open(url, "_blank", "noopener,noreferrer");
              setTimeout(function () {{ URL.revokeObjectURL(url); }}, 120000);
            }} catch (e) {{
              console.error(e);
              alert("Could not open the report in a new tab.");
            }}
          }});
        }})();
        </script>
        """,
        height=96,
    )


def build_report_pdf(report_text: str) -> bytes:
    if canvas is None or letter is None:
        raise RuntimeError("PDF generation dependency missing. Please install 'reportlab'.")
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 72  # 1 inch
    y = height - margin
    c.setFont("Helvetica", 12)
    lines: List[str] = []
    for paragraph in (report_text or "").splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        wrapped = textwrap.wrap(paragraph, width=90)
        lines.extend(wrapped if wrapped else [""])
    for line in lines:
        if y < margin:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = height - margin
        c.drawString(margin, y, line)
        y -= 14
    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def build_structured_report_pdf(report: Dict[str, Any]) -> bytes:
    if SimpleDocTemplate is None or letter is None:
        raise RuntimeError("PDF generation dependency missing. Please install 'reportlab'.")
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=56,
        leftMargin=56,
        topMargin=56,
        bottomMargin=56,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        textColor=colors.HexColor("#3F3D2E"),
        fontSize=20,
        leading=24,
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#3F3D2E"),
        fontSize=13,
        leading=16,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["BodyText"],
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#3F3D2E"),
    )
    subtle_style = ParagraphStyle(
        "Subtle",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#5d5a44"),
    )

    def risk_color(level: str):
        mapping = {
            "NONE": colors.HexColor("#0f766e"),
            "LOW": colors.HexColor("#16a34a"),
            "MODERATE": colors.HexColor("#f59e0b"),
            "HIGH": colors.HexColor("#ef4444"),
            "EMERGENCY": colors.HexColor("#991b1b"),
        }
        return mapping.get((level or "").upper(), colors.HexColor("#3F3D2E"))

    story: list[Any] = []
    story.append(Paragraph("Clinical Summary Report", title_style))
    story.append(Spacer(1, 6))

    rl = str(report.get("risk_level") or "").upper()
    risk_label = f"Risk Level: {rl or 'UNKNOWN'}"
    risk_bg = risk_color(rl)
    risk_tbl = Table([[risk_label]], style=[
        ("BACKGROUND", (0, 0), (-1, -1), risk_bg),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("INNERPADDING", (0, 0), (-1, -1), 6),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), 4),
    ])
    story.append(risk_tbl)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Overall Assessment", section_style))
    story.append(Paragraph(report.get("overall_assessment", "") or "\u2014", body_style))

    kc = report.get("key_concerns") or []
    if kc:
        story.append(Paragraph("Key Concerns", section_style))
        story.append(ListFlowable(
            [ListItem(Paragraph(str(item), body_style), leftIndent=6) for item in kc],
            bulletType="bullet", start=None, bulletFontName="Helvetica", bulletFontSize=8,
        ))

    symptoms = report.get("symptoms") or []
    if symptoms:
        story.append(Paragraph("Symptoms", section_style))
        for s in symptoms:
            name = str(s.get("name") or "").strip()
            desc = str(s.get("description") or "").strip()
            ev = s.get("evidence_from_messages") or []
            if name:
                story.append(Paragraph(f"<b>{name}</b>", body_style))
            if desc:
                story.append(Paragraph(desc, subtle_style))
            if ev:
                story.append(ListFlowable(
                    [ListItem(Paragraph(str(e), subtle_style), leftIndent=12) for e in ev],
                    bulletType="bullet", start=None, bulletFontName="Helvetica", bulletFontSize=7,
                ))
            story.append(Spacer(1, 6))

    pf = report.get("protective_factors") or []
    if pf:
        story.append(Paragraph("Protective Factors", section_style))
        story.append(ListFlowable(
            [ListItem(Paragraph(str(item), body_style), leftIndent=6) for item in pf],
            bulletType="bullet", start=None, bulletFontName="Helvetica", bulletFontSize=8,
        ))

    fi = report.get("functional_impact", "") or ""
    if fi.strip():
        story.append(Paragraph("Functional Impact", section_style))
        story.append(Paragraph(fi, body_style))

    rcf = report.get("recommended_clinical_focus", "") or ""
    if rcf.strip():
        story.append(Paragraph("Recommended Clinical Focus", section_style))
        story.append(Paragraph(rcf, body_style))

    lim = report.get("limitations", "") or ""
    if lim.strip():
        story.append(Paragraph("Limitations", section_style))
        story.append(Paragraph(lim, subtle_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ═══════════════════════════════════════════════════════════
# AUTH GATE — show login/register if not authenticated
# ═══════════════════════════════════════════════════════════

def show_auth_page():
    st.markdown(
        """
        <div class="hero">
          <div class="logo"></div>
          <div class="app-title">MEMORIRAY</div>
        </div>
        <div class="subtle">A gentle space to reflect, feel, and be heard.</div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                if not username.strip() or not password:
                    st.error("Please enter both username and password.")
                else:
                    try:
                        data = call_login(username.strip(), password)
                        st.session_state["user_id"] = data["user_id"]
                        st.session_state["username"] = data["username"]
                        st.rerun()
                    except RuntimeError as e:
                        st.error(str(e))

    with tab_register:
        with st.form("register_form"):
            new_user = st.text_input("Choose a username")
            new_pass = st.text_input("Choose a password", type="password")
            confirm_pass = st.text_input("Confirm password", type="password")
            submitted_reg = st.form_submit_button("Create account")
            if submitted_reg:
                if not new_user.strip() or not new_pass:
                    st.error("Please fill in all fields.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match.")
                elif len(new_pass) < 4:
                    st.error("Password must be at least 4 characters.")
                else:
                    try:
                        data = call_register(new_user.strip(), new_pass)
                        st.session_state["user_id"] = data["user_id"]
                        st.session_state["username"] = data["username"]
                        st.rerun()
                    except RuntimeError as e:
                        st.error(str(e))

    st.markdown(
        '<div class="footer">This is a supportive tool and not a substitute for professional care.</div>',
        unsafe_allow_html=True,
    )


def show_chat_page():
    user_id = _current_user_id()
    username = st.session_state.get("username", "")

    st.markdown(
        f"""
        <div class="hero">
          <div class="logo"></div>
          <div class="app-title">MEMORIRAY</div>
        </div>
        <div class="subtle">Welcome back, <strong>{username}</strong></div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    col_clear, col_export, col_logout = st.columns([1, 1, 1])
    with col_clear:
        if st.button("🧹 Clear"):
            st.session_state.pop("messages", None)
            st.session_state.pop("report_html", None)
            st.session_state.pop("report_pdf_bytes", None)
            st.session_state.pop("report_filename", None)
            try:
                path = _history_path(user_id)
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
            st.rerun()
    with col_export:
        download_ready = st.session_state.get("messages", [])
        if download_ready:
            transcript = ""
            for m in download_ready:
                role = "You" if m["role"] == "user" else "Guide"
                transcript += f"{role}: {m['content']}\n"
            st.download_button(
                "Export",
                data=transcript.encode("utf-8"),
                file_name="solace_chat.txt",
                mime="text/plain",
            )
    with col_logout:
        if st.button("Logout"):
            for key in ["user_id", "username", "messages", "report_html", "report_pdf_bytes", "report_filename"]:
                st.session_state.pop(key, None)
            st.rerun()

    if "messages" not in st.session_state:
        saved = load_saved_messages(user_id)
        if saved:
            st.session_state.messages = saved
        else:
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": (
                        f"Hi {username} \u2014 I'm here with a calm, supportive ear. "
                        "How are you feeling right now?"
                    ),
                }
            ]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ─── Sidebar ───
    if "attach_uploader_key" not in st.session_state:
        st.session_state.attach_uploader_key = 0

    with st.sidebar:
        st.markdown(f"**Logged in as** `{username}`")
        st.divider()
        st.markdown("**Attach Memories**")
        st.caption("Add an image to your memory vault")
        with st.form("attach_image_form", border=True):
            uploaded = st.file_uploader(
                "Upload image(s)",
                type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True,
                key=f"attach_uploader_{st.session_state.attach_uploader_key}",
            )
            submitted = st.form_submit_button("Add to memory")
            if submitted:
                if not uploaded:
                    st.warning("Please select one or more images.")
                else:
                    results = st.container()
                    total = len(uploaded)
                    for idx, uf in enumerate(uploaded, start=1):
                        try:
                            file_bytes = uf.getvalue()
                            b64_str = base64.b64encode(file_bytes).decode("utf-8")
                            with st.spinner(f"Uploading and processing image {idx} of {total}..."):
                                resp = call_add_memory(b64_str)
                            results.success(resp or f"{uf.name}: Memory added successfully")
                        except Exception as e:
                            results.error(f"{uf.name}: {e}")

        st.divider()
        st.markdown("**Trusted Contacts**")
        st.caption("People to reach out to if you're in crisis.")
        try:
            _existing_contacts = call_get_trusted_contacts()
        except Exception:
            _existing_contacts = []
        if _existing_contacts:
            st.caption("Saved contacts:")
            for em in _existing_contacts:
                st.markdown(f"- {em}")
        with st.form("trusted_contacts_form", border=True):
            emails_input = st.text_input(
                "Add Trusted Contact(s)",
                placeholder="alice@example.com, bob@example.com",
                help="Separate multiple emails with commas",
            )
            submitted_tc = st.form_submit_button("Save contacts")
            if submitted_tc:
                emails = [e.strip() for e in emails_input.split(",") if e.strip()]
                if not emails:
                    st.warning("Please enter at least one valid email.")
                else:
                    try:
                        resp = call_add_trusted_contact(emails)
                        st.success(resp or "Trusted contacts saved.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        st.divider()
        st.markdown("**Report**")
        st.caption(
            "Creates an AI-styled, self-contained HTML summary. "
            "Use **View report** to open it in a new tab."
        )
        col_gen, col_view = st.columns([1, 1])
        with col_gen:
            if st.button("Generate report"):
                try:
                    with st.spinner("Summarizing conversation and designing HTML report..."):
                        structured: Dict[str, Any] | None = None
                        try:
                            structured = call_generate_report_structured()
                        except Exception:
                            structured = None
                        if not structured:
                            report_text = call_generate_report()
                            if not (report_text or "").strip():
                                st.warning("No report content available.")
                            else:
                                structured = {
                                    "overall_assessment": report_text,
                                    "risk_level": "NONE",
                                    "key_concerns": [],
                                    "symptoms": [],
                                    "protective_factors": [],
                                    "functional_impact": "",
                                    "recommended_clinical_focus": "",
                                    "limitations": "",
                                }
                        if structured:
                            payload = clinical_report_json_for_styled_html(structured)
                            if not payload.strip():
                                st.warning("No report content available.")
                            else:
                                html_doc = call_generate_report_html(structured)
                                st.session_state["report_html"] = html_doc
                                st.session_state.pop("report_pdf_bytes", None)
                                st.session_state.pop("report_filename", None)
                                st.success("Report ready \u2014 click **View report**.")
                except Exception as e:
                    st.error(str(e))
        with col_view:
            html_for_view = st.session_state.get("report_html")
            if html_for_view:
                st.caption("Opens in a **new tab** (allow pop-ups if the browser blocks them).")
                render_report_open_in_new_tab(html_for_view, component_key="memori_report_html")

    # ─── Chat input ───
    prompt = st.chat_input("Share what's on your mind...")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_messages(user_id, st.session_state.messages)
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            reply_placeholder = st.empty()
            try:
                api_result = call_chat_api(prompt)
                reply_text = api_result.get("reply", "")
                images = api_result.get("images", []) or []
                shown = ""
                for ch in reply_text:
                    shown += ch
                    reply_placeholder.markdown(shown)
                    time.sleep(0.002)
                if images:
                    for img_b64 in images:
                        try:
                            img_bytes = base64.b64decode(img_b64)
                            st.image(img_bytes, use_container_width=False)
                        except Exception:
                            pass
            except Exception:
                gentle_msg = (
                    "I'm feeling a bit disconnected right now. "
                    "Let's try again in a moment."
                )
                st.info(gentle_msg)
                reply_text = gentle_msg
                reply_placeholder.markdown(reply_text)

        st.session_state.messages.append({"role": "assistant", "content": reply_text})
        save_messages(user_id, st.session_state.messages)

    st.markdown(
        '<div class="footer">This is a supportive tool and not a substitute for professional care. '
        "If you're in immediate danger or crisis, please contact local emergency services or a crisis hotline in your region.</div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════
# MAIN ROUTING
# ═══════════════════════════════════════════════════════════

if "user_id" not in st.session_state:
    show_auth_page()
else:
    show_chat_page()
