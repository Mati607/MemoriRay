"""
Create a conversation service in the mindsync-backend that talks with users.
Uses free Large Language Models via Groq API.
"""

import os
from typing import List, Dict, Optional
from groq import Groq

import dotenv


class ConversationService:
    """
    Service for handling conversational interactions using free LLMs.
    
    Supports multiple free models via Groq:
    - llama-3.1-8b-instant
    - mixtral-8x7b-32768
    - gemma2-9b-it
    """
    
    def __init__(self, model_name: str = "llama-3.1-8b-instant"):
        """
        Initialize the conversation service.
        
        Args:
            model_name: Name of the LLM model to use
        """
        self.model_name = model_name
        self.api_key = os.getenv("GROQ_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY not found in environment variables. "
                "Get a free API key at https://console.groq.com"
            )
        
        self.client = Groq(api_key=self.api_key)
        self.conversation_history: List[Dict[str, str]] = []
    
    def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False
    ) -> str:
        """
        Send a message and get a response from the LLM.
        
        Args:
            user_message: The user's input message
            system_prompt: Optional system prompt to guide the model's behavior
            temperature: Controls randomness (0.0-2.0). Lower = more focused
            max_tokens: Maximum tokens in the response
            stream: Whether to stream the response (returns generator if True)
        
        Returns:
            The model's response as a string (or generator if stream=True)
        """
        # Build messages list
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add conversation history
        messages.extend(self.conversation_history)
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Call the API
        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            if stream:
                return self._handle_stream(chat_completion, user_message)
            else:
                response_content = chat_completion.choices[0].message.content
                
                # Update conversation history
                self.conversation_history.append({
                    "role": "user",
                    "content": user_message
                })
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response_content
                })
                
                return response_content
                
        except Exception as e:
            raise Exception(f"Error calling LLM: {str(e)}")
    
    def _handle_stream(self, stream, user_message: str):
        """Handle streaming responses."""
        full_response = ""
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content
        
        # Update history after streaming completes
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": full_response
        })
    
    def clear_history(self):
        """Clear the conversation history."""
        self.conversation_history = []
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get the current conversation history."""
        return self.conversation_history.copy()
    
    def set_history(self, history: List[Dict[str, str]]):
        """Set the conversation history (useful for loading saved conversations)."""
        self.conversation_history = history


# Example usage for your digital health project
if __name__ == "__main__":
    # Initialize the service
    service = ConversationService()
    os.loadenv(".env")  # Load environment variables from .env file
    
    # Example system prompt for a mental health support context
    system_prompt = """You are a supportive AI assistant for a digital health application 
    focused on positive memory recall and mental wellness. Be empathetic, encouraging, 
    and help users reflect on positive experiences. Always maintain a warm, supportive tone."""
    
    # Start a conversation
    print("MindSync Conversation Service")
    print("Type 'quit' to exit\n")
    
    while True:
        user_input = input("You: ")
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
        
        try:
            response = service.chat(
                user_message=user_input,
                system_prompt=system_prompt,
                temperature=0.7
            )
            print(f"\nAssistant: {response}\n")
        except Exception as e:
            print(f"Error: {e}")
            break