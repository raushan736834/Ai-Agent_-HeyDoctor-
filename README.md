# AI Medical Appointment Agent 🤖

Intelligent AI-powered chatbot for the doctor appointment system with natural language understanding, multi-turn conversations, and symptom triage.

## 🚀 Quick Start

### 1. Get Gemini API Key
Get your free API key from: https://makersuite.google.com/app/apikey

### 2. Configure Environment
```bash
cd ai-agent
# Edit .env file and add your Gemini API key:
GEMINI_API_KEY=your_actual_api_key_here
```

### 3. Run the AI Service
```bash
# Windows
cd ..
.\run_agent.bat

# Or manually
cd ai-agent
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Service starts on: `http://localhost:8000`

### 4. Configure Backend
Add to `src/main/resources/application.properties`:
```properties
ai.agent.url=http://localhost:8000
```

### 5. Test It!
```bash
# Health check
curl http://localhost:8000/health

# Chat test
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"test\",\"message\":\"Hello\"}"
```

## ✨ Features

- ✅ **Intelligent Chatbot** - Natural language understanding with Gemini AI
- ✅ **Multi-turn Booking** - Step-by-step appointment scheduling
- ✅ **Symptom Triage** - AI-powered symptom analysis (EMERGENCY/URGENT/ROUTINE)
- ✅ **Doctor Search** - Find doctors by specialty, name, or location
- ✅ **Session Management** - Redis-based conversation history
- ✅ **Backend Integration** - Connects to Spring Boot APIs
- ✅ **Natural Language** - Parse dates ("tomorrow", "next Monday") and times ("3pm")

## 📚 Documentation

- **[AI_FEATURES.md](./ai-agent/AI_FEATURES.md)** - Complete feature documentation
- **[walkthrough.md](./walkthrough.md)** - Implementation walkthrough
- **[.env.example](./ai-agent/.env.example)** - Environment configuration template

## 🛠️ Tech Stack

- **FastAPI** - Web framework
- **Gemini AI** - Natural language processing
- **Redis** - Session storage (optional)
- **Spring Boot** - Backend integration

## 🔗 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Main chat interface |
| `/health` | GET | Service health check |
| `/session/start` | POST | Start conversation session |
| `/session/{user_id}` | GET | Get session info |
| `/specialists` | GET | List specialties |

## 💬 Example Conversation

```
User: Hi
AI: Hello! I'm your AI medical appointment assistant...

User: I need a cardiologist
AI: I found 3 cardiologists: Dr. Smith, Dr. Johnson...

User: Book with Dr. Smith for tomorrow at 3pm
AI: Perfect! Your appointment is confirmed:
    📅 Date: 2026-01-29
    🕐 Time: 3:00 PM
    👨‍⚕️ Doctor: Dr. Smith
```

## ⚠️ Requirements

- Python 3.8+
- Gemini API key (required for AI features)
- Redis (optional, uses in-memory if not available)
- Spring Boot backend running on port 9090

## 🐛 Troubleshooting

**Issue**: "Gemini API not configured"
- Add your API key to `ai-agent/.env`

**Issue**: "Cannot connect to backend"
- Ensure Spring Boot is running: `mvn spring-boot:run`

**Issue**: "Redis connection failed"
- Install Redis or ignore (will use in-memory storage)

## 📝 Files Structure

```
ai-agent/
├── main.py                    # FastAPI app
├── service.py                 # AI service logic
├── models.py                  # Data models
├── conversation_manager.py    # Session management
├── symptom_triage.py         # Symptom analysis
├── appointment_manager.py     # Booking flow
├── requirements.txt          # Dependencies
├── .env                      # Configuration
└── AI_FEATURES.md            # Full documentation
```

## 👨‍💻 Author

Implemented for Doctor Appointment Backend System

## 📄 License

Part of the Doctor Appointment System project
