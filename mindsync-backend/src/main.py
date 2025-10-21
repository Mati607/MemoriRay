
"""
MindSync Backend - Main Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import health, memory, conversation, user
from src.config.settings import get_settings
from src.core.database import init_db

settings = get_settings()

app = FastAPI(
    title="MindSync API",
    description="AI-powered mental health companion with memory recall",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(user.router, prefix="/api/v1/users", tags=["users"])
app.include_router(memory.router, prefix="/api/v1/memory", tags=["memory"])
app.include_router(conversation.router, prefix="/api/v1/conversation", tags=["conversation"])

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    await init_db()
    print("MindSync API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("MindSync API shutting down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
