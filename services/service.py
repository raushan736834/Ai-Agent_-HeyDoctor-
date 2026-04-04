import os
import google.generativeai as genai
from typing import Dict, Any, Optional, Tuple
from models.api import ChatResponse
from models.enum import  IntentType
from conversation_manager import ConversationManager
from symptom_triage import SymptomTriageService
from appointment_manager import AppointmentManager, BookingState
from models.state import FlowType

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
            if session.active_flow == FlowType.BOOKING:
                context = session.booking_context
                if context and context.state not in [BookingState.COMPLETED, BookingState.CANCELLED]:
                    response_text, updated_context, suggestions, action_data = \
                        await self.booking_sm.process_step(user_id, message, context, jwt_token)
                    
                    session.booking_context = updated_context
                    
                    if updated_context.state in [BookingState.COMPLETED, BookingState.CANCELLED]:
                        session.clear_active_flow()
            
            elif session.active_flow == FlowType.CANCELLATION:
                context = session.cancellation_context
                if context and context.state not in [CancellationState.COMPLETED, CancellationState.ABORTED]:
                    response_text, updated_context, suggestions, action_data = \
                        await self.cancellation_sm.process_step(user_id, message, context, jwt_token)
                    
                    session.cancellation_context = updated_context
                    
                    if updated_context.state in [CancellationState.COMPLETED, CancellationState.ABORTED]:
                        session.clear_active_flow()
            
            elif session.active_flow == FlowType.RESCHEDULING:
                context = session.rescheduling_context
                if context and context.state not in [ReschedulingState.COMPLETED, ReschedulingState.ABORTED]:
                    response_text, updated_context, suggestions, action_data = \
                        await self.rescheduling_sm.process_step(user_id, message, context, jwt_token)
                    
                    session.rescheduling_context = updated_context
                    
                    if updated_context.state in [ReschedulingState.COMPLETED, ReschedulingState.ABORTED]:
                        session.clear_active_flow()
            

            elif intent == IntentType.BOOK_APPOINTMENT.value:
                # Start booking flow
                from models.state import BookingContext
                session.booking_context = BookingContext()
                session.active_flow = FlowType.BOOKING
                
                response_text, updated_context, suggestions, action_data = \
                    await self.booking_sm.process_step(user_id, message, session.booking_context, jwt_token)
                
                session.booking_context = updated_context
            
            elif intent == IntentType.CANCEL_APPOINTMENT.value:
                # Start cancellation flow
                from models.state import CancellationContext
                session.cancellation_context = CancellationContext()
                session.active_flow = FlowType.CANCELLATION
                
                response_text, updated_context, suggestions, action_data = \
                    await self.cancellation_sm.process_step(user_id, message, session.cancellation_context, jwt_token)
                
                session.cancellation_context = updated_context
            
            elif intent == IntentType.RESCHEDULE_APPOINTMENT.value:
                # Start rescheduling flow
                from models.state import ReschedulingContext
                session.rescheduling_context = ReschedulingContext()
                session.active_flow = FlowType.RESCHEDULING
                
                response_text, updated_context, suggestions, action_data = \
                    await self.rescheduling_sm.process_step(user_id, message, session.rescheduling_context, jwt_token)
                
                session.rescheduling_context = updated_context
            
            elif intent == IntentType.GREETING.value:
                response_text = self._handle_greeting(user_id)
                suggestions = ["Find doctor", "Book appointment", "My appointments"]
            
            elif intent == IntentType.SYMPTOM_CHECK.value:
                response_text, action_data = self._handle_symptom_check(message)
                suggestions = ["Book appointment", "Find specialist"]
            
            elif intent == IntentType.SEARCH_DOCTOR.value:
                response_text, action_data, suggestions = await self._handle_doctor_search(message, session)
            
            elif intent == IntentType.VIEW_APPOINTMENTS.value:
                response_text = self._handle_view_appointments(user_id, jwt_token)
                suggestions = ["Cancel appointment", "Reschedule appointment"]
            
            elif intent == IntentType.CANCEL_POLICY.value:
                response_text = self._handle_cancel_policy()
            
            elif intent == IntentType.FAREWELL.value:
                response_text = self._handle_farewell(user_id)
                self.conversation_manager.end_session(user_id)
            
            else:
                response_text = self._generate_general_response(message, conversation_history)
                suggestions = ["Book appointment", "Find doctor", "My appointments"]
        
        except Exception as e:
            print(f"[AI Agent] Error: {e}")
            import traceback
            traceback.print_exc()
            response_text = "I encountered an error. Please try again."
        
        # Save session
        self.conversation_manager._save_session(session)
        
        # Add response to history
        self.conversation_manager.add_message(user_id, "assistant", response_text)
        
        return ChatResponse(
            response=response_text,
            intent=intent,
            data=action_data,
            suggestions=suggestions[:4] if suggestions else None
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
