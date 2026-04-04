from pydantic import BaseModel, Field, field_validator
from typing import List,Dict,Optional,Any

class ValidationError(BaseModel):
    """Validation error details"""
    field: str
    message: str
    error_code: Optional[str] = None

class ErrorResponse(BaseModel):
    """Standardized error response"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    validation_errors: Optional[List[ValidationError]] = None
    data: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User message")

    @field_validator('message')
    def message_not_empty(self, v):
        if not v or not v.strip():
            raise ValueError('Message cannot be empty or whitespace only')
        return v.strip()

class ChatResponse(BaseModel):
    response: str
    success: bool = True
    intent: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None  # Quick reply suggestions
    requires_action: Optional[bool] = False  # Whether user needs to take action
    error_code: Optional[str] = None
    validation_errors: Optional[List[ValidationError]] = None
