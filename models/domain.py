from pydantic import BaseModel
from typing import Optional

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