"""
Memory Service - Handles memory storage and retrieval
"""
from typing import List, Optional
from src.services.memory.vector_store import VectorStore
from src.services.memory.embeddings import EmbeddingGenerator
from src.models.schemas.memory import Memory, MemoryCreate

class MemoryService:
    def __init__(self):
        self.vector_store = VectorStore()
        self.embedding_generator = EmbeddingGenerator()
    
    async def store_memory(self, user_id: str, memory: MemoryCreate) -> Memory:
        """Store a new positive memory"""
        # Generate embedding
        embedding = await self.embedding_generator.generate(memory.content)
        
        # Store in vector database
        memory_id = await self.vector_store.add(
            user_id=user_id,
            content=memory.content,
            embedding=embedding,
            metadata=memory.metadata
        )
        
        return Memory(id=memory_id, **memory.dict())
    
    async def recall_memories(
        self, 
        user_id: str, 
        mood_context: str, 
        top_k: int = 5
    ) -> List[Memory]:
        """Retrieve relevant positive memories based on current mood"""
        # Generate query embedding
        query_embedding = await self.embedding_generator.generate(mood_context)
        
        # Search vector store
        results = await self.vector_store.search(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=top_k
        )
        
        return results
    
    async def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Delete a memory"""
        return await self.vector_store.delete(user_id, memory_id)
