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


