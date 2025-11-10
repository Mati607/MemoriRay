"""
MindSync Backend Services

This package contains core services for the MindSync digital health platform:
- ConversationService: LLM-powered conversational interactions
"""

from .conversation_service import ConversationService

__all__ = ['ConversationService']
__version__ = '0.1.0'