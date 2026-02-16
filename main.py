from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError as PydanticValidationError
from service import AIAgentService
from models import ChatRequest, ChatResponse, ValidationError
import os
from dotenv import load_dotenv
from typing import Optional

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
        if not request.user_id or not request.user_id.strip():
            return ChatResponse(
                response="User ID is required",
                success=False,
                message="User ID is required",
                validation_errors=[ValidationError(
                    field="user_id",
                    message="User ID cannot be empty",
                    error_code="REQUIRED_FIELD"
                )]
            )
        
        if not request.message or not request.message.strip():
            return ChatResponse(
                response="Message cannot be empty",
                success=False,
                message="Message cannot be empty",
                validation_errors=[ValidationError(
                    field="message",
                    message="Message cannot be empty",
                    error_code="REQUIRED_FIELD"
                )]
            )
        
        # Extract JWT token from Authorization header if present
        jwt_token = None
        if authorization and authorization.startswith("Bearer "):
            jwt_token = authorization[7:]  # Remove "Bearer " prefix
        elif request.jwt_token:
            jwt_token = request.jwt_token
        
        response = await agent_service.process_message(
            request.user_id, 
            request.message,
            jwt_token
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
            message="Validation failed",
            validation_errors=validation_errors
        )
    except ValueError as e:
        # Handle value errors
        return ChatResponse(
            response=str(e),
            success=False,
            message=str(e),
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
            message="Internal server error",
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
