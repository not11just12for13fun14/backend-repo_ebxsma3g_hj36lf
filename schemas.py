"""
Database Schemas for MinSplit

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- Conversation -> "conversation"
- Message -> "message" (embedded inside Conversation typically)
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class Message(BaseModel):
    role: Literal["user", "emotional", "logical", "summary"] = Field(..., description="Who said the message")
    content: str = Field(..., description="Message text content")
    turn: int = Field(0, description="Turn index in the debate")

class Conversation(BaseModel):
    situation: str = Field(..., description="User provided situation or decision context")
    messages: List[Message] = Field(default_factory=list, description="Ordered messages in the debate")
    final_decision: Optional[str] = Field(None, description="Balanced decision synthesized from the debate")
    tags: List[str] = Field(default_factory=list, description="Optional tags inferred from the situation")
