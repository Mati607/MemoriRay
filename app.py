import os
import base64
import time
from typing import Dict, Any, List
import json

import requests
import streamlit as st

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
