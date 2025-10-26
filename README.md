# MemoriRay (Local RAG Prototype)

A minimal, fully local prototype for a supportive mental health companion:
- Upload positive memories (text + optional photo)
- Stores embeddings locally with FAISS
- Recalls helpful memories during chats using a local LLM (via Ollama) or a simple fallback

## Tech Choices (Free & Local)
- Frontend: Streamlit
- Embeddings: `sentence-transformers` (`all-MiniLM-L6-v2`)
- Vector search: FAISS (persisted to `data/`)
- LLM: [Ollama](https://ollama.com) (optional).

## Setup
1) Python 3.10+
2) Optional but recommended: Install Ollama and pull a model:
   ```bash
   brew install ollama
   ollama serve &
   ollama pull llama3.2
   ```

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `faiss-cpu` fails on your platform, try:
```bash
pip install faiss-cpu==1.7.4
```

## Run
```bash
streamlit run app.py
```
Then open the local URL shown in the terminal.

## Run the CLI chat bot (Poetry)
This repo already contains `pyproject.toml`, so you can install and run with Poetry directly.

1) Install Poetry (one of):
```bash
brew install poetry            # macOS
# or
pipx install poetry
```

2) Install dependencies:
```bash
poetry install
```

3) Run the bot:
```bash
poetry run python bot.py
```

Notes:
- On Apple Silicon, PyTorch may use `mps` (Metal) automatically if available; otherwise CPU is used.
- If you were starting a brand-new project without `pyproject.toml`, you would first run `poetry init` to create it (not needed here).

## How it works
- Memories are embedded with `all-MiniLM-L6-v2` and added to a cosine-similarity FAISS index.
- On chat, your message is embedded and used to retrieve top-k memories; we prompt a local LLM (Ollama) to weave them into a gentle response. If Ollama isn’t running, a template-based fallback reply is used.
- All data (index, metadata, uploads) is stored under `data/`.

## Notes
- This is a classroom prototype, not medical advice.
- Keep image sizes modest to save disk and memory.
- Everything runs locally; no paid API keys required.
