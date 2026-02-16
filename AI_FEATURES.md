# AI Medical Appointment Agent - Features & Documentation

## Overview

This AI agent provides intelligent conversation-based assistance for medical appointment booking and patient queries. It uses Google's Gemini AI for natural language understanding and integrates seamlessly with the Spring Boot backend.

## ✨ Key Features

### 1. **Intelligent Conversation**
- Natural language understanding using Gemini 1.5 Flash
- Multi-turn conversation with context awareness
- Session-based conversation history (Redis or in-memory)
- Intent classification for accurate response routing

### 2. **Appointment Booking**
- Multi-step booking flow (Doctor → Date → Time → Confirm)
- Natural language date parsing ("tomorrow", "next Monday", etc.)
- Time slot availability checking
- Integration with backend booking API

### 3. **Doctor Search**
- Search by specialty (e.g., "cardiologist", "dermatologist")
- Search by doctor name or location
- Display doctor details (experience, fees, location)
- List available specialists

### 4. **Symptom Triage** 🏥
- AI-powered symptom analysis
- Urgency classification:
  - **EMERGENCY**: Life-threatening conditions → Immediate care advice
  - **URGENT**: Serious conditions → 24-hour appointment recommendation
  - **ROUTINE**: Non-urgent → Regular appointment scheduling
- Specialist recommendations based on symptoms
- Medical disclaimer for safety

### 5. **Session Management**
- Redis-based persistent sessions (falls back to in-memory)
- Conversation history tracking
- Context preservation across messages
- Session endpoints for start/end/view

### 6. **Backend Integration**
- Seamless integration with Spring Boot APIs
- JWT token support for authenticated requests
- CORS configured for frontend access
- RESTful API communication

## 📋 Supported Intents

| Intent | Description | Example Queries |
|--------|-------------|-----------------|
| `GREETING` | Initial greetings | "Hello", "Hi" |
| `SYMPTOM_CHECK` | Symptom analysis | "I have chest pain" |
| `SEARCH_DOCTOR` | Find doctors | "Find a cardiologist" |
| `BOOK_APPOINTMENT` | Book appointments | "Book appointment with Dr. Smith" |
| `CHECK_AVAILABILITY` | Check slots | "Is Dr. Smith available tomorrow?" |
| `CANCEL_POLICY` | Cancellation info | "What's your cancellation policy?" |
| `VIEW_APPOINTMENTS` | View bookings | "Show my appointments" |
| `FAREWELL` | End conversation | "Goodbye", "Thanks" |

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))
- Redis (optional, for persistent sessions)
- Spring Boot backend running on port 9090

### Installation

1. **Navigate to ai-agent directory:**
   ```bash
   cd ai-agent
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   # Copy .env.example to .env
   copy .env.example .env
   
   # Edit .env and add your Gemini API key
   GEMINI_API_KEY=your_actual_api_key_here
   ```

5. **Run the AI agent:**
   ```bash
   # Option 1: Using the batch file (Windows)
   ..\run_agent.bat
   
   # Option 2: Directly with Python
   python main.py
   ```

The service will start on `http://localhost:8000`

### Backend Configuration

Add this property to your Spring Boot `application.properties`:

```properties
ai.agent.url=http://localhost:8000
```

The backend `ChatController` is already configured to forward requests to the AI agent.

## 📡 API Endpoints

### Chat Endpoint
```http
POST /chat
Content-Type: application/json

{
  "user_id": "user@example.com",
  "message": "I need a cardiologist"
}

Response:
{
  "response": "I found 3 cardiologists...",
  "intent": "SEARCH_DOCTOR",
  "data": { "doctors": [...] },
  "suggestions": ["Book with Dr. Smith", "Book with Dr. Johnson"]
}
```

### Session Management
```http
POST /session/start?user_id=user123
GET /session/{user_id}
POST /session/end?user_id=user123
DELETE /history/{user_id}
```

### Health Check
```http
GET /health

Response:
{
  "status": "ok",
  "service": "AI Medical Appointment Agent",
  "gemini_api": "OK",
  "backend_url": "http://localhost:9090",
  "version": "1.0.0"
}
```

## 💬 Example Conversations

### Booking Flow
```
User: Hi
AI: Hello! I'm your AI medical appointment assistant. How can I help you today?

User: I need a cardiologist
AI: I found 3 cardiologists:
    1. Dr. Smith - 15 years experience - ₹500
    2. Dr. Johnson - 10 years experience - ₹600
    Would you like to book with any of these doctors?

User: Book with Dr. Smith tomorrow at 3pm
AI: Great! Here are available slots for tomorrow:
    Morning: 9:00 AM, 10:00 AM
    Afternoon: 2:00 PM, 3:00 PM, 4:00 PM
    
User: 3 PM
AI: Perfect! Your appointment is confirmed:
    📅 Date: 2026-01-29
    🕐 Time: 3:00 PM
    👨‍⚕️ Doctor: Dr. Smith
```

### Symptom Triage
```
User: I have severe chest pain and difficulty breathing
AI: ⚠️ EMERGENCY: This requires immediate medical attention. 
    Please call emergency services (911/108) immediately or go 
    to the nearest emergency room. Do not wait for an appointment.
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | Required | Your Gemini API key |
| `BACKEND_URL` | `http://localhost:9090` | Spring Boot backend URL |
| `PORT` | `8000` | AI agent service port |
| `FRONTEND_URL` | `http://localhost:5173` | Frontend URL for CORS |
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | None | Redis password |

### Redis Configuration

The AI agent can work with or without Redis:

- **With Redis**: Persistent sessions and conversation history across restarts
- **Without Redis**: In-memory storage (loses data on restart)

If Redis connection fails, the service automatically falls back to in-memory storage.

## 🐛 Troubleshooting

### Issue: "Gemini API key not configured"
**Solution**: Copy `.env.example` to `.env` and add your API key

### Issue: "Cannot connect to backend"
**Solution**: Ensure Spring Boot backend is running on the configured `BACKEND_URL`

### Issue: "Redis connection failed"
**Solution**: Either install/start Redis, or ignore (will use in-memory storage)

### Issue: "CORS error from frontend"
**Solution**: Ensure `FRONTEND_URL` in `.env` matches your frontend URL

## 📁 File Structure

```
ai-agent/
├── main.py                    # FastAPI application
├── service.py                 # Main AI service logic
├── models.py                  # Pydantic models
├── conversation_manager.py    # Session & history management
├── symptom_triage.py         # Symptom analysis
├── appointment_manager.py     # Booking flow & doctor search
├── requirements.txt          # Python dependencies
├── .env.example              # Environment template
└── .env                      # Your configuration (create this)
```

## 🔐 Security Notes

- Never commit `.env` file to version control
- JWT tokens are forwarded to backend for authenticated requests
- Guest users (unauthenticated) have limited access
- Medical advice disclaimers are always included

## 📊 Monitoring

Check service health:
```bash
curl http://localhost:8000/health
```

View logs in the console where `main.py` is running.

## 🎯 Future Enhancements

- [ ] Appointment cancellation flow
- [ ] Appointment rescheduling
- [ ] Insurance verification integration  
- [ ] Email/SMS notifications
- [ ] Voice interface support
- [ ] Multi-language support
- [ ] Analytics dashboard

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review error logs in the console
3. Verify all dependencies are installed
4. Ensure environment variables are properly configured
