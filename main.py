import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from models.api import ChatResponse, ChatRequest, ValidationError
from service import AIAgentService
from utils.JwtExtractor import extract_user_id_from_jwt

load_dotenv()
app = FastAPI(
    title="AI Medical Appointment Agent",
    description="Intelligent AI agent for medical appointment booking and patient assistance",
    version="1.0.0"
)

# CORS Configuration
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:8080", "*"],  # Add backend and allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent_service = AIAgentService()

# Custom exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Handle Pydantic validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "error_code": "VALIDATION_ERROR"
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Invalid request data",
            "validation_errors": errors
        }
    )

@app.post("/ai/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, authorization: Optional[str] = Header(None)):
    """
    Main chat endpoint for AI conversation
    
    Args:
        request: Chat request with user_id and message
        authorization: Optional JWT token from Authorization header
    
    Returns:
        ChatResponse with AI response and metadata
    """
    try:
        # Validate request
        if not request.message or not request.message.strip():
            return ChatResponse(
                response="Message cannot be empty",
                success=False,
                validation_errors=[ValidationError(
                    field="message",
                    message="Message cannot be empty",
                    error_code="REQUIRED_FIELD"
                )]
            )
        
        # Extract JWT token from Authorization header if present
        jwt_token = None
        user_id='anonymous'
        if authorization and authorization.startswith("Bearer "):
            jwt_token = authorization[7:]  # Remove "Bearer " prefix
            user_id = extract_user_id_from_jwt(jwt_token)

        
        response = await agent_service.process_message(
            user_id=user_id,
            message=request.message,
            jwt_token=jwt_token
        )
        return response

    except PydanticValidationError as e:
        # Handle Pydantic validation errors
        validation_errors = [
            ValidationError(
                field=str(err.get("loc", [""])[0]),
                message=err.get("msg", "Validation error"),
                error_code="VALIDATION_ERROR"
            )
            for err in e.errors()
        ]
        return ChatResponse(
            response="Please check your input and try again",
            success=False,
            validation_errors=validation_errors
        )
    except ValueError as e:
        # Handle value errors
        return ChatResponse(
            response=str(e),
            success=False,
            validation_errors=[ValidationError(
                field="general",
                message=str(e),
                error_code="VALUE_ERROR"
            )]
        )
    except Exception as e:
        print(f"[API Error] {str(e)}")
        import traceback
        traceback.print_exc()
        return ChatResponse(
            response="An unexpected error occurred. Please try again later.",
            success=False,
            intent="UNKNOWN"
        )

@app.get("/health")
def health_check():
    """Health check endpoint"""
    gemini_status = "OK" if os.getenv("GEMINI_API_KEY") else "NOT_CONFIGURED"
    backend_url = os.getenv("BACKEND_URL", "http://localhost:9090")
    
    return {
        "status": "ok",
        "service": "AI Medical Appointment Agent",
        "gemini_api": gemini_status,
        "backend_url": backend_url,
        "version": "1.0.0"
    }
