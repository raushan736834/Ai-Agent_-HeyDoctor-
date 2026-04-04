# cancellation_state_machine.py
from typing import Tuple, Optional, Dict, List, Any
from models.state import CancellationState, CancellationContext
from appointment_manager import AppointmentManager
import logging
from datetime import datetime, timedelta

class CancellationStateMachine:
    """Finite State Machine for appointment cancellation"""
    
    TRANSITIONS = {
        CancellationState.INITIAL: [CancellationState.FETCHING_APPOINTMENTS, CancellationState.ABORTED],
        CancellationState.FETCHING_APPOINTMENTS: [CancellationState.SELECTING_APPOINTMENT, CancellationState.ERROR, CancellationState.ABORTED],
        CancellationState.SELECTING_APPOINTMENT: [CancellationState.CONFIRMING_CANCELLATION, CancellationState.FETCHING_APPOINTMENTS, CancellationState.ABORTED],
        CancellationState.CONFIRMING_CANCELLATION: [CancellationState.PROCESSING, CancellationState.SELECTING_APPOINTMENT, CancellationState.ABORTED],
        CancellationState.PROCESSING: [CancellationState.COMPLETED, CancellationState.ERROR],
        CancellationState.COMPLETED: [CancellationState.INITIAL],
        CancellationState.ERROR: [CancellationState.INITIAL, CancellationState.ABORTED],
        CancellationState.ABORTED: [CancellationState.INITIAL]
    }
    
    def __init__(self, appointment_manager: AppointmentManager):
        self.appointment_manager = appointment_manager
        self.logger = logging.getLogger(__name__)
    
    def transition(self, current_state: CancellationState, next_state: CancellationState) -> bool:
        """Validate state transition"""
        if next_state not in self.TRANSITIONS.get(current_state, []):
            self.logger.warning(f"Invalid transition: {current_state} -> {next_state}")
            return False
        return True
    
    async def process_step(
        self,
        user_id: str,
        message: str,
        context: CancellationContext,
        jwt_token: Optional[str] = None
    ) -> Tuple[str, CancellationContext, List[str], Optional[Dict]]:
        """Process current step in cancellation flow"""
        
        self.logger.info(f"Cancellation step: {context.state} for user {user_id}")
        
        handlers = {
            CancellationState.INITIAL: self._handle_initial,
            CancellationState.FETCHING_APPOINTMENTS: self._handle_fetching,
            CancellationState.SELECTING_APPOINTMENT: self._handle_selection,
            CancellationState.CONFIRMING_CANCELLATION: self._handle_confirmation,
            CancellationState.PROCESSING: self._handle_processing,
        }
        
        handler = handlers.get(context.state)
        if not handler:
            return ("Error in cancellation flow", context, ["Start over"], None)
        
        return await handler(user_id, message, context, jwt_token)
    
    async def _handle_initial(
        self, user_id: str, message: str, context: CancellationContext, jwt_token: Optional[str]
    ) -> Tuple[str, CancellationContext, List[str], Optional[Dict]]:
        """Initial state - check auth and start fetching"""
        
        if not jwt_token:
            return (
                "🔐 Please **log in** to view and cancel your appointments.",
                context,
                ["Login"],
                None
            )
        
        # Transition to fetching
        if self.transition(context.state, CancellationState.FETCHING_APPOINTMENTS):
            context.state = CancellationState.FETCHING_APPOINTMENTS
            return await self._handle_fetching(user_id, message, context, jwt_token)
        
        return ("Error starting cancellation", context, [], None)
    
    async def _handle_fetching(
        self, user_id: str, message: str, context: CancellationContext, jwt_token: Optional[str]
    ) -> Tuple[str, CancellationContext, List[str], Optional[Dict]]:
        """Fetch user's upcoming appointments"""
        
        # Fetch appointments from backend
        appointments_result = await self.appointment_manager.get_user_appointments(
            jwt_token,
            status="UPCOMING"  # Only upcoming appointments can be cancelled
        )
        
        if not appointments_result.get("success"):
            if self.transition(context.state, CancellationState.ERROR):
                context.state = CancellationState.ERROR
                context.error_message = appointments_result.get("message")
            
            return (
                f"❌ {appointments_result.get('message', 'Unable to fetch appointments')}\n\n"
                "Please try again later.",
                context,
                ["Try again", "Exit"],
                None
            )
        
        appointments = appointments_result.get("data", [])
        
        if not appointments:
            if self.transition(context.state, CancellationState.COMPLETED):
                context.state = CancellationState.COMPLETED
            
            return (
                "You don't have any upcoming appointments to cancel.\n\n"
                "Would you like to book a new appointment?",
                context,
                ["Book appointment", "Exit"],
                None
            )
        
        # Store appointments in context
        context.user_appointments = appointments
        
        # Transition to selection
        if self.transition(context.state, CancellationState.SELECTING_APPOINTMENT):
            context.state = CancellationState.SELECTING_APPOINTMENT
        
        # Format appointments
        response = "📋 **Your Upcoming Appointments:**\n\n"
        
        for i, apt in enumerate(appointments[:10], 1):
            doctor_name = apt.get('doctorName', 'Doctor')
            date = apt.get('appointmentDate', 'N/A')
            time = apt.get('appointmentTime', 'N/A')
            specialty = apt.get('specialty', '')
            
            # Check if cancellable (24 hours before)
            is_cancellable = self._is_cancellable(date, time)
            status_icon = "✅" if is_cancellable else "⏰"
            
            response += (
                f"{status_icon} **{i}. Dr. {doctor_name}**\n"
                f"   📅 {date} at {time}\n"
                f"   🏥 {specialty}\n"
            )
            
            if not is_cancellable:
                response += "   ⚠️ _Cannot cancel (less than 24hrs before)_\n"
            
            response += "\n"
        
        response += "Please select an appointment to cancel by saying the number (e.g., '1' or 'First one')"
        
        suggestions = [f"Cancel #{i}" for i in range(1, min(4, len(appointments) + 1))]
        suggestions.append("Exit")
        
        return (
            response,
            context,
            suggestions,
            {"appointments": appointments}
        )
    
    def _is_cancellable(self, date_str: str, time_str: str) -> bool:
        """Check if appointment is cancellable (24 hours before)"""
        try:
            apt_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            time_until = apt_datetime - datetime.now()
            return time_until > timedelta(hours=24)
        except:
            return True  # Default to cancellable if parsing fails
    
    async def _handle_selection(
        self, user_id: str, message: str, context: CancellationContext, jwt_token: Optional[str]
    ) -> Tuple[str, CancellationContext, List[str], Optional[Dict]]:
        """Handle appointment selection"""
        
        # Extract selection
        appointment_index = self._extract_appointment_selection(message)
        
        if appointment_index is None:
            return (
                "Please select an appointment by number (e.g., '1', 'Second one', etc.)",
                context,
                [f"#{i}" for i in range(1, min(4, len(context.user_appointments) + 1))],
                None
            )
        
        if appointment_index >= len(context.user_appointments):
            return (
                f"Invalid selection. Please choose a number between 1 and {len(context.user_appointments)}",
                context,
                [f"#{i}" for i in range(1, min(4, len(context.user_appointments) + 1))],
                None
            )
        
        selected_apt = context.user_appointments[appointment_index]
        
        # Check if cancellable
        if not self._is_cancellable(
            selected_apt.get('appointmentDate', ''),
            selected_apt.get('appointmentTime', '')
        ):
            return (
                "⚠️ **This appointment cannot be cancelled**\n\n"
                "Appointments can only be cancelled at least 24 hours before the scheduled time.\n\n"
                "Would you like to select a different appointment?",
                context,
                ["Choose another", "Exit"],
                None
            )
        
        # Store selected appointment
        context.selected_appointment_id = selected_apt.get('appointmentId')
        context.selected_appointment_details = selected_apt
        
        # Calculate refund eligibility
        context.refund_eligible = True  # Assuming 24+ hours = full refund
        context.refund_amount = selected_apt.get('consultationFee', 0)
        
        # Transition to confirmation
        if self.transition(context.state, CancellationState.CONFIRMING_CANCELLATION):
            context.state = CancellationState.CONFIRMING_CANCELLATION
        
        return (
            "📋 **Cancellation Details:**\n\n"
            f"👨‍⚕️ **Doctor:** Dr. {selected_apt.get('doctorName', 'N/A')}\n"
            f"📅 **Date:** {selected_apt.get('appointmentDate', 'N/A')}\n"
            f"🕐 **Time:** {selected_apt.get('appointmentTime', 'N/A')}\n"
            f"💰 **Refund:** ₹{context.refund_amount} (Full refund)\n\n"
            "⚠️ **Are you sure you want to cancel this appointment?**\n\n"
            "_Say 'Confirm' to proceed with cancellation or 'Back' to choose another._",
            context,
            ["✅ Confirm cancellation", "❌ Go back", "Exit"],
            {"selected_appointment": selected_apt}
        )
    
    def _extract_appointment_selection(self, message: str) -> Optional[int]:
        """Extract appointment selection from message"""
        import re
        
        message_lower = message.lower()
        
        # Number match
        number_match = re.search(r'\b(\d+)\b', message)
        if number_match:
            return int(number_match.group(1)) - 1  # Convert to 0-indexed
        
        # Ordinal words
        ordinals = {
            'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4,
            '1st': 0, '2nd': 1, '3rd': 2, '4th': 3, '5th': 4
        }
        
        for word, index in ordinals.items():
            if word in message_lower:
                return index
        
        return None
    
    async def _handle_confirmation(
        self, user_id: str, message: str, context: CancellationContext, jwt_token: Optional[str]
    ) -> Tuple[str, CancellationContext, List[str], Optional[Dict]]:
        """Handle cancellation confirmation"""
        
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['confirm', 'yes', 'cancel it', 'proceed']):
            # Proceed with cancellation
            if self.transition(context.state, CancellationState.PROCESSING):
                context.state = CancellationState.PROCESSING
                return await self._handle_processing(user_id, message, context, jwt_token)
        
        elif any(word in message_lower for word in ['back', 'no', 'choose another']):
            # Go back to selection
            if self.transition(context.state, CancellationState.SELECTING_APPOINTMENT):
                context.state = CancellationState.SELECTING_APPOINTMENT
                context.selected_appointment_id = None
                context.selected_appointment_details = None
                
                return await self._handle_selection(user_id, "show appointments", context, jwt_token)
        
        elif 'exit' in message_lower or 'abort' in message_lower:
            if self.transition(context.state, CancellationState.ABORTED):
                context.state = CancellationState.ABORTED
                context.reset()
                
                return (
                    "❌ Cancellation aborted. Your appointment is still active.",
                    context,
                    ["View appointments", "Exit"],
                    None
                )
        
        return (
            "Please confirm the cancellation by saying:\n"
            "• 'Confirm' to cancel the appointment\n"
            "• 'Back' to choose a different appointment\n"
            "• 'Exit' to abort",
            context,
            ["Confirm", "Back", "Exit"],
            None
        )
    
    async def _handle_processing(
        self, user_id: str, message: str, context: CancellationContext, jwt_token: Optional[str]
    ) -> Tuple[str, CancellationContext, List[str], Optional[Dict]]:
        """Process the actual cancellation via API"""
        
        try:
            # Call cancellation API
            cancel_result = await self.appointment_manager.cancel_appointment(
                context.selected_appointment_id,
                jwt_token,
                reason=context.cancellation_reason
            )
            
            if cancel_result.get("success"):
                cancellation_data = cancel_result.get("data", {})
                context.cancellation_id = cancellation_data.get("cancellationId")
                
                # Transition to completed
                if self.transition(context.state, CancellationState.COMPLETED):
                    context.state = CancellationState.COMPLETED
                
                apt_details = context.selected_appointment_details
                
                return (
                    "✅ **Appointment Cancelled Successfully**\n\n"
                    f"📋 **Cancellation ID:** {context.cancellation_id}\n"
                    f"👨‍⚕️ **Doctor:** Dr. {apt_details.get('doctorName', 'N/A')}\n"
                    f"📅 **Original Date:** {apt_details.get('appointmentDate', 'N/A')}\n"
                    f"💰 **Refund Amount:** ₹{context.refund_amount}\n\n"
                    "💳 Your refund will be processed within 5-7 business days.\n"
                    "📧 You will receive a confirmation email shortly.",
                    context,
                    ["Book new appointment", "View appointments", "Done"],
                    {
                        "cancellation": cancellation_data,
                        "refund_amount": context.refund_amount
                    }
                )
            else:
                # Cancellation failed
                if self.transition(context.state, CancellationState.ERROR):
                    context.state = CancellationState.ERROR
                    context.error_message = cancel_result.get("message")
                
                return (
                    f"❌ **Cancellation Failed**\n\n"
                    f"{cancel_result.get('message', 'An error occurred')}\n\n"
                    "Would you like to try again?",
                    context,
                    ["Try again", "Contact support", "Exit"],
                    None
                )
        
        except Exception as e:
            self.logger.error(f"Error processing cancellation: {e}", exc_info=True)
            
            if self.transition(context.state, CancellationState.ERROR):
                context.state = CancellationState.ERROR
                context.error_message = str(e)
            
            return (
                "⚠️ An unexpected error occurred during cancellation.\n"
                "Please try again or contact support.",
                context,
                ["Try again", "Contact support"],
                None
            )