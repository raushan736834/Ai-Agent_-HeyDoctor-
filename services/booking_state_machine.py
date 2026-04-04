# booking_state_machine.py
from typing import Tuple, Optional, Dict, List, Any
from models.state import BookingState, BookingContext
from models.api import ChatResponse
from appointment_manager import AppointmentManager
import logging


class BookingStateMachine:
    """Finite State Machine for appointment booking"""

    # Valid state transitions
    TRANSITIONS = {
        BookingState.INITIAL: [BookingState.SELECTING_SPECIALTY, BookingState.SELECTING_DOCTOR],
        BookingState.SELECTING_SPECIALTY: [BookingState.SELECTING_DOCTOR, BookingState.CANCELLED],
        BookingState.SELECTING_DOCTOR: [BookingState.SELECTING_DATE, BookingState.SELECTING_SPECIALTY,
                                        BookingState.CANCELLED],
        BookingState.SELECTING_DATE: [BookingState.SELECTING_TIME, BookingState.SELECTING_DOCTOR,
                                      BookingState.CANCELLED],
        BookingState.SELECTING_TIME: [BookingState.CONFIRMING, BookingState.SELECTING_DATE, BookingState.CANCELLED],
        BookingState.CONFIRMING: [BookingState.PROCESSING, BookingState.SELECTING_TIME, BookingState.CANCELLED],
        BookingState.PROCESSING: [BookingState.COMPLETED, BookingState.ERROR],
        BookingState.COMPLETED: [BookingState.INITIAL],
        BookingState.ERROR: [BookingState.INITIAL, BookingState.CANCELLED],
        BookingState.CANCELLED: [BookingState.INITIAL]
    }


    def __init__(self, appointment_manager: AppointmentManager):
        self.appointment_manager = appointment_manager
        self.logger = logging.getLogger(__name__)

    def transition(self, current_state: BookingState, next_state: BookingState) -> bool:
        """Validate and perform state transition"""
        if next_state not in self.TRANSITIONS.get(current_state, []):
            self.logger.warning(
                f"Invalid state transition: {current_state} -> {next_state}"
            )
            return False
        return True

    async def process_step(
            self,
            user_id: str,
            message: str,
            context: BookingContext,
            jwt_token: Optional[str] = None
    ) -> Tuple[str, BookingContext, List[str], Optional[Dict]]:
        """
        Process current step in booking flow

        Returns:
            Tuple of (response_text, updated_context, suggestions, action_data)
        """
        self.logger.info(f"Processing booking step: {context.state} for user {user_id}")

        # Route to appropriate handler based on current state
        handlers = {
            BookingState.INITIAL: self._handle_initial,
            BookingState.SELECTING_SPECIALTY: self._handle_specialty_selection,
            BookingState.SELECTING_DOCTOR: self._handle_doctor_selection,
            BookingState.SELECTING_DATE: self._handle_date_selection,
            BookingState.SELECTING_TIME: self._handle_time_selection,
            BookingState.CONFIRMING: self._handle_confirmation,
            BookingState.PROCESSING: self._handle_processing,
        }

        handler = handlers.get(context.state)
        if not handler:
            return (
                "I'm not sure what step we're on. Let's start over.",
                context,
                ["Start over"],
                None
            )

        return await handler(user_id, message, context, jwt_token)

    async def _handle_initial(
            self, user_id: str, message: str, context: BookingContext, jwt_token: Optional[str]
    ) -> Tuple[str, BookingContext, List[str], Optional[Dict]]:
        """Initial state - determine if user has specialty in mind"""

        # Check if JWT token is present
        if not jwt_token:
            return (
                "To book an appointment, please **log in** to your account first.\n\n"
                "Once logged in, I can help you find the perfect doctor and schedule your visit!",
                context,
                ["Login", "Learn more"],
                None
            )

        # Try to extract specialty or doctor name
        keyword = self.appointment_manager._extract_search_keyword(message)

        if keyword:
            # User mentioned a specialty - go directly to doctor search
            context.search_keyword = keyword

            if self.transition(context.state, BookingState.SELECTING_DOCTOR):
                context.state = BookingState.SELECTING_DOCTOR
                return await self._handle_doctor_selection(user_id, message, context, jwt_token)

        # No specialty mentioned - ask for it
        if self.transition(context.state, BookingState.SELECTING_SPECIALTY):
            context.state = BookingState.SELECTING_SPECIALTY

        specialists = await self.appointment_manager.get_specialists()
        top_specialties = [s.get('specialist', '') for s in specialists[:6]]

        return (
            "I'd be happy to help you book an appointment!\n\n"
            "**Which type of doctor are you looking for?**\n"
            "You can choose from our specialties or tell me what you need.",
            context,
            top_specialties[:4],  # Top 4 as quick replies
            {"specialists": specialists}
        )

    async def _handle_specialty_selection(
            self, user_id: str, message: str, context: BookingContext, jwt_token: Optional[str]
    ) -> Tuple[str, BookingContext, List[str], Optional[Dict]]:
        """Handle specialty selection"""

        keyword = self.appointment_manager._extract_search_keyword(message)

        if not keyword:
            return (
                "Please tell me which specialty you're looking for.\n"
                "For example: 'Cardiologist', 'Dermatologist', 'Dentist'",
                context,
                ["Cardiologist", "Dermatologist", "Dentist", "General Physician"],
                None
            )

        context.search_keyword = keyword

        # Transition to doctor selection
        if self.transition(context.state, BookingState.SELECTING_DOCTOR):
            context.state = BookingState.SELECTING_DOCTOR
            return await self._handle_doctor_selection(user_id, message, context, jwt_token)

        return "Error transitioning state", context, [], None

    async def _handle_doctor_selection(
            self, user_id: str, message: str, context: BookingContext, jwt_token: Optional[str]
    ) -> Tuple[str, BookingContext, List[str], Optional[Dict]]:
        """Handle doctor search and selection"""

        # Check if user selected a doctor by number or name
        doctor_id = self._extract_doctor_selection(message, context)

        if doctor_id:
            # Doctor selected - validate and move to date selection
            doctor_result = await self.appointment_manager.get_doctor_by_id(doctor_id)

            if doctor_result.get("success"):
                doctor_data = doctor_result.get("data")
                context.selected_doctor_id = doctor_id
                context.selected_doctor_name = (
                    f"Dr. {doctor_data.get('firstName', '')} {doctor_data.get('lastName', '')}"
                )

                # Transition to date selection
                if self.transition(context.state, BookingState.SELECTING_DATE):
                    context.state = BookingState.SELECTING_DATE

                return (
                    f"Great choice! You've selected **{context.selected_doctor_name}** "
                    f"({doctor_data.get('specialist', 'Specialist')}).\n\n"
                    f"**When would you like to schedule your appointment?**\n"
                    f"You can say 'tomorrow', 'next Monday', or provide a specific date.",
                    context,
                    ["Tomorrow", "Day after tomorrow", "Next Monday", "Choose date"],
                    {"selected_doctor": doctor_data}
                )
            else:
                return (
                    "I couldn't find that doctor. Please try selecting again.",
                    context,
                    ["Show doctors again", "Start over"],
                    None
                )

        # No selection yet - search for doctors
        keyword = context.search_keyword or self.appointment_manager._extract_search_keyword(message)

        if not keyword:
            return (
                "Which doctor would you like to see? You can search by:\n"
                "• Specialty (e.g., 'Cardiologist')\n"
                "• Doctor name\n"
                "• City or location",
                context,
                ["Cardiologist", "Dermatologist", "General Physician"],
                None
            )

        # Search doctors
        search_result = await self.appointment_manager.search_doctors(keyword)

        if not search_result.get("success"):
            error_code = search_result.get("error_code")

            if error_code == "NOT_FOUND":
                specialists = await self.appointment_manager.get_specialists()
                specialist_names = [s.get('specialist', '') for s in specialists[:8]]

                return (
                    f"No doctors found for '{keyword}'.\n\n"
                    f"**Available specialties:**\n" +
                    "\n".join(f"• {s}" for s in specialist_names[:6]) +
                    "\n\nPlease choose one of these or try a different search.",
                    context,
                    specialist_names[:4],
                    {"specialists": specialists}
                )

            return (
                f"{search_result.get('message', 'Error searching doctors')}",
                context,
                ["Try again", "Start over"],
                None
            )

        doctors = search_result.get("data", [])

        if not doctors:
            return (
                "No doctors available at the moment. Please try again later.",
                context,
                ["Try different specialty", "Start over"],
                None
            )

        # Store available doctors in context
        context.available_doctors = doctors[:10]

        # Format doctor list
        response = f"**Found {len(doctors)} doctor(s) for '{keyword}':**\n\n"

        for i, doc in enumerate(doctors[:5], 1):
            response += (
                f"**{i}. Dr. {doc.get('firstName', '')} {doc.get('lastName', '')}**\n"
                f"   • Specialty: {doc.get('specialist', 'N/A')}\n"
                f"   • Experience: {doc.get('experience', 'N/A')} years\n"
                f"   • Fee: ₹{doc.get('consultationFee', 'N/A')}\n"
                f"   • Location: {doc.get('city', 'N/A')}\n\n"
            )

        if len(doctors) > 5:
            response += f"_...and {len(doctors) - 5} more doctors available_\n\n"

        response += "**Please select a doctor by saying the number** (e.g., '1' or 'First one')"

        suggestions = [f"Doctor {i}" for i in range(1, min(4, len(doctors) + 1))]

        return (
            response,
            context,
            suggestions,
            {"doctors": doctors[:5]}
        )

    def _extract_doctor_selection(self, message: str, context: BookingContext) -> Optional[str]:
        """Extract doctor selection from user message"""
        import re

        message_lower = message.lower()

        # Check for number selection (1, 2, 3, etc.)
        number_match = re.search(r'\b(\d+)\b', message)
        if number_match:
            index = int(number_match.group(1)) - 1  # Convert to 0-based index
            if 0 <= index < len(context.available_doctors):
                return context.available_doctors[index].get('doctorId')

        # Check for ordinal words (first, second, etc.)
        ordinals = {
            'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4,
            '1st': 0, '2nd': 1, '3rd': 2, '4th': 3, '5th': 4
        }

        for word, index in ordinals.items():
            if word in message_lower:
                if index < len(context.available_doctors):
                    return context.available_doctors[index].get('doctorId')

        return None

    async def _handle_date_selection(
            self, user_id: str, message: str, context: BookingContext, jwt_token: Optional[str]
    ) -> Tuple[str, BookingContext, List[str], Optional[Dict]]:
        """Handle date selection and fetch available slots"""

        # Parse date from message
        date = self.appointment_manager.parse_date_from_text(message)

        if not date:
            return (
                "Please provide a date for your appointment.\n\n"
                "You can say:\n"
                "• 'Tomorrow'\n"
                "• 'Next Monday'\n"
                "• Or provide a specific date like '2024-04-15'",
                context,
                ["Tomorrow", "Day after tomorrow", "Next Monday"],
                None
            )

        # Fetch available slots
        slots_result = await self.appointment_manager.get_available_slots(
            context.selected_doctor_id,
            date
        )

        if not slots_result.get("success"):
            error_code = slots_result.get("error_code")

            if error_code == "PAST_DATE":
                return (
                    "Cannot book appointments for past dates.\n"
                    "Please select a future date.",
                    context,
                    ["Tomorrow", "Day after tomorrow", "Next week"],
                    None
                )
            elif error_code == "NO_SLOTS_FOUND":
                return (
                    f"No available slots on **{date}**.\n\n"
                    "Would you like to try another date?",
                    context,
                    ["Tomorrow", "Day after tomorrow", "Next week"],
                    None
                )
            else:
                context.retry_count += 1
                if context.retry_count > 3:
                    context.state = BookingState.ERROR
                    return (
                        "I'm having trouble fetching available slots. "
                        "Please try again later or contact support.",
                        context,
                        ["Start over"],
                        None
                    )

                return (
                    f"{slots_result.get('message')}. Please try another date.",
                    context,
                    ["Tomorrow", "Try again"],
                    None
                )

        available_slots = slots_result.get("data", [])

        if not available_slots:
            return (
                f"No slots available on {date}. Please choose another date.",
                context,
                ["Tomorrow", "Day after tomorrow", "Next week"],
                None
            )

        # Update context
        context.selected_date = date
        context.available_slots = available_slots

        # Transition to time selection
        if self.transition(context.state, BookingState.SELECTING_TIME):
            context.state = BookingState.SELECTING_TIME

        # Format slots
        formatted_slots = self.appointment_manager.format_available_slots(available_slots)

        return (
            f"Great! Here are the available time slots for **{date}**:\n\n"
            f"{formatted_slots}\n\n"
            f"**Which time works best for you?**\n"
            f"You can say the time like '3:00 PM' or '15:00'",
            context,
            available_slots[:4],  # Show first 4 as quick replies
            {"available_slots": available_slots, "date": date}
        )

    async def _handle_time_selection(
            self, user_id: str, message: str, context: BookingContext, jwt_token: Optional[str]
    ) -> Tuple[str, BookingContext, List[str], Optional[Dict]]:
        """Handle time slot selection"""

        # Parse time from message
        time = self.appointment_manager.parse_time_from_text(message)

        # Also check if user selected from available slots
        if not time:
            message_lower = message.lower()
            for slot in context.available_slots:
                if slot.lower() in message_lower:
                    time = slot
                    break

        if not time:
            return (
                "Please select a time slot.\n\n"
                "Available slots:\n" +
                "\n".join(f"• {slot}" for slot in context.available_slots[:8]) +
                "\n\nYou can also say the time like '3:00 PM'",
                context,
                context.available_slots[:4],
                None
            )

        # Validate that selected time is in available slots
        # Normalize time format for comparison
        time_normalized = time
        if len(time.split(':')) == 2:
            time_normalized = f"{time}:00"

        # Check if time is available
        is_available = any(
            slot.startswith(time_normalized[:5]) or time_normalized.startswith(slot[:5])
            for slot in context.available_slots
        )

        if not is_available:
            return (
                f"The time '{time}' is not available.\n\n"
                "Please choose from the available slots:\n" +
                "\n".join(f"• {slot}" for slot in context.available_slots[:8]),
                context,
                context.available_slots[:4],
                None
            )

        # Update context
        context.selected_time = time_normalized

        # Transition to confirmation
        if self.transition(context.state, BookingState.CONFIRMING):
            context.state = BookingState.CONFIRMING

        return (
            "📋 **Please confirm your appointment details:**\n\n"
            f"👨‍⚕️ **Doctor:** {context.selected_doctor_name}\n"
            f"📅 **Date:** {context.selected_date}\n"
            f"🕐 **Time:** {self.appointment_manager._format_time_12hr(time_normalized)}\n\n"
            "Is this correct? Say 'Confirm' to book or 'Change' to modify.",
            context,
            ["Confirm", "Change time", "Change date", "Cancel"],
            {
                "booking_summary": {
                    "doctor": context.selected_doctor_name,
                    "doctor_id": context.selected_doctor_id,
                    "date": context.selected_date,
                    "time": context.selected_time
                }
            }
        )

    async def _handle_confirmation(
            self, user_id: str, message: str, context: BookingContext, jwt_token: Optional[str]
    ) -> Tuple[str, BookingContext, List[str], Optional[Dict]]:
        """Handle appointment confirmation"""

        message_lower = message.lower()

        # Check for confirmation
        if any(word in message_lower for word in ['confirm', 'yes', 'book', 'proceed']):
            # Transition to processing
            if self.transition(context.state, BookingState.PROCESSING):
                context.state = BookingState.PROCESSING
                return await self._handle_processing(user_id, message, context, jwt_token)

        # Check for modifications
        elif 'time' in message_lower or 'slot' in message_lower:
            if self.transition(context.state, BookingState.SELECTING_TIME):
                context.state = BookingState.SELECTING_TIME
                context.selected_time = None

                formatted_slots = self.appointment_manager.format_available_slots(
                    context.available_slots
                )

                return (
                    f"Available slots for {context.selected_date}:\n\n{formatted_slots}\n\n"
                    "Which time would you prefer?",
                    context,
                    context.available_slots[:4],
                    None
                )

        elif 'date' in message_lower:
            if self.transition(context.state, BookingState.SELECTING_DATE):
                context.state = BookingState.SELECTING_DATE
                context.selected_date = None
                context.selected_time = None
                context.available_slots = []

                return (
                    "When would you like to schedule the appointment?",
                    context,
                    ["Tomorrow", "Day after tomorrow", "Next week"],
                    None
                )

        elif 'cancel' in message_lower:
            if self.transition(context.state, BookingState.CANCELLED):
                context.state = BookingState.CANCELLED
                context.reset()

                return (
                    "Booking cancelled. Is there anything else I can help you with?",
                    context,
                    ["Find another doctor", "Check symptoms", "Exit"],
                    None
                )

        # Invalid response
        return (
            "Please confirm your appointment by saying:\n"
            "• 'Confirm' or 'Yes' to book\n"
            "• 'Change time' or 'Change date' to modify\n"
            "• 'Cancel' to start over",
            context,
            ["Confirm", "Change time", "Cancel"],
            None
        )

    async def _handle_processing(
            self, user_id: str, message: str, context: BookingContext, jwt_token: Optional[str]
    ) -> Tuple[str, BookingContext, List[str], Optional[Dict]]:
        """Process the actual booking via API"""

        try:
            # Make API call to book appointment
            booking_payload = {
                "doctorId": context.selected_doctor_id,
                "date": context.selected_date,
                "slotTime": context.selected_time
            }

            # This would be the actual API call
            booking_result = await self.appointment_manager.book_appointment(
                booking_payload,
                jwt_token
            )

            if booking_result.get("success"):
                appointment_data = booking_result.get("data", {})
                context.appointment_id = appointment_data.get("appointmentId")

                # Transition to completed
                if self.transition(context.state, BookingState.COMPLETED):
                    context.state = BookingState.COMPLETED

                return (
                    "🎉 **Appointment Booked Successfully!**\n\n"
                    f"📋 **Appointment ID:** {context.appointment_id}\n"
                    f"👨‍⚕️ **Doctor:** {context.selected_doctor_name}\n"
                    f"📅 **Date:** {context.selected_date}\n"
                    f"🕐 **Time:** {self.appointment_manager._format_time_12hr(context.selected_time)}\n\n"
                    "📧 You will receive a confirmation email and SMS shortly.\n"
                    "💡 You can view your appointment in 'My Appointments'.",
                    context,
                    ["View appointments", "Book another", "Done"],
                    {
                        "appointment": appointment_data,
                        "booking_confirmed": True
                    }
                )
            else:
                # Booking failed
                if self.transition(context.state, BookingState.ERROR):
                    context.state = BookingState.ERROR
                    context.error_message = booking_result.get("message")

                return (
                    f" **Booking Failed**\n\n"
                    f"{booking_result.get('message', 'An error occurred during booking')}\n\n"
                    "Would you like to try again?",
                    context,
                    ["Try again", "Choose different time", "Start over"],
                    None
                )

        except Exception as e:
            self.logger.error(f"Error processing booking: {e}", exc_info=True)

            if self.transition(context.state, BookingState.ERROR):
                context.state = BookingState.ERROR
                context.error_message = str(e)

            return (
                " An unexpected error occurred while booking your appointment.\n"
                "Please try again or contact support.",
                context,
                ["Try again", "Contact support"],
                None
            )