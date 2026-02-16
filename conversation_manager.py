import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import redis

class ConversationManager:
    """Manages conversation sessions and history using Redis"""
    
    def __init__(self):
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            self.use_redis = True
            print(f"✓ Connected to Redis at {redis_host}:{redis_port}")
        except Exception as e:
            print(f"⚠ Redis connection failed: {e}. Using in-memory storage.")
            self.use_redis = False
            self.memory_storage = {}
    
    def _get_session_key(self, user_id: str) -> str:
        """Generate Redis key for session"""
        return f"chat_session:{user_id}"
    
    def _get_history_key(self, user_id: str) -> str:
        """Generate Redis key for conversation history"""
        return f"chat_history:{user_id}"
    
    def start_session(self, user_id: str, metadata: Optional[Dict] = None) -> Dict:
        """Start a new conversation session"""
        session_data = {
            "user_id": user_id,
            "started_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "metadata": metadata or {},
            "context": {}
        }
        
        session_key = self._get_session_key(user_id)
        
        if self.use_redis:
            # Store session with 1 hour expiry
            self.redis_client.setex(
                session_key,
                timedelta(hours=1),
                json.dumps(session_data)
            )
        else:
            self.memory_storage[session_key] = session_data
        
        return session_data
    
    def get_session(self, user_id: str) -> Optional[Dict]:
        """Get existing session or create new one"""
        session_key = self._get_session_key(user_id)
        
        if self.use_redis:
            session_data = self.redis_client.get(session_key)
            if session_data:
                return json.loads(session_data)
        else:
            if session_key in self.memory_storage:
                return self.memory_storage[session_key]
        
        # No active session, create new one
        return self.start_session(user_id)
    
    def update_session_context(self, user_id: str, context_updates: Dict) -> None:
        """Update session context with new information"""
        session = self.get_session(user_id)
        session["context"].update(context_updates)
        session["last_activity"] = datetime.now().isoformat()
        
        session_key = self._get_session_key(user_id)
        
        if self.use_redis:
            self.redis_client.setex(
                session_key,
                timedelta(hours=1),
                json.dumps(session)
            )
        else:
            self.memory_storage[session_key] = session
    
    def add_message(self, user_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """Add a message to conversation history"""
        message = {
            "role": role,  # 'user' or 'assistant'
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        history_key = self._get_history_key(user_id)
        
        if self.use_redis:
            # Add to list and keep last 50 messages
            self.redis_client.lpush(history_key, json.dumps(message))
            self.redis_client.ltrim(history_key, 0, 49)
            self.redis_client.expire(history_key, timedelta(hours=24))
        else:
            if history_key not in self.memory_storage:
                self.memory_storage[history_key] = []
            self.memory_storage[history_key].insert(0, message)
            self.memory_storage[history_key] = self.memory_storage[history_key][:50]
    
    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get recent conversation history"""
        history_key = self._get_history_key(user_id)
        
        if self.use_redis:
            messages = self.redis_client.lrange(history_key, 0, limit - 1)
            return [json.loads(msg) for msg in messages]
        else:
            if history_key in self.memory_storage:
                return self.memory_storage[history_key][:limit]
            return []
    
    def get_context_string(self, user_id: str, limit: int = 5) -> str:
        """Get conversation history formatted as context string for AI"""
        history = self.get_conversation_history(user_id, limit)
        
        if not history:
            return ""
        
        # Reverse to get chronological order
        history = list(reversed(history))
        
        context_lines = []
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            context_lines.append(f"{role}: {msg['content']}")
        
        return "\n".join(context_lines)
    
    def end_session(self, user_id: str) -> None:
        """End conversation session"""
        session_key = self._get_session_key(user_id)
        
        if self.use_redis:
            self.redis_client.delete(session_key)
        else:
            if session_key in self.memory_storage:
                del self.memory_storage[session_key]
    
    def clear_history(self, user_id: str) -> None:
        """Clear conversation history"""
        history_key = self._get_history_key(user_id)
        
        if self.use_redis:
            self.redis_client.delete(history_key)
        else:
            if history_key in self.memory_storage:
                del self.memory_storage[history_key]
