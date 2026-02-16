import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dateutil import parser
from enum import Enum
import re
import logging

class BookingState(Enum):
    INITIAL = "INITIAL"
    SELECT_SPECIALTY = "SELECT_SPECIALTY"
    SELECT_DOCTOR = "SELECT_DOCTOR"
    SELECT_DATE = "SELECT_DATE"
    SELECT_TIME = "SELECT_TIME"
    CONFIRM = "CONFIRM"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"

class AppointmentManager:
    """Manages multi-turn appointment booking flow"""
    
    def __init__(self, backend_url: str):
        self.backend_url = backend_url.rstrip('/')
        self.logger = logging.getLogger(__name__)
    
    def search_doctors(self, keyword: str) -> Dict[str, Any]:
        """Search for doctors by keyword (name, specialty, city)"""
        # Validate input
        if not keyword or not keyword.strip():
            return {
                "success": False,
                "message": "Search keyword cannot be empty",
                "data": [],
                "error_code": "INVALID_KEYWORD"
            }
        
        keyword = keyword.strip()
        if len(keyword) < 2:
            return {
                "success": False,
                "message": "Search keyword must be at least 2 characters long",
                "data": [],
                "error_code": "KEYWORD_TOO_SHORT"
            }
        
        try:
            response = requests.get(
                f"{self.backend_url}/api/public/search",
                params={"keyword": keyword},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                doctors = data.get("data", [])
                return {
                    "success": True,
                    "message": f"Found {len(doctors)} doctor(s)",
                    "data": doctors
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "message": f"No doctors found for '{keyword}'",
                    "data": [],
                    "error_code": "NOT_FOUND"
                }
            else:
                return {
                    "success": False,
                    "message": f"Server error while searching doctors (Status: {response.status_code})",
                    "data": [],
                    "error_code": "SERVER_ERROR"
                }
        except requests.exceptions.Timeout:
            self.logger.error("Timeout while searching doctors")
            return {
                "success": False,
                "message": "Request timeout. Please try again.",
                "data": [],
                "error_code": "TIMEOUT"
            }
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error searching doctors: {e}", exc_info=True)
            return {
                "success": False,
                "message": "Unable to connect to the server. Please check your connection.",
                "data": [],
                "error_code": "NETWORK_ERROR"
            }
        except Exception as e:
            self.logger.error(f"Error searching doctors: {e}", exc_info=True)
            return {
                "success": False,
                "message": "An unexpected error occurred while searching doctors",
                "data": [],
                "error_code": "UNKNOWN_ERROR"
            }
    
    def get_doctor_by_id(self, doctor_id: str) -> Dict[str, Any]:
        """Get doctor details by ID"""
        # Validate input
        if not doctor_id or not doctor_id.strip():
            return {
                "success": False,
                "message": "Doctor ID cannot be empty",
                "data": None,
                "error_code": "INVALID_DOCTOR_ID"
            }
        
        try:
            response = requests.get(
                f"{self.backend_url}/api/public/getDoctor/{doctor_id.strip()}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "message": "Doctor found successfully",
                    "data": data.get("data")
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "message": f"Doctor with ID '{doctor_id}' not found",
                    "data": None,
                    "error_code": "DOCTOR_NOT_FOUND"
                }
            else:
                return {
                    "success": False,
                    "message": f"Server error while fetching doctor (Status: {response.status_code})",
                    "data": None,
                    "error_code": "SERVER_ERROR"
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "message": "Request timeout. Please try again.",
                "data": None,
                "error_code": "TIMEOUT"
            }
        except Exception as e:
            self.logger.error(f"Error getting doctor: {e}", exc_info=True)
            return {
                "success": False,
                "message": "An unexpected error occurred while fetching doctor details",
                "data": None,
                "error_code": "UNKNOWN_ERROR"
            }
    
    def get_specialists(self) -> List[Dict]:
        """Get list of all specialties"""
        try:
            response = requests.get(
                f"{self.backend_url}/api/public/getSpecialist",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            return []
        except Exception as e:
            self.logger.error(f"Error getting specialists: {e}", exc_info=True)
            return []
    
    def get_available_slots(self, doctor_id: str, date: str) -> Dict[str, Any]:
        """Get available time slots for a doctor on a specific date"""
        # Validate inputs
        if not doctor_id or not doctor_id.strip():
            return {
                "success": False,
                "message": "Doctor ID cannot be empty",
                "data": [],
                "error_code": "INVALID_DOCTOR_ID"
            }
        
        if not date or not date.strip():
            return {
                "success": False,
                "message": "Date cannot be empty",
                "data": [],
                "error_code": "INVALID_DATE"
            }
        
        # Validate date format (ISO format YYYY-MM-DD)
        import re
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date.strip()):
            return {
                "success": False,
                "message": "Date must be in YYYY-MM-DD format",
                "data": [],
                "error_code": "INVALID_DATE_FORMAT"
            }
        
        try:
            # Validate date is not in the past
            from datetime import datetime
            date_obj = datetime.strptime(date.strip(), "%Y-%m-%d").date()
            if date_obj < datetime.now().date():
                return {
                    "success": False,
                    "message": "Cannot book appointments for past dates",
                    "data": [],
                    "error_code": "PAST_DATE"
                }
        except ValueError:
            return {
                "success": False,
                "message": "Invalid date value",
                "data": [],
                "error_code": "INVALID_DATE_VALUE"
            }
        
        try:
            response = requests.get(
                f"{self.backend_url}/api/slots",
                params={"doctorId": doctor_id.strip(), "date": date.strip()},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                slots_data = data.get("data", [])
                
                # Extract only available slots (status = "AVAILABLE")
                available_slots = [
                    slot["slotTime"] 
                    for slot in slots_data 
                    if slot.get("status") == "AVAILABLE"
                ]
                
                return {
                    "success": True,
                    "message": f"Found {len(available_slots)} available slot(s)",
                    "data": available_slots
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "message": f"No slots found for the selected date",
                    "data": [],
                    "error_code": "NO_SLOTS_FOUND"
                }
            else:
                return {
                    "success": False,
                    "message": f"Server error while fetching slots (Status: {response.status_code})",
                    "data": [],
                    "error_code": "SERVER_ERROR"
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "message": "Request timeout. Please try again.",
                "data": [],
                "error_code": "TIMEOUT"
            }
        except Exception as e:
            self.logger.error(f"Error getting slots: {e}", exc_info=True)
            return {
                "success": False,
                "message": "An unexpected error occurred while fetching available slots",
                "data": [],
                "error_code": "UNKNOWN_ERROR"
            }
    
    def parse_date_from_text(self, text: str) -> Optional[str]:
        """Parse natural language date into ISO format"""
        text_lower = text.lower()
        today = datetime.now().date()
        
        # Handle relative dates
        if "today" in text_lower:
            return today.isoformat()
        elif "tomorrow" in text_lower:
            return (today + timedelta(days=1)).isoformat()
        elif "day after tomorrow" in text_lower:
            return (today + timedelta(days=2)).isoformat()
        elif "next week" in text_lower:
            return (today + timedelta(days=7)).isoformat()
        
        # Handle specific days
        days_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        
        for day_name, day_num in days_map.items():
            if day_name in text_lower:
                days_ahead = day_num - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return (today + timedelta(days=days_ahead)).isoformat()
        
        # Try to parse date directly
        try:
            # Extract date-like patterns
            date_match = re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', text)
            if date_match:
                parsed_date = parser.parse(date_match.group(), dayfirst=True)
                return parsed_date.date().isoformat()
        except Exception:
            pass
        
        return None
    
    def parse_time_from_text(self, text: str) -> Optional[str]:
        """Parse natural language time into HH:MM:SS format"""
        text_lower = text.lower()
        
        # Try to find time patterns
        # Pattern: 3pm, 3:30pm, 15:00, etc.
        time_patterns = [
            r'(\d{1,2})\s*(am|pm)',
            r'(\d{1,2}):(\d{2})\s*(am|pm)',
            r'(\d{1,2}):(\d{2})',
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    if 'am' in text_lower or 'pm' in text_lower:
                        # 12-hour format
                        hour = int(match.group(1))
                        minute = int(match.group(2)) if len(match.groups()) > 2 else 0
                        
                        if 'pm' in text_lower and hour != 12:
                            hour += 12
                        elif 'am' in text_lower and hour == 12:
                            hour = 0
                        
                        return f"{hour:02d}:{minute:02d}:00"
                    else:
                        # 24-hour format
                        hour = int(match.group(1))
                        minute = int(match.group(2)) if len(match.groups()) > 1 else 0
                        return f"{hour:02d}:{minute:02d}:00"
                except Exception:
                    continue
        
        return None
    
    def extract_booking_info(self, message: str, current_context: Dict) -> Dict:
        """
        Extract booking information from user message
        Updates the booking context with new information found
        """
        updates = {}
        
        # Try to extract date
        if "date" not in current_context or not current_context.get("date"):
            date = self.parse_date_from_text(message)
            if date:
                updates["date"] = date
        
        # Try to extract time
        if "time" not in current_context or not current_context.get("time"):
            time = self.parse_time_from_text(message)
            if time:
                updates["time"] = time
        
        return updates
    
    def format_doctor_info(self, doctor: Dict) -> str:
        """Format doctor information for display"""
        return (
            f"Dr. {doctor.get('firstName', '')} {doctor.get('lastName', '')} "
            f"({doctor.get('specialist', 'General Practitioner')})"
        )
    
    def format_available_slots(self, slots: List[str]) -> str:
        """Format available time slots for display"""
        if not slots:
            return "No available slots"
        
        # Group by AM/PM
        am_slots = [s for s in slots if int(s.split(':')[0]) < 12]
        pm_slots = [s for s in slots if int(s.split(':')[0]) >= 12]
        
        result = []
        if am_slots:
            formatted_am = [self._format_time_12hr(s) for s in am_slots[:5]]
            result.append(f"Morning: {', '.join(formatted_am)}")
        
        if pm_slots:
            formatted_pm = [self._format_time_12hr(s) for s in pm_slots[:5]]
            result.append(f"Afternoon/Evening: {', '.join(formatted_pm)}")
        
        return "\n".join(result)
    
    def _format_time_12hr(self, time_24hr: str) -> str:
        """Convert 24-hour time to 12-hour format"""
        hour, minute, _ = time_24hr.split(':')
        hour = int(hour)
        
        if hour == 0:
            return f"12:{minute} AM"
        elif hour < 12:
            return f"{hour}:{minute} AM"
        elif hour == 12:
            return f"12:{minute} PM"
        else:
            return f"{hour-12}:{minute} PM"
