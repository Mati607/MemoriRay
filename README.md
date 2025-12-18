# MEMORIRAY

A minimal mental-health chat app with a Streamlit frontend and a FastAPI backend powered by Google's Gemini (via `google-genai`).

## Prerequisites

- Python 3.10+
- Poetry
- Google API key for Gemini

## Install dependencies

```bash
poetry install
poetry env activate
```

## Environment

Create `.env` in the project root:

```env
GOOGLE_API_KEY=your_google_api_key
```

## Run the backend (FastAPI)

```
baml-cli generate
```

```bash
poetry run python bot.py
```

## Run the frontend (Streamlit)

```bash
poetry run streamlit run app.py
```

Open the app at `http://localhost:8501`.

## How to run the full app (end‑to‑end)

1. **Generate BAML client code** (only needed when you change `.baml` files):

   ```bash
   baml-cli generate
   ```

2. **Start the backend** (FastAPI) in one terminal:

   ```bash
   poetry run python bot.py
   ```

3. **Start the frontend** (Streamlit) in a second terminal:

   ```bash
   poetry run streamlit run app.py
   ```

4. **Use the app** by visiting `http://localhost:8501` in your browser and chatting with the assistant.

## Project structure overview

- `app.py` **(Streamlit frontend)**: Renders the chat UI, sends user messages to the backend, and displays responses and memory-related content.
- `bot.py` **(FastAPI backend)**: Exposes HTTP endpoints used by the frontend, orchestrates calls to Gemini via BAML, manages memories/trusted contacts, and generates clinical-style summaries.
- `baml_src/` **(BAML definitions)**: Contains `.baml` files that define the LLM-powered tools, prompts, and agents used by the backend.
- `baml_client/` **(Generated BAML client)**: Auto-generated Python client code produced by `baml-cli generate`, used by `bot.py` to call the BAML-defined flows.
- `memories/` **(sample memory assets)**: Example images and media used for positive memory recall and testing memory-related features.
- `mindsync-backend/` **(full backend service)**: A more complete backend for persistence and advanced features (API routes in `src/api/`, services in `src/services/`, models in `src/models/`, etc.); see its own `README.md` for details.
- `chat_history.json` **(local chat log)**: Stores recent chat history for the simple app, useful for debugging and experimentation.
- `i2c.py` **(image-to-JSON helper)**: Utility script that converts an image into a base64-encoded JSON payload suitable for memory ingestion APIs.
