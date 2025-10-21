"""
Vector Store - Manages ChromaDB/Pinecone operations
"""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any
from src.config.settings import get_settings

settings = get_settings()

class VectorStore:
    def __init__(self):
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=settings.CHROMA_PERSIST_DIR
        ))
        self.collection = self.client.get_or_create_collection(
            name="positive_memories",
            metadata={"description": "User positive memories for recall"}
        )
    
    async def add(
        self, 
        user_id: str, 
        content: str, 
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> str:
        """Add memory to vector store"""
        import uuid
        memory_id = str(uuid.uuid4())
        
        self.collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{**metadata, "user_id": user_id}]
        )
        
        return memory_id
    
    async def search(
        self,
        user_id: str,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Dict]:
        """Search for similar memories"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"user_id": user_id}
        )
        
        return results
    
    async def delete(self, user_id: str, memory_id: str) -> bool:
        """Delete a memory"""
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False
