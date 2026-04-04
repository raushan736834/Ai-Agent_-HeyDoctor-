# models/state.py - Complete version with all flows
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# ============================================================================
# BOOKING FLOW
# ============================================================================
class BookingState(str, Enum):
    """Finite State Machine for booking flow"""
    INITIAL = "INITIAL"
    SELECTING_SPECIALTY = "SELECTING_SPECIALTY"
    SELECTING_DOCTOR = "SELECTING_DOCTOR"
    SELECTING_DATE = "SELECTING_DATE"
    SELECTING_TIME = "SELECTING_TIME"
    CONFIRMING = "CONFIRMING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"

class BookingContext(BaseModel):
    """Complete booking context"""
    state: BookingState = BookingState.INITIAL
    search_keyword: Optional[str] = None
    available_doctors: List[Dict] = []
    selected_doctor_id: Optional[str] = None
    selected_doctor_name: Optional[str] = None
    selected_date: Optional[str] = None
    available_slots: List[str] = []
    selected_time: Optional[str] = None
    slot_id: Optional[str] = None
    appointment_id: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.now)
    retry_count: int = 0
    error_message: Optional[str] = None
    
    def is_complete(self) -> bool:
        return all([
            self.selected_doctor_id,
            self.selected_date,
            self.selected_time
        ])
    
    def reset(self):
        self.state = BookingState.INITIAL
        self.selected_doctor_id = None
        self.selected_doctor_name = None
        self.selected_date = None
        self.selected_time = None
        self.available_slots = []
        self.retry_count = 0


class CancellationState(str, Enum):
    """Finite State Machine for cancellation flow"""
    INITIAL = "INITIAL"
    FETCHING_APPOINTMENTS = "FETCHING_APPOINTMENTS"
    SELECTING_APPOINTMENT = "SELECTING_APPOINTMENT"
    CONFIRMING_CANCELLATION = "CONFIRMING_CANCELLATION"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    ERROR = "ERROR"

class CancellationContext(BaseModel):
    """Context for appointment cancellation"""
    state: CancellationState = CancellationState.INITIAL
    
    # User's appointments
    user_appointments: List[Dict] = []
    
    # Selected appointment to cancel
    selected_appointment_id: Optional[str] = None
    selected_appointment_details: Optional[Dict] = None
    
    # Cancellation details
    cancellation_reason: Optional[str] = None
    refund_eligible: bool = False
    refund_amount: Optional[float] = None
    
    # Processing
    cancellation_id: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.now)
    retry_count: int = 0
    error_message: Optional[str] = None
    
    def reset(self):
        self.state = CancellationState.INITIAL
        self.selected_appointment_id = None
        self.selected_appointment_details = None
        self.cancellation_reason = None
        self.retry_count = 0


class ReschedulingState(str, Enum):
    """Finite State Machine for rescheduling flow"""
    INITIAL = "INITIAL"
    FETCHING_APPOINTMENTS = "FETCHING_APPOINTMENTS"
    SELECTING_APPOINTMENT = "SELECTING_APPOINTMENT"
    SELECTING_NEW_DATE = "SELECTING_NEW_DATE"
    SELECTING_NEW_TIME = "SELECTING_NEW_TIME"
    CONFIRMING_RESCHEDULE = "CONFIRMING_RESCHEDULE"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    ERROR = "ERROR"

class ReschedulingContext(BaseModel):
    """Context for appointment rescheduling"""
    state: ReschedulingState = ReschedulingState.INITIAL
    
    # User's appointments
    user_appointments: List[Dict] = []
    
    # Original appointment
    original_appointment_id: Optional[str] = None
    original_appointment_details: Optional[Dict] = None
    original_date: Optional[str] = None
    original_time: Optional[str] = None
    
    # New schedule
    new_date: Optional[str] = None
    available_slots: List[str] = []
    new_time: Optional[str] = None
    new_slot_id: Optional[str] = None
    
    # Processing
    doctor_id: Optional[str] = None
    doctor_name: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.now)
    retry_count: int = 0
    error_message: Optional[str] = None
    
    def reset(self):
        self.state = ReschedulingState.INITIAL
        self.original_appointment_id = None
        self.new_date = None
        self.new_time = None
        self.available_slots = []
        self.retry_count = 0


class FlowType(str, Enum):
    """Types of conversation flows"""
    NONE = "NONE"
    BOOKING = "BOOKING"
    CANCELLATION = "CANCELLATION"
    RESCHEDULING = "RESCHEDULING"

class ConversationSession(BaseModel):
    """Enhanced session model supporting multiple flows"""
    user_id: str
    session_id: str
    started_at: datetime
    last_activity: datetime
    
    # Active flow tracking
    active_flow: FlowType = FlowType.NONE
    
    # Flow contexts (only one active at a time)
    booking_context: Optional[BookingContext] = None
    cancellation_context: Optional[CancellationContext] = None
    rescheduling_context: Optional[ReschedulingContext] = None
    
    # Conversation history
    message_count: int = 0
    last_intent: Optional[str] = None
    intent_history: List[str] = []
    
    # User preferences
    preferred_specialty: Optional[str] = None
    preferred_city: Optional[str] = None
    
    def get_active_context(self):
        """Get the currently active flow context"""
        if self.active_flow == FlowType.BOOKING:
            return self.booking_context
        elif self.active_flow == FlowType.CANCELLATION:
            return self.cancellation_context
        elif self.active_flow == FlowType.RESCHEDULING:
            return self.rescheduling_context
        return None
    
    def clear_active_flow(self):
        """Clear the active flow and its context"""
        if self.active_flow == FlowType.BOOKING:
            self.booking_context = None
        elif self.active_flow == FlowType.CANCELLATION:
            self.cancellation_context = None
        elif self.active_flow == FlowType.RESCHEDULING:
            self.rescheduling_context = None
        self.active_flow = FlowType.NONE