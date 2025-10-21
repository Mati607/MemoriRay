"""
Memory management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from src.models.schemas.memory import Memory, MemoryCreate
from src.services.memory.memory_service import MemoryService

router = APIRouter()

@router.post("/", response_model=Memory)
async def create_memory(
    memory: MemoryCreate,
    user_id: str,  # In production, get from auth token
    memory_service: MemoryService = Depends()
):
    """Store a new positive memory"""
    return await memory_service.store_memory(user_id, memory)

@router.get("/recall", response_model=List[Memory])
async def recall_memories(
    mood_context: str,
    user_id: str,
    top_k: int = 5,
    memory_service: MemoryService = Depends()
):
    """Retrieve relevant memories based on mood"""
    return await memory_service.recall_memories(user_id, mood_context, top_k)

@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    user_id: str,
    memory_service: MemoryService = Depends()
):
    """Delete a memory"""
    success = await memory_service.delete_memory(user_id, memory_id)
    if not success:
        raise HTTPException(status_code=404, message="Memory not found")
    return {"status": "deleted"}
