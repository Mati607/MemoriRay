"""
Conversation endpoints
"""
from fastapi import APIRouter, Depends, WebSocket
from src.services.agent.agent_orchestrator import AgentOrchestrator
from src.models.schemas.conversation import ConversationMessage, ConversationResponse

router = APIRouter()

@router.post("/message", response_model=ConversationResponse)
async def send_message(
    message: ConversationMessage,
    user_id: str,
    agent: AgentOrchestrator = Depends()
):
    """Send message to agent"""
    response = await agent.run(
        user_id=user_id,
        message=message.content,
        chat_history=message.history or []
    )
    
    return ConversationResponse(content=response)

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time chat"""
    await websocket.accept()
    agent = AgentOrchestrator()
    
    try:
        while True:
            data = await websocket.receive_text()
            response = await agent.run(user_id, data, [])
            await websocket.send_text(response)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()
