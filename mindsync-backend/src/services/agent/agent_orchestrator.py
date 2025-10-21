"""
Agent Orchestrator - Manages LLM and tool execution
"""
from typing import List, Dict, Any
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool
from src.services.agent.tools import MemoryRecallTool, MoodAnalysisTool
from src.config.settings import get_settings

settings = get_settings()

class AgentOrchestrator:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY
        )
        
        self.tools = [
            MemoryRecallTool(),
            MoodAnalysisTool()
        ]
        
        self.prompt = self._create_prompt()
        self.agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )
        
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True
        )
    
    def _create_prompt(self) -> ChatPromptTemplate:
        """Create system prompt for the agent"""
        return ChatPromptTemplate.from_messages([
            ("system", """You are MindSync, an empathetic AI mental health companion.

Your capabilities:
- You have access to the user's positive memories through the memory_recall tool
- You can detect emotional tone and offer support
- When the user seems down, you can retrieve and gently reference their happy memories

Guidelines:
- Be warm, validating, and non-judgmental
- If mood is low, consider using the memory_recall tool
- Integrate memories naturally into conversation
- Never force positivity; acknowledge their current feelings first
- Always respect user privacy and consent"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
    
    async def run(self, user_id: str, message: str, chat_history: List[Dict]) -> str:
        """Execute agent with user message"""
        result = await self.executor.ainvoke({
            "input": message,
            "chat_history": chat_history,
            "user_id": user_id
        })
        
        return result["output"]
