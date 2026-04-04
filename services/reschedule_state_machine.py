# rescheduling_state_machine.py
from typing import Tuple, Optional, Dict, List, Any
from models.state import ReschedulingState, ReschedulingContext
from appointment_manager import AppointmentManager
import logging

class ReschedulingStateMachine:
    """Finite State Machine for appointment rescheduling"""
    
    TRANSITIONS = {
        ReschedulingState.INITIAL: [ReschedulingState.FETCHING_APPOINTMENTS, ReschedulingState.ABORTED],
        ReschedulingState.FETCHING_APPOINTMENTS: [ReschedulingState.SELECTING_APPOINTMENT, ReschedulingState.ERROR, ReschedulingState.ABORTED],
        ReschedulingState.SELECTING_APPOINTMENT: [ReschedulingState.SELECTING_NEW_DATE, ReschedulingState.FETCHING_APPOINTMENTS, ReschedulingState.ABORTED],
        ReschedulingState.SELECTING_NEW_DATE: [ReschedulingState.SELECTING_NEW_TIME, ReschedulingState.SELECTING_APPOINTMENT, ReschedulingState.ABORTED],
        ReschedulingState.SELECTING_NEW_TIME: [ReschedulingState.CONFIRMING_RESCHEDULE, ReschedulingState.SELECTING_NEW_DATE, ReschedulingState.ABORTED],
        ReschedulingState.CONFIRMING_RESCHEDULE: [ReschedulingState.PROCESSING, ReschedulingState.SELECTING_NEW_TIME, ReschedulingState.ABORTED],
        ReschedulingState.PROCESSING: [ReschedulingState.COMPLETED, ReschedulingState.ERROR],
        ReschedulingState.COMPLETED: [ReschedulingState.INITIAL],
        ReschedulingState.ERROR: [ReschedulingState.INITIAL, ReschedulingState.ABORTED],
        ReschedulingState.ABORTED: [ReschedulingState.INITIAL]
    }
    
    def __init__(self, appointment_manager: AppointmentManager):
        self.appointment_manager = appointment_manager
        self.logger = logging.getLogger(__name__)
    
    def transition(self, current_state: ReschedulingState, next_state: ReschedulingState) -> bool:
        """Validate state transition"""
        if next_state not in self.TRANSITIONS.get(current_state, []):
            self.logger.warning(f"Invalid transition: {current_state} -> {next_state}")
            return False
        return True
    
    async def process_step(
        self,
        user_id: str,
        message: str,
        context: ReschedulingContext,
        jwt_token: Optional[str] = None
    ) -> Tuple[str, ReschedulingContext, List[str], Optional[Dict]]:
        """Process current step in rescheduling flow"""
        
        self.logger.info(f"Rescheduling step: {context.state} for user {user_id}")
        
        handlers = {
            ReschedulingState.INITIAL: self._handle_initial,
            ReschedulingState.FETCHING_APPOINTMENTS: self._handle_fetching,
            ReschedulingState.SELECTING_APPOINTMENT: self._handle_appointment_selection,
            ReschedulingState.SELECTING_NEW_DATE: self._handle_date_selection,
            ReschedulingState.SELECTING_NEW_TIME: self._handle_time_selection,
            ReschedulingState.CONFIRMING_RESCHEDULE: self._handle_confirmation,
            ReschedulingState.PROCESSING: self._handle_processing,
        }
        
        handler = handlers.get(context.state)
        if not handler:
            return ("Error in rescheduling flow", context, ["Start over"], None)
        
        return await handler(user_id, message, context, jwt_token)
    
    async def _handle_initial(
        self, user_id: str, message: str, context: ReschedulingContext, jwt_token: Optional[str]
    ) -> Tuple[str, ReschedulingContext, List[str], Optional[Dict]]:
        """Initial state"""
        
        if not jwt_token:
            return (
                "🔐 Please **log in** to reschedule your appointments.",
                context,
                ["Login"],
                None
            )
        
        if self.transition(context.state, ReschedulingState.FETCHING_APPOINTMENTS):
            context.state = ReschedulingState.FETCHING_APPOINTMENTS
            return await self._handle_fetching(user_id, message, context, jwt_token)
        
        return ("Error starting reschedule", context, [], None)
    
    async def _handle_fetching(
        self, user_id: str, message: str, context: ReschedulingContext, jwt_token: Optional[str]
    ) -> Tuple[str, ReschedulingContext, List[str], Optional[Dict]]:
        """Fetch user's appointments"""
        
        appointments_result = await self.appointment_manager.get_user_appointments(
            jwt_token,
            status="UPCOMING"
        )
        
        if not appointments_result.get("success"):
            if self.transition(context.state, ReschedulingState.ERROR):
                context.state = ReschedulingState.ERROR
            
            return (
                f"❌ {appointments_result.get('message', 'Unable to fetch appointments')}",
                context,
                ["Try again", "Exit"],
                None
            )
        
        appointments = appointments_result.get("data", [])
        
        if not appointments:
            if self.transition(context.state, ReschedulingState.COMPLETED):
                context.state = ReschedulingState.COMPLETED
            
            return (
                "You don't have any upcoming appointments to reschedule.",
                context,
                ["Book new appointment", "Exit"],
                None
            )
        
        context.user_appointments = appointments
        
        if self.transition(context.state, ReschedulingState.SELECTING_APPOINTMENT):
            context.state = ReschedulingState.SELECTING_APPOINTMENT
        
        response = "📋 **Your Upcoming Appointments:**\n\n"
        
        for i, apt in enumerate(appointments[:10], 1):
            response += (
                f"**{i}. Dr. {apt.get('doctorName', 'Doctor')}**\n"
                f"   📅 {apt.get('appointmentDate')} at {apt.get('appointmentTime')}\n"
                f"   🏥 {apt.get('specialty', 'N/A')}\n\n"
            )
        
        response += "Which appointment would you like to reschedule? (say the number)"
        
        return (
            response,
            context,
            [f"#{i}" for i in range(1, min(4, len(appointments) + 1))],
            {"appointments": appointments}
        )
    
    async def _handle_appointment_selection(
        self, user_id: str, message: str, context: ReschedulingContext, jwt_token: Optional[str]
    ) -> Tuple[str, ReschedulingContext, List[str], Optional[Dict]]:
        """Handle appointment selection"""
        
        index = self._extract_selection(message)
        
        if index is None or index >= len(context.user_appointments):
            return (
                f"Please select an appointment (1-{len(context.user_appointments)})",
                context,
                [f"#{i}" for i in range(1, min(4, len(context.user_appointments) + 1))],
                None
            )
        
        selected_apt = context.user_appointments[index]
        
        context.original_appointment_id = selected_apt.get('appointmentId')
        context.original_appointment_details = selected_apt
        context.original_date = selected_apt.get('appointmentDate')
        context.original_time = selected_apt.get('appointmentTime')
        context.doctor_id = selected_apt.get('doctorId')
        context.doctor_name = selected_apt.get('doctorName')
        
        if self.transition(context.state, ReschedulingState.SELECTING_NEW_DATE):
            context.state = ReschedulingState.SELECTING_NEW_DATE
        
        return (
            f"📅 **Current Appointment:**\n"
            f"Dr. {context.doctor_name}\n"
            f"{context.original_date} at {context.original_time}\n\n"
            "When would you like to reschedule to?\n"
            "(e.g., 'Tomorrow', 'Next Monday', or specific date)",
            context,
            ["Tomorrow", "Day after tomorrow", "Next week"],
            {"selected_appointment": selected_apt}
        )
    
    async def _handle_date_selection(
        self, user_id: str, message: str, context: ReschedulingContext, jwt_token: Optional[str]
    ) -> Tuple[str, ReschedulingContext, List[str], Optional[Dict]]:
        """Handle new date selection"""
        
        new_date = self.appointment_manager.parse_date_from_text(message)
        
        if not new_date:
            return (
                "Please provide a date (e.g., 'Tomorrow', 'Next Monday')",
                context,
                ["Tomorrow", "Day after tomorrow", "Next week"],
                None
            )
        
        # Same date as original
        if new_date == context.original_date:
            return (
                "⚠️ That's the same date as your current appointment.\n"
                "Please choose a different date.",
                context,
                ["Tomorrow", "Day after tomorrow", "Next week"],
                None
            )
        
        # Fetch available slots
        slots_result = await self.appointment_manager.get_available_slots(
            context.doctor_id,
            new_date
        )
        
        if not slots_result.get("success"):
            return (
                f"❌ {slots_result.get('message')}\nPlease try another date.",
                context,
                ["Tomorrow", "Try another date"],
                None
            )
        
        available_slots = slots_result.get("data", [])
        
        if not available_slots:
            return (
                f"No slots available on {new_date}. Try another date?",
                context,
                ["Tomorrow", "Day after tomorrow"],
                None
            )
        
        context.new_date = new_date
        context.available_slots = available_slots
        
        if self.transition(context.state, ReschedulingState.SELECTING_NEW_TIME):
            context.state = ReschedulingState.SELECTING_NEW_TIME
        
        formatted_slots = self.appointment_manager.format_available_slots(available_slots)
        
        return (
            f"✅ Available slots for **{new_date}**:\n\n{formatted_slots}\n\n"
            "Which time works for you?",
            context,
            available_slots[:4],
            {"available_slots": available_slots}
        )
    
    async def _handle_time_selection(
        self, user_id: str, message: str, context: ReschedulingContext, jwt_token: Optional[str]
    ) -> Tuple[str, ReschedulingContext, List[str], Optional[Dict]]:
        """Handle new time selection"""
        
        new_time = self.appointment_manager.parse_time_from_text(message)
        
        # Check if exact slot match
        if not new_time:
            for slot in context.available_slots:
                if slot.lower() in message.lower():
                    new_time = slot
                    break
        
        if not new_time:
            return (
                "Please select a time from available slots",
                context,
                context.available_slots[:4],
                None
            )
        
        # Validate time is available
        time_normalized = new_time if len(new_time.split(':')) == 3 else f"{new_time}:00"
        
        is_available = any(
            slot.startswith(time_normalized[:5]) or time_normalized.startswith(slot[:5])
            for slot in context.available_slots
        )
        
        if not is_available:
            return (
                f"'{new_time}' is not available. Please choose from:\n" +
                "\n".join(f"• {s}" for s in context.available_slots[:8]),
                context,
                context.available_slots[:4],
                None
            )
        
        context.new_time = time_normalized
        
        if self.transition(context.state, ReschedulingState.CONFIRMING_RESCHEDULE):
            context.state = ReschedulingState.CONFIRMING_RESCHEDULE
        
        return (
            "📋 **Reschedule Summary:**\n\n"
            f"**Current:**\n"
            f"📅 {context.original_date} at {context.original_time}\n\n"
            f"**New:**\n"
            f"📅 {context.new_date} at {self.appointment_manager._format_time_12hr(time_normalized)}\n\n"
            "Confirm reschedule?",
            context,
            ["✅ Confirm", "Change time", "Cancel"],
            {
                "reschedule_summary": {
                    "original_date": context.original_date,
                    "original_time": context.original_time,
                    "new_date": context.new_date,
                    "new_time": context.new_time
                }
            }
        )
    
    async def _handle_confirmation(
        self, user_id: str, message: str, context: ReschedulingContext, jwt_token: Optional[str]
    ) -> Tuple[str, ReschedulingContext, List[str], Optional[Dict]]:
        """Handle reschedule confirmation"""
        
        message_lower = message.lower()
        
        if any(w in message_lower for w in ['confirm', 'yes', 'reschedule']):
            if self.transition(context.state, ReschedulingState.PROCESSING):
                context.state = ReschedulingState.PROCESSING
                return await self._handle_processing(user_id, message, context, jwt_token)
        
        elif 'time' in message_lower:
            if self.transition(context.state, ReschedulingState.SELECTING_NEW_TIME):
                context.state = ReschedulingState.SELECTING_NEW_TIME
                context.new_time = None
                return await self._handle_time_selection(user_id, "show slots", context, jwt_token)
        
        elif 'cancel' in message_lower or 'abort' in message_lower:
            if self.transition(context.state, ReschedulingState.ABORTED):
                context.state = ReschedulingState.ABORTED
                context.reset()
                return (
                    "Reschedule cancelled. Your original appointment is unchanged.",
                    context,
                    ["View appointments", "Exit"],
                    None
                )
        
        return (
            "Please say 'Confirm' to reschedule, 'Change time', or 'Cancel'",
            context,
            ["Confirm", "Change time", "Cancel"],
            None
        )
    
    async def _handle_processing(
        self, user_id: str, message: str, context: ReschedulingContext, jwt_token: Optional[str]
    ) -> Tuple[str, ReschedulingContext, List[str], Optional[Dict]]:
        """Process the reschedule via API"""
        
        try:
            reschedule_result = await self.appointment_manager.reschedule_appointment(
                context.original_appointment_id,
                {
                    "newDate": context.new_date,
                    "newSlotTime": context.new_time
                },
                jwt_token
            )
            
            if reschedule_result.get("success"):
                if self.transition(context.state, ReschedulingState.COMPLETED):
                    context.state = ReschedulingState.COMPLETED
                
                return (
                    "🎉 **Appointment Rescheduled Successfully!**\n\n"
                    f"👨‍⚕️ **Doctor:** Dr. {context.doctor_name}\n"
                    f"📅 **New Date:** {context.new_date}\n"
                    f"🕐 **New Time:** {self.appointment_manager._format_time_12hr(context.new_time)}\n\n"
                    "📧 Confirmation email sent!",
                    context,
                    ["View appointments", "Done"],
                    {"rescheduled": True}
                )
            else:
                if self.transition(context.state, ReschedulingState.ERROR):
                    context.state = ReschedulingState.ERROR
                
                return (
                    f"❌ Reschedule failed: {reschedule_result.get('message')}",
                    context,
                    ["Try again", "Exit"],
                    None
                )
        
        except Exception as e:
            self.logger.error(f"Error rescheduling: {e}", exc_info=True)
            
            if self.transition(context.state, ReschedulingState.ERROR):
                context.state = ReschedulingState.ERROR
            
            return (
                "⚠️ Error rescheduling. Please try again.",
                context,
                ["Try again", "Contact support"],
                None
            )
    
    def _extract_selection(self, message: str) -> Optional[int]:
        """Extract number selection"""
        import re
        match = re.search(r'\b(\d+)\b', message)
        if match:
            return int(match.group(1)) - 1
        
        ordinals = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4}
        for word, idx in ordinals.items():
            if word in message.lower():
                return idx
        return None