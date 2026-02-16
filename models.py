from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from enum import Enum

class IntentType(str, Enum):
    """Classification of user intents"""
    GREETING = "GREETING"
    PATIENT_QUERY = "PATIENT_QUERY"
    CHECK_AVAILABILITY = "CHECK_AVAILABILITY"
    SEARCH_DOCTOR = "SEARCH_DOCTOR"
    BOOK_APPOINTMENT = "BOOK_APPOINTMENT"
    CANCEL_APPOINTMENT = "CANCEL_APPOINTMENT"
    RESCHEDULE_APPOINTMENT = "RESCHEDULE_APPOINTMENT"
    VIEW_APPOINTMENTS = "VIEW_APPOINTMENTS"
    SYMPTOM_CHECK = "SYMPTOM_CHECK"
    CANCEL_POLICY = "CANCEL_POLICY"
    INSURANCE_QUERY = "INSURANCE_QUERY"
    FAREWELL = "FAREWELL"
    UNKNOWN = "UNKNOWN"

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
    message: str = Field(..., min_length=1, max_length=5000, description="User message")
    
    @validator('message')
    def message_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Message cannot be empty or whitespace only')
        return v.strip()

class ChatResponse(BaseModel):
    response: str
    success: bool = True
    intent: Optional[str] = None
    action_taken: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None  # Quick reply suggestions
    requires_action: Optional[bool] = False  # Whether user needs to take action
    validation_errors: Optional[List[ValidationError]] = None
    message: Optional[str] = None  # Additional message for status/errors

class SessionContext(BaseModel):
    """Tracks conversation session state"""
    user_id: str
    session_id: str
    started_at: str
    last_activity: str
    booking_state: Optional[str] = None
    selected_doctor_id: Optional[str] = None
    selected_date: Optional[str] = None
    selected_time: Optional[str] = None
    intent_history: List[str] = []
    metadata: Dict[str, Any] = {}

class DoctorInfo(BaseModel):
    """Doctor information from backend"""
    doctorId: str
    firstName: str
    lastName: str
    specialist: str
    experience: Optional[int] = None
    consultationFee: Optional[float] = None
    city: Optional[str] = None
    clinicName: Optional[str] = None

class SlotInfo(BaseModel):
    """Appointment slot information"""
    slotId: Optional[str] = None
    date: str
    time: str
    available: bool

class SymptomAnalysisResult(BaseModel):
    """Result of symptom triage"""
    urgency: str  # EMERGENCY, URGENT, ROUTINE
    recommended_specialty: str
    advice: str
    disclaimer: str

class BookingFlowState(BaseModel):
    """State of the booking flow"""
    state: str  # INITIAL, SELECT_DOCTOR, SELECT_DATE, SELECT_TIME, CONFIRM, COMPLETE
    doctor_id: Optional[str] = None
    doctor_name: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    slot_id: Optional[str] = None
