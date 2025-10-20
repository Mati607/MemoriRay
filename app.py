import os
import time
from typing import Optional

import streamlit as st
from PIL import Image

from memory_store import MemoryStore
from llm import generate_response


DATA_DIR = os.path.join(os.getcwd(), "data")
INDEX_PATH = os.path.join(DATA_DIR, "faiss.index")
META_PATH = os.path.join(DATA_DIR, "metadata.json")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")


@st.cache_resource(show_spinner=True)
def get_store() -> MemoryStore:
	os.makedirs(DATA_DIR, exist_ok=True)
	os.makedirs(UPLOAD_DIR, exist_ok=True)
	return MemoryStore(index_path=INDEX_PATH, metadata_path=META_PATH)


def save_uploaded_image(upload, prefix: Optional[str] = None) -> Optional[str]:
	if upload is None:
		return None
	try:
		name = upload.name or "image"
		stamp = int(time.time())
		base = f"{prefix or 'mem'}_{stamp}_{name}"
		path = os.path.join(UPLOAD_DIR, base)
		image = Image.open(upload)
		image.save(path)
		return path
	except Exception:
		return None


def render_memory_card(text: str, image_path: Optional[str]) -> None:
	st.markdown(f"**Memory:** {text}")
	if image_path and os.path.exists(image_path):
		st.image(image_path, use_column_width=True)


st.set_page_config(page_title="MemoriRay - Positive Memory Companion", page_icon="🧠")
st.title("MemoriRay 🧠")
st.caption("A minimal local prototype: upload positive memories and gently recall them when needed.")

# Guarded store initialization with spinner
store = None
store_error = None
with st.spinner("Loading embeddings model (first run may take a few minutes)..."):
	try:
		store = get_store()
	except Exception as e:
		store_error = str(e)

if store_error:
	st.error(f"Memory store failed to initialize: {store_error}")
	st.info("Tip: For first-time setup, ensure internet access to download 'all-MiniLM-L6-v2'. After it downloads once, the app works offline. If you prefer offline-only, pre-download the model into your Hugging Face cache and restart.")

add_tab, chat_tab, browse_tab = st.tabs(["Add Memory", "Chat", "Browse Memories"]) 

with add_tab:
	st.subheader("Add a positive memory")
	if store is None:
		st.info("Memory store is loading or unavailable. Please wait or check the error above.")
	with st.form("add_memory_form"):
		text = st.text_area("Describe your memory (what happened, who was there, how you felt)", height=120)
		image = st.file_uploader("Optional: attach a photo", type=["png", "jpg", "jpeg", "webp"])
		submitted = st.form_submit_button("Save memory")
		if submitted:
			if store is None:
				st.warning("Storage not ready yet. Try again in a moment.")
			elif not (text or image is not None):
				st.warning("Please write a short description or attach a photo.")
			else:
				img_path = save_uploaded_image(image, prefix="memory") if image is not None else None
				try:
					caption = text.strip() if (text and text.strip()) else "A positive moment I want to remember."
					mid = store.add_memory(text=caption, image_path=img_path)
					st.success("Saved! This memory can now be recalled during chats.")
					st.toast(f"Added memory #{mid}")
				except Exception as e:
					st.error(f"Could not save memory: {e}")

with chat_tab:
	st.subheader("Chat")
	st.markdown("Share how you're feeling. I'll gently bring up your positive memories.")
	user_msg = st.text_input("Message", placeholder="I'm feeling low today…")
	col1, col2 = st.columns([1, 2])
	with col1:
		k = st.slider("Memories to recall", min_value=1, max_value=8, value=3)
	with col2:
		model = st.text_input("Ollama model (local)", value="llama3.2", help="Requires Ollama running locally; otherwise a simple fallback is used.")

	if st.button("Send"):
		if not user_msg.strip():
			st.warning("Type a message first.")
		elif store is None:
			st.warning("Storage not ready yet. Try again in a moment.")
		else:
			with st.spinner("Recalling helpful moments…"):
				results = store.search(user_msg, k=k)
				if results:
					st.markdown("**Memories I found:**")
					for (meta, score) in results:
						with st.expander(meta.get("text", "(no text)")):
							render_memory_card(meta.get("text", ""), meta.get("image_path"))
				response = generate_response(user_msg, results, model=model)
				st.markdown("**Assistant**:")
				st.write(response)

with browse_tab:
	st.subheader("All memories")
	if store is None:
		st.info("Storage is still loading or unavailable.")
	else:
		mems = store.all_memories()
		if not mems:
			st.info("No memories yet. Add one in the 'Add Memory' tab.")
		else:
			for m in mems:
				st.markdown("---")
				render_memory_card(m.get("text", ""), m.get("image_path"))
