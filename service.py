import os
import google.generativeai as genai
from typing import Dict, Any, Optional, Tuple
from models import ChatResponse, IntentType
from conversation_manager import ConversationManager
from symptom_triage import SymptomTriageService
from appointment_manager import AppointmentManager, BookingState

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Backend Base URL (Spring Boot)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")

class AIAgentService:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-flash') if GEMINI_API_KEY else None
        self.conversation_manager = ConversationManager()
        self.symptom_triage = SymptomTriageService()
        self.appointment_manager = AppointmentManager(BACKEND_URL)
    
    async def process_message(self, user_id: str, message: str, jwt_token: Optional[str] = None) -> ChatResponse:
        """
        Main entry point for processing user messages
        
        Args:
            user_id: User identifier
            message: User's message
            jwt_token: JWT token for authenticated requests
        
        Returns:
            ChatResponse with AI response and metadata
        """
        # Get or create session
        session = self.conversation_manager.get_session(user_id)
        
        # Add user message to history
        self.conversation_manager.add_message(user_id, "user", message)
        
        # Get conversation context
        conversation_history = self.conversation_manager.get_context_string(user_id, limit=5)
        
        # Classify intent
        intent = self._classify_intent(message, conversation_history)
        print(f"[AI Agent] Detected Intent: {intent} for user: {user_id}")
        
        # Handle based on intent
        response_text = ""
        action_data = None
        suggestions = []
        
        try:
            if intent == IntentType.GREETING.value:
                response_text = self._handle_greeting(user_id)
                suggestions = [
                    "Find a doctor",
                    "Book appointment",
                    "Check symptoms",
                    "View my appointments"
                ]
            
            elif intent == IntentType.SYMPTOM_CHECK.value:
                response_text, action_data = self._handle_symptom_check(message)
                suggestions = ["Book appointment", "Find specialist", "Emergency help"]
            
            elif intent == IntentType.SEARCH_DOCTOR.value or intent == IntentType.CHECK_AVAILABILITY.value:
                response_text, action_data, suggestions = self._handle_doctor_search(message, session)
            
            elif intent == IntentType.BOOK_APPOINTMENT.value:
                response_text, action_data, suggestions = await self._handle_booking_flow(
                    user_id, message, session, jwt_token
                )
            
            elif intent == IntentType.CANCEL_POLICY.value:
                response_text = self._handle_cancel_policy()
            
            elif intent == IntentType.VIEW_APPOINTMENTS.value:
                response_text = self._handle_view_appointments(user_id, jwt_token)
                
            elif intent == IntentType.FAREWELL.value:
                response_text = self._handle_farewell(user_id)
                self.conversation_manager.end_session(user_id)
            
            else:
                # General query
                response_text = self._generate_general_response(message, conversation_history)
                suggestions = ["Book appointment", "Find doctor", "Check symptoms"]
        
        except Exception as e:
            print(f"[AI Agent] Error processing message: {e}")
            response_text = "I apologize, but I'm having trouble processing your request. Please try again or rephrase your question."
        
        # Add assistant response to history
        self.conversation_manager.add_message(user_id, "assistant", response_text)
        
        return ChatResponse(
            response=response_text,
            intent=intent,
            data=action_data,
            suggestions=suggestions[:4] if suggestions else None  # Limit to 4 suggestions
        )
    
    def _classify_intent(self, message: str, context: str = "") -> str:
        """Classify user intent using AI"""
        if not self.model:
            return self._fallback_intent_classification(message)
        
        prompt = f"""Classify the user's intent into ONE of these categories:
- GREETING: Greetings like hello, hi, good morning
- SYMPTOM_CHECK: Describing symptoms or health issues
- SEARCH_DOCTOR: Looking for doctors, asking about specialists
- CHECK_AVAILABILITY: Asking about doctor availability or open slots
- BOOK_APPOINTMENT: Wanting to book/schedule an appointment
- CANCEL_APPOINTMENT: Want to cancel an appointment
- RESCHEDULE_APPOINTMENT: Want to change appointment time
- VIEW_APPOINTMENTS: Want to see their appointments
- CANCEL_POLICY: Asking about cancellation or refund policy
- INSURANCE_QUERY: Questions about insurance
- FAREWELL: Goodbye, bye, thanks and ending conversation
- PATIENT_QUERY: General questions about clinic, services, etc.

{f"Recent conversation context: {context}" if context else ""}

Current message: "{message}"

Respond with ONLY the category name (e.g., BOOK_APPOINTMENT)."""

        try:
            response = self.model.generate_content(prompt)
            intent = response.text.strip()
            
            # Validate intent
            valid_intents = [e.value for e in IntentType]
            if intent in valid_intents:
                return intent
            
            # Fallback
            return self._fallback_intent_classification(message)
        except Exception as e:
            print(f"[AI Agent] Intent classification error: {e}")
            return self._fallback_intent_classification(message)
    
    def _fallback_intent_classification(self, message: str) -> str:
        """Rule-based intent classification fallback"""
        message_lower = message.lower()
        
        # Greeting
        if any(word in message_lower for word in ["hello", "hi", "hey", "good morning", "good evening"]):
            return IntentType.GREETING.value
        
        # Symptom check
        if any(word in message_lower for word in ["pain", "fever", "sick", "symptom", "ache", "hurt", "cough", "cold"]):
            return IntentType.SYMPTOM_CHECK.value
        
        # Booking
        if any(word in message_lower for word in ["book", "appointment", "schedule", "reserve"]):
            return IntentType.BOOK_APPOINTMENT.value
        
        # Doctor search
        if any(word in message_lower for word in ["doctor", "specialist", "find", "search", "cardiologist", "dermatologist"]):
            return IntentType.SEARCH_DOCTOR.value
        
        # Cancel policy
        if any(word in message_lower for word in ["cancel", "refund", "policy"]):
            return IntentType.CANCEL_POLICY.value
        
        # Farewell
        if any(word in message_lower for word in ["bye", "goodbye", "see you", "thanks", "thank you"]) and \
           any(word in message_lower for word in ["bye", "goodbye", "see you"]):
            return IntentType.FAREWELL.value
        
        return IntentType.PATIENT_QUERY.value
    
    def _handle_greeting(self, user_id: str) -> str:
        """Handle greeting messages"""
        return (
            "Hello! 👋 I'm your AI medical appointment assistant. "
            "I can help you with:\n"
            "• Finding and booking doctors\n"
            "• Checking doctor availability\n"
            "• Analyzing symptoms\n"
            "• Viewing your appointments\n\n"
            "How can I assist you today?"
        )
    
    def _handle_symptom_check(self, message: str) -> Tuple[str, Optional[Dict]]:
        """Handle symptom analysis"""
        result = self.symptom_triage.analyze_symptoms(message)
        
        response = f"**Symptom Analysis:**\n\n"
        response += f"🔍 Urgency: {result['urgency']}\n"
        response += f"👨‍⚕️ Recommended Specialty: {result['recommended_specialty']}\n"
        response += f"💡 Advice: {result['advice']}\n\n"
        response += f"_{result['disclaimer']}_\n\n"
        
        if result['urgency'] != 'EMERGENCY':
            response += "Would you like me to help you find a specialist or book an appointment?"
        
        return response, result
    
    def _handle_doctor_search(self, message: str, session: Dict) -> Tuple[str, Optional[Dict], list]:
        """Handle doctor search queries"""
        # Extract search keyword from message
        keyword = self._extract_search_keyword(message)
        
        if not keyword:
            return (
                "I'd be happy to help you find a doctor. Could you please tell me:\n"
                "• What specialty are you looking for? (e.g., Cardiologist, Dermatologist)\n"
                "• Or which city/location?"
            ), None, []
        
        # Search doctors
        search_result = self.appointment_manager.search_doctors(keyword)
        
        # Handle errors
        if not search_result.get("success"):
            error_message = search_result.get("message", "Unable to search for doctors")
            
            # If no results found, suggest specialties
            if search_result.get("error_code") == "NOT_FOUND":
                specialists = self.appointment_manager.get_specialists()
                specialist_names = [s.get('specialist', '') for s in specialists[:10]]
                
                return (
                    f"{error_message}. "
                    f"Here are some available specialties:\n" +
                    "\n".join(f"• {s}" for s in specialist_names) +
                    "\n\nWhich specialty would you like?"
                ), {"specialists": specialists}, specialist_names[:4]
            
            return error_message, None, ["Try again", "Browse specialties"]
        
        doctors = search_result.get("data", [])
        
        if not doctors:
            return (
                "I couldn't find any doctors at the moment. Please try again later."
            ), None, []
        
        # Format doctor list
        response = f"I found {len(doctors)} doctor(s) for '{keyword}':\n\n"
        
        for i, doc in enumerate(doctors[:5], 1):
            response += (
                f"{i}. Dr. {doc.get('firstName', '')} {doc.get('lastName', '')}\n"
                f"   Specialty: {doc.get('specialist', 'N/A')}\n"
                f"   Experience: {doc.get('experience', 'N/A')} years\n"
                f"   Fee: ₹{doc.get('consultationFee', 'N/A')}\n"
                f"   Location: {doc.get('clinicName', 'N/A')}, {doc.get('city', 'N/A')}\n\n"
            )
        
        if len(doctors) > 5:
            response += f"...and {len(doctors) - 5} more.\n\n"
        
        response += "Would you like to book an appointment with any of these doctors?"
        
        # Update session context
        self.conversation_manager.update_session_context(
            session['user_id'],
            {"available_doctors": [d['doctorId'] for d in doctors[:5]]}
        )
        
        suggestions = [f"Book with Dr. {d.get('lastName', '')}" for d in doctors[:3]]
        
        return response, {"doctors": doctors[:5]}, suggestions
    
    def _extract_search_keyword(self, message: str) -> str:
        """Extract search keyword from message"""
        message_lower = message.lower()
        
        # Common specialty keywords
        specialties = [
            "cardiologist", "dermatologist", "orthopedic", "pediatrician",
            "dentist", "gynecologist", "neurologist", "psychiatrist",
            "ophthalmologist", "ent", "gastroenterologist"
        ]
        
        for specialty in specialties:
            if specialty in message_lower:
                return specialty
        
        #Extract quoted text or after "for"
        import re
        quoted = re.search(r'"([^"]+)"', message)
        if quoted:
            return quoted.group(1)
        
        for_match = re.search(r'for\s+(\w+)', message_lower)
        if for_match:
            return for_match.group(1)
        
        # Return last word if it's not a common word
        words = message.split()
        if words:
            last_word = words[-1].strip('.,!?')
            if last_word.lower() not in ['doctor', 'specialist', 'find', 'search', 'need', 'want']:
                return last_word
        
        return ""
    
    async def _handle_booking_flow(self, user_id: str, message: str, session: Dict, jwt_token: Optional[str]) -> Tuple[str, Optional[Dict], list]:
        """Handle multi-turn appointment booking flow"""
        
        if not jwt_token:
            return (
                "To book an appointment, you need to be logged in. "
                "Please log in to your account and try again."
            ), None, ["Login", "Create account"]
        
        # Get current booking state from session
        booking_state = session.get("context", {}).get("booking_state", BookingState.INITIAL.value)
        
        # Extract booking information from message
        booking_info = self.appointment_manager.extract_booking_info(message, session.get("context", {}))
        
        # Update context with extracted info
        if booking_info:
            self.conversation_manager.update_session_context(user_id, booking_info)
            session = self.conversation_manager.get_session(user_id)
        
        context = session.get("context", {})
        
        # State machine for booking flow
        if not context.get("doctor_id"):
            # Need to select doctor first
            return self._booking_step_select_doctor(message, context)
        
        elif not context.get("date"):
            # Need to select date
            return self._booking_step_select_date(message, context)
        
        elif not context.get("time"):
            # Need to select time
            return self._booking_step_select_time(message, context)
        
        else:
            # All info collected, confirm
            return self._booking_step_confirm(user_id, context, jwt_token)
    
    def _booking_step_select_doctor(self, message: str, context: Dict) -> Tuple[str, Optional[Dict], list]:
        """Booking step 1: Select doctor"""
        keyword = self._extract_search_keyword(message)
        
        if keyword:
            return self._handle_doctor_search(message, {"user_id": context.get("user_id", ""), "context": context})
        
        return (
            "To book an appointment, I need to know which doctor you'd like to see. "
            "You can search by specialty (e.g., 'cardiologist') or doctor name."
        ), None, ["Cardiologist", "Dermatologist", "Dentist"]
    
    def _booking_step_select_date(self, message: str, context: Dict) -> Tuple[str, Optional[Dict], list]:
        """Booking step 2: Select date"""
        date = self.appointment_manager.parse_date_from_text(message)
        
        if date:
            # Check available slots for this date
            doctor_id = context.get("doctor_id")
            if doctor_id:
                slots_result = self.appointment_manager.get_available_slots(doctor_id, date)
                
                # Handle errors
                if not slots_result.get("success"):
                    error_message = slots_result.get("message", "Unable to fetch available slots")
                    error_code = slots_result.get("error_code")
                    
                    if error_code == "PAST_DATE":
                        return (
                            error_message + " Please select a future date."
                        ), None, ["Tomorrow", "Day after tomorrow", "Next week"]
                    elif error_code == "NO_SLOTS_FOUND":
                        return (
                            f"Sorry, no slots available on {date}. "
                            "Would you like to try another date?"
                        ), None, ["Tomorrow", "Day after tomorrow", "Next week"]
                    else:
                        return (
                            f"{error_message}. Would you like to try another date?"
                        ), None, ["Tomorrow", "Try again"]
                
                slots = slots_result.get("data", [])
                
                if slots:
                    formatted_slots = self.appointment_manager.format_available_slots(slots)
                    return (
                        f"Great! Here are available time slots for {date}:\n\n{formatted_slots}\n\n"
                        "Which time works best for you?"
                    ), {"available_slots": slots, "date": date}, []
                else:
                    return (
                        f"Sorry, no slots available on {date}. "
                        "Would you like to try another date?"
                    ), None, ["Tomorrow", "Day after tomorrow", "Next week"]
        
        return (
            "When would you like to schedule the appointment? "
            "You can say something like 'tomorrow', 'next Monday', or provide a specific date."
        ), None, ["Tomorrow", "Day after tomorrow", "Next week"]
    
    def _booking_step_select_time(self, message: str, context: Dict) -> Tuple[str, Optional[Dict], list]:
        """Booking step 3: Select time"""
        time = self.appointment_manager.parse_time_from_text(message)
        
        if time:
            return (
                f"Perfect! Let me confirm your appointment:\n\n"
                f"📅 Date: {context.get('date')}\n"
                f"🕐 Time: {time}\n"
                f"👨‍⚕️ Doctor: {context.get('doctor_name', 'Selected doctor')}\n\n"
                "Please confirm to book this appointment."
            ), {"time": time}, ["Confirm", "Cancel"]
        
        return (
            "What time would you prefer? "
            "You can say something like '3:00 PM' or '15:00'."
        ), None, []
    
    def _booking_step_confirm(self, user_id: str, context: Dict, jwt_token: Optional[str]) -> Tuple[str, Optional[Dict], list]:
        """Booking step 4: Confirm and create appointment"""
        # This would make an actual API call to book the appointment
        # For now, return confirmation message
        return (
            "✅ Your appointment has been booked successfully!\n\n"
            f"📅 Date: {context.get('date')}\n"
            f"🕐 Time: {context.get('time')}\n"
            f"👨‍⚕️ Doctor: {context.get('doctor_name', 'Doctor')}\n\n"
            "You will receive a confirmation email and SMS shortly. "
            "You can view all your appointments in 'My Appointments'."
        ), {"booking_confirmed": True}, ["View appointments", "Book another"]
    
    def _handle_cancel_policy(self) -> str:
        """Handle cancellation policy query"""
        return (
            "**Cancellation Policy:**\n\n"
            "• You can cancel your appointment up to 24 hours before the scheduled time for a full refund.\n"
            "• Cancellations made within 24 hours may be subject to a cancellation fee.\n"
            "• No-shows will be charged the full consultation fee.\n"
            "• Rescheduling is free if done at least 6 hours before the appointment.\n\n"
            "Would you like to cancel or reschedule an existing appointment?"
        )
    
    def _handle_view_appointments(self, user_id: str, jwt_token: Optional[str]) -> str:
        """Handle view appointments request"""
        if not jwt_token:
            return "Please log in to view your appointments."
        
        # Would make API call to get appointments
        return (
            "To view your appointments, please go to the 'My Appointments' section in your account. "
            "You can also ask me to help you book, cancel, or reschedule appointments."
        )
    
    def _handle_farewell(self, user_id: str) -> str:
        """Handle farewell message"""
        return (
            "Thank you for using our service! Take care and feel better soon. 👋\n\n"
            "If you need any assistance in the future, I'm always here to help!"
        )
    
    def _generate_general_response(self, message: str, context: str = "") -> str:
        """Generate response for general queries using AI"""
        if not self.model:
            return "I'm here to help you with booking appointments, finding doctors, and checking symptoms. How can I assist you?"
        
        prompt = f"""You are a helpful medical clinic AI assistant. Answer the following query politely and professionally.

        IMPORTANT Rules:
        - Do NOT give medical advice or diagnosis
        - If asked about medical conditions, suggest seeing a doctor
        - Keep responses concise (2-3 sentences)
        - Always be helpful and empathetic

        {f"Recent conversation: {context}" if context else ""}

        User Query: "{message}"

        Respond naturally and helpfully:"""

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"[AI Agent] General response error: {e}")
            return (
                "I'm here to help you with booking appointments and finding doctors. "
                "Is there anything specific I can assist you with?"
            )
