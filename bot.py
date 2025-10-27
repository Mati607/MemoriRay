import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai


DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

from fastapi.responses import HTMLResponse, Response


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="`message` must not be empty.")

    client: genai.Client = app.state.genai_client
    model_name = (req.model or DEFAULT_MODEL).strip()

    try:
        resp = client.models.generate_content(
            model=model_name,
            contents=req.message,
        )
        reply_text = getattr(resp, "text", "") or ""
        return ChatResponse(reply=reply_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="127.0.0.1", port=8000, reload=True)
