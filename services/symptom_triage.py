import os
import google.generativeai as genai
from typing import Dict, List, Optional
from enum import Enum

class UrgencyLevel(Enum):
    EMERGENCY = "EMERGENCY"
    URGENT = "URGENT"
    ROUTINE = "ROUTINE"

class SymptomTriageService:
    """Analyzes symptoms and provides triage recommendations"""
    
    def __init__(self):
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
    
    def analyze_symptoms(self, symptoms: str, additional_info: Optional[str] = None) -> Dict:
        """
        Analyze symptoms and provide triage recommendation
        
        Args:
            symptoms: Description of symptoms from user
            additional_info: Additional context (duration, severity, etc.)
        
        Returns:
            Dict with urgency level, recommended specialty, and advice
        """
        if not self.model:
            return self._fallback_triage(symptoms)
        
        # Emergency keywords for quick detection
        emergency_keywords = [
            "chest pain", "difficulty breathing", "can't breathe", "severe bleeding",
            "stroke", "unconscious", "seizure", "severe headache", "suicide",
            "overdose", "severe burn", "choking", "heart attack"
        ]
        
        symptoms_lower = symptoms.lower()
        
        # Immediate emergency detection
        if any(keyword in symptoms_lower for keyword in emergency_keywords):
            return {
                "urgency": UrgencyLevel.EMERGENCY.value,
                "recommended_specialty": "Emergency Medicine",
                "advice": "⚠️ EMERGENCY: Please call emergency services (911/108) immediately or go to the nearest emergency room. Do not wait for an appointment.",
                "disclaimer": "This is an automated triage system and does not replace professional medical judgment."
            }
        
        # Use AI for nuanced analysis
        try:
            prompt = f"""You are a medical triage AI assistant. Analyze the following symptoms and provide a triage recommendation.

            Symptoms: {symptoms}
            {f"Additional Information: {additional_info}" if additional_info else ""}

            Based on these symptoms, provide:
            1. Urgency Level: EMERGENCY, URGENT, or ROUTINE
            2. Recommended Medical Specialty (e.g., Cardiology, Dermatology, General Practice, etc.)
            3. Brief advice (1-2 sentences)

            IMPORTANT Guidelines:
            - EMERGENCY: Life-threatening conditions requiring immediate care
            - URGENT: Serious conditions requiring care within 24 hours
            - ROUTINE: Non-urgent conditions that can be scheduled normally

            Respond in this exact JSON format:
            {{
                "urgency": "EMERGENCY/URGENT/ROUTINE",
                "recommended_specialty": "Specialty Name",
                "advice": "Your advice here"
            }}
            """
            
            response = self.model.generate_content(prompt)
            result = self._parse_ai_response(response.text)
            
            # Add disclaimer
            result["disclaimer"] = "This is an automated assessment and does not replace professional medical diagnosis. Please consult with a healthcare provider."
            
            # Add emergency warning if classified as emergency
            if result["urgency"] == UrgencyLevel.EMERGENCY.value:
                result["advice"] = f"⚠️ EMERGENCY: {result['advice']} Call emergency services immediately."
            
            return result
            
        except Exception as e:
            print(f"Error in AI triage: {e}")
            return self._fallback_triage(symptoms)
    
    def _parse_ai_response(self, response_text: str) -> Dict:
        """Parse AI response and extract triage information"""
        import json
        import re
        
        try:
            # Try to find JSON in response
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Validate urgency level
                if result.get("urgency") not in ["EMERGENCY", "URGENT", "ROUTINE"]:
                    result["urgency"] = "ROUTINE"
                
                return result
        except Exception as e:
            print(f"Error parsing AI response: {e}")
        
        # Fallback parsing
        return {
            "urgency": "ROUTINE",
            "recommended_specialty": "General Practice",
            "advice": "Please schedule an appointment with a doctor to discuss your symptoms."
        }
    
    def _fallback_triage(self, symptoms: str) -> Dict:
        """Fallback triage using rule-based system"""
        symptoms_lower = symptoms.lower()
        
        # Emergency keywords
        emergency_keywords = [
            "chest pain", "difficulty breathing", "severe bleeding", "stroke",
            "unconscious", "seizure", "heart attack"
        ]
        
        # Urgent keywords
        urgent_keywords = [
            "high fever", "severe pain", "vomiting", "can't eat", "severe", "acute"
        ]
        
        if any(kw in symptoms_lower for kw in emergency_keywords):
            return {
                "urgency": UrgencyLevel.EMERGENCY.value,
                "recommended_specialty": "Emergency Medicine",
                "advice": "⚠️ EMERGENCY: Call emergency services immediately.",
                "disclaimer": "This is an automated assessment. When in doubt, seek immediate medical attention."
            }
        elif any(kw in symptoms_lower for kw in urgent_keywords):
            return {
                "urgency": UrgencyLevel.URGENT.value,
                "recommended_specialty": "General Practice",
                "advice": "Please schedule an appointment within 24 hours.",
                "disclaimer": "This is an automated assessment and does not replace professional medical diagnosis."
            }
        else:
            return {
                "urgency": UrgencyLevel.ROUTINE.value,
                "recommended_specialty": "General Practice",
                "advice": "Please schedule a regular appointment to discuss your symptoms.",
                "disclaimer": "This is an automated assessment and does not replace professional medical diagnosis."
            }
    
    def get_specialty_keywords(self) -> Dict[str, List[str]]:
        """Map symptoms to potential specialties"""
        return {
            "Cardiology": ["chest pain", "heart", "palpitation", "irregular heartbeat", "shortness of breath"],
            "Dermatology": ["skin", "rash", "acne", "mole", "itching", "eczema"],
            "Orthopedics": ["bone", "joint", "fracture", "sprain", "back pain", "knee pain"],
            "ENT": ["ear", "nose", "throat", "sinus", "hearing", "tinnitus"],
            "Gastroenterology": ["stomach", "digestion", "abdominal pain", "diarrhea", "constipation"],
            "Neurology": ["headache", "migraine", "dizziness", "numbness", "tingling"],
            "Ophthalmology": ["eye", "vision", "blurry", "eye pain"],
            "Psychiatry": ["anxiety", "depression", "stress", "mental health", "sleep problems"]
        }
