"""
Application settings and configuration
"""
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "MindSync"
    DEBUG: bool = False
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/mindsync"
    
    # Vector Database
    VECTOR_DB_TYPE: str = "chromadb"  # chromadb, pinecone, qdrant
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    
    # LLM Configuration
    LLM_PROVIDER: str = "openai"  # openai, ollama, anthropic
    LLM_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: str = ""
    
    # Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    
    # Memory Service
    MAX_MEMORY_RECALL: int = 5
    MEMORY_RELEVANCE_THRESHOLD: float = 0.7
    
    # Safety
    ENABLE_SAFETY_MONITOR: bool = True
    CRISIS_DETECTION_THRESHOLD: float = 0.8
    
    class Config:
        env_file = ".env"

_settings = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
