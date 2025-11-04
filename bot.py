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

if importlib.util.find_spec("baml_client") is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from baml_client import b as baml  # type: ignore

from fastapi.responses import HTMLResponse, Response


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str

class AddMemoryRequest(BaseModel):
    text: Optional[str] = None
    base_64_image: Optional[str] = None
    image_url: Optional[HttpUrl] = None


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

msg_history : list[str] = []

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="`message` must not be empty.")

    sentiment = await baml.SentimentAnalysis(req.message)
    reply_text = await baml.ChatReply(req.message, msg_history, sentiment)
    msg_history.append(req.message + " -> " + reply_text)
    return ChatResponse(reply=reply_text)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="127.0.0.1", port=8000, reload=True)


def convert_image_to_base64(image_url: HttpUrl) -> str:
    response = requests.get(str(image_url), timeout=15)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("utf-8")

memory_store : list[tuple[str, Optional[str]]] = []

def get_image_description(image_url: HttpUrl) -> str:
    response = requests.get(image_url)
    return response.text

def is_gibberish(text: str) -> bool:
    raise  NotImplementedError("Not implemented") # TODO: Implement this

@app.post("/add_memory", response_model=ChatResponse)
def add_memory(req: AddMemoryRequest):
    if req.base_64_image:
        if req.text:
            memory_store.append((req.text, req.base_64_image))
        else:
            description = get_image_description(req.base_64_image)
            memory_store.append((description,req.base_64_image))

    elif req.image_url:
        base_64_image = convert_image_to_base64(req.image_url)
        if req.text:
            memory_store.append((req.text, base_64_image))
        else:
            description = get_image_description(req.image_url)
            memory_store.append((description,req.image_url))
    elif req.text:
        memory_store.append((req.text,None)) 
    else:   
        return ChatResponse(reply="Memory addition failed")

    return ChatResponse(reply="Memory added successfully")

def get_memory(query: str) -> str:
    raise  NotImplementedError("Not implemented") # TODO: Implement this