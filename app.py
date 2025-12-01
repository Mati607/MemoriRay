import os
import base64
import time
from typing import Dict, Any, List
import json

import requests
import streamlit as st
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

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "chat_history.json")

def load_saved_messages() -> List[Dict[str, Any]]:
    try:
        if os.path.exists(HISTORY_PATH):
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [m for m in data if isinstance(m, dict) and "role" in m and "content" in m]
    except Exception:
        pass
    return []

def save_messages(messages: List[Dict[str, Any]]) -> None:
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

st.set_page_config(
    page_title="MEMORIRAY · Mental Health Chat",
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
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <div class="logo"></div>
      <div class="app-title">MEMORIRAY · Mental Health Chat</div>
    </div>
    <div class="subtle">A gentle space to reflect, feel, and be heard.</div>
    """,
    unsafe_allow_html=True,
)
st.divider()

col_clear, col_export = st.columns([1,1])
with col_clear:
    if st.button("🧹 Clear"):
        st.session_state.pop("messages", None)
        try:
            if os.path.exists(HISTORY_PATH):
                os.remove(HISTORY_PATH)
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
            "⬇️ Export",
            data=transcript.encode("utf-8"),
            file_name="solace_chat.txt",
            mime="text/plain",
        )

if "messages" not in st.session_state:
    saved = load_saved_messages()
    if saved:
        st.session_state.messages = saved
    else:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Hi—I'm here with a calm, supportive ear. "
                    "How are you feeling right now? 🌱"
                ),
            }
        ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

def call_chat_api(message: str) -> Dict[str, Any]:
    base = os.getenv("CHAT_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    url = f"{base}/chat"
    payload = {"message": message}
    r = requests.post(url, json=payload, timeout=60)
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"I'm having trouble connecting right now ({r.status_code}).")
    data = r.json()
    return {
        "reply": data.get("reply", "") or "",
        "images": data.get("images") or [],
    }

def call_add_memory(base_64_image: str) -> str:
    base = os.getenv("CHAT_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    url = f"{base}/add_memory"
    payload = {"base_64_image": base_64_image}
    r = requests.post(url, json=payload, timeout=60)
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"Upload failed ({r.status_code}). {detail}")
    data = r.json()
    return data.get("reply", "") or ""

def call_add_trusted_contact(emails: List[str]) -> str:
    base = os.getenv("CHAT_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    # Try with and without leading slash since backend route may be defined without it
    paths = ["/add_trusted_contact", "add_trusted_contact"]
    payload = {"email_list": emails}
    last_error = None
    for path in paths:
        url = f"{base}/{path.lstrip('/')}"
        try:
            r = requests.post(url, json=payload, timeout=60)
            if r.ok:
                data = r.json()
                return data.get("reply", "") or "Trusted contacts updated."
            last_error = f"{r.status_code} {r.text}"
        except Exception as e:
            last_error = str(e)
    raise RuntimeError(f"Add trusted contacts failed. {last_error or ''}")

def call_get_trusted_contacts() -> List[str]:
    base = os.getenv("CHAT_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    paths = ["/get_trusted_contact", "get_trusted_contact"]
    last_error = None
    for path in paths:
        url = f"{base}/{path.lstrip('/')}"
        try:
            r = requests.post(url, timeout=60)
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
            last_error = f"{r.status_code} {r.text}"
        except Exception as e:
            last_error = str(e)
    return []

def call_generate_report() -> str:
    base = os.getenv("CHAT_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    url = f"{base}/generate_report"
    r = requests.post(url, timeout=120)
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"Report generation failed ({r.status_code}). {detail}")
    data = r.json()
    return data.get("reply", "") or ""

def call_generate_report_structured() -> Dict[str, Any]:
    base = os.getenv("CHAT_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    url = f"{base}/generate_report_structured"
    r = requests.post(url, timeout=120)
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

def build_report_pdf(report_text: str) -> bytes:
    if canvas is None or letter is None:
        raise RuntimeError("PDF generation dependency missing. Please install 'reportlab'.")
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 72  # 1 inch
    y = height - margin
    c.setFont("Helvetica", 12)
    # Basic word wrap
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
    # Custom styles
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
    # Title
    story.append(Paragraph("Clinical Summary Report", title_style))
    story.append(Spacer(1, 6))

    # Risk badge
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

    # Overall assessment
    story.append(Paragraph("Overall Assessment", section_style))
    story.append(Paragraph(report.get("overall_assessment", "") or "—", body_style))

    # Key concerns
    kc = report.get("key_concerns") or []
    if kc:
        story.append(Paragraph("Key Concerns", section_style))
        story.append(ListFlowable(
            [ListItem(Paragraph(str(item), body_style), leftIndent=6) for item in kc],
            bulletType="bullet",
            start=None,
            bulletFontName="Helvetica",
            bulletFontSize=8,
        ))

    # Symptoms
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
                    bulletType="bullet",
                    start=None,
                    bulletFontName="Helvetica",
                    bulletFontSize=7,
                ))
            story.append(Spacer(1, 6))

    # Protective factors
    pf = report.get("protective_factors") or []
    if pf:
        story.append(Paragraph("Protective Factors", section_style))
        story.append(ListFlowable(
            [ListItem(Paragraph(str(item), body_style), leftIndent=6) for item in pf],
            bulletType="bullet",
            start=None,
            bulletFontName="Helvetica",
            bulletFontSize=8,
        ))

    # Functional impact
    fi = report.get("functional_impact", "") or ""
    if fi.strip():
        story.append(Paragraph("Functional Impact", section_style))
        story.append(Paragraph(fi, body_style))

    # Recommended focus
    rcf = report.get("recommended_clinical_focus", "") or ""
    if rcf.strip():
        story.append(Paragraph("Recommended Clinical Focus", section_style))
        story.append(Paragraph(rcf, body_style))

    # Limitations
    lim = report.get("limitations", "") or ""
    if lim.strip():
        story.append(Paragraph("Limitations", section_style))
        story.append(Paragraph(lim, subtle_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

if "attach_uploader_key" not in st.session_state:
    st.session_state.attach_uploader_key = 0

with st.sidebar:
    st.markdown("**📎 Attach Memories**")
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
                        with st.spinner(f"Uploading and processing image {idx} of {total}…"):
                            resp = call_add_memory(b64_str)
                        results.success(resp or f"{uf.name}: Memory added successfully")
                    except Exception as e:
                        results.error(f"{uf.name}: {e}")

    st.divider()
    st.markdown("**👥 Trusted Contacts**")
    st.caption("People to reach out to if you're in crisis.")
    # Display currently saved contacts
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
    st.markdown("**📄 Report**")
    # Persist the last generated PDF for download across reruns
    report_pdf_bytes = st.session_state.get("report_pdf_bytes")
    report_filename = st.session_state.get("report_filename", "memori_report.pdf")
    col_gen, col_dl = st.columns([1,1])
    with col_gen:
        if st.button("Generate Report (PDF)"):
            try:
                with st.spinner("Generating report…"):
                    pdf_bytes: bytes | None = None
                    try:
                        structured = call_generate_report_structured()
                        if structured and isinstance(structured, dict):
                            pdf_bytes = build_structured_report_pdf(structured)
                            # Create filename hint with risk level if present
                            rl = str(structured.get("risk_level") or "").upper()
                            if rl:
                                st.session_state["report_filename"] = f"memori_report_{rl.lower()}.pdf"
                    except Exception:
                        # Fallback to text-only version if structured endpoint fails
                        report_text = call_generate_report()
                        if report_text.strip():
                            pdf_bytes = build_report_pdf(report_text)
                    if not pdf_bytes:
                        st.warning("No report content available.")
                    else:
                        st.session_state["report_pdf_bytes"] = pdf_bytes
                        st.session_state["report_filename"] = st.session_state.get("report_filename", report_filename)
                        st.success("Report ready below.")
            except Exception as e:
                st.error(str(e))
    with col_dl:
        if report_pdf_bytes:
            st.download_button(
                "⬇️ Download",
                data=report_pdf_bytes,
                file_name=report_filename,
                mime="application/pdf",
                use_container_width=True,
            )

prompt = st.chat_input("Share what's on your mind…")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_messages(st.session_state.messages)
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
                "I’m feeling a bit disconnected right now. "
                "Let’s try again in a moment."
            )
            st.info(gentle_msg)
            reply_text = gentle_msg
            reply_placeholder.markdown(reply_text)

    st.session_state.messages.append({"role": "assistant", "content": reply_text})
    save_messages(st.session_state.messages)

st.markdown(
    '<div class="footer">This is a supportive tool and not a substitute for professional care. '
    'If you’re in immediate danger or crisis, please contact local emergency services or a crisis hotline in your region.</div>',
    unsafe_allow_html=True,
)
