#!/usr/bin/env python3
"""
Discord Session Manager - Handles user session tracking and conversation state
"""

import asyncio
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """Represents a user's conversation session"""
    user_id: str
    channel_id: str
    user_email: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    last_activity: datetime = field(default_factory=datetime.now)
    thread_id: Optional[str] = None
    is_dm: bool = False
    rate_limit_count: int = 0
    rate_limit_reset: datetime = field(default_factory=datetime.now)
    
    # Conversation Flow State
    conversation_active: bool = False
    conversation_started_at: Optional[datetime] = None
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
    
    def is_expired(self, timeout_seconds: int) -> bool:
        """Check if session has expired"""
        return (datetime.now() - self.last_activity).seconds > timeout_seconds
    
    def check_rate_limit(self, max_requests: int, window_seconds: int) -> bool:
        """Check if user is rate limited"""
        now = datetime.now()
        
        # Reset counter if window has passed
        if now > self.rate_limit_reset:
            self.rate_limit_count = 0
            self.rate_limit_reset = now + timedelta(seconds=window_seconds)
        
        # Check if under limit
        if self.rate_limit_count >= max_requests:
            return False
        
        self.rate_limit_count += 1
        return True
    
    def start_conversation(self):
        """Start an active conversation flow"""
        self.conversation_active = True
        self.conversation_started_at = datetime.now()
        self.update_activity()
    
    def end_conversation(self):
        """End the active conversation flow"""
        self.conversation_active = False
        self.conversation_started_at = None
    
    def is_conversation_expired(self, timeout_seconds: int) -> bool:
        """Check if active conversation has expired"""
        if not self.conversation_active or not self.conversation_started_at:
            return False
        
        return (datetime.now() - self.last_activity).seconds > timeout_seconds
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information"""
        return {
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "user_email": self.user_email,
            "last_activity": self.last_activity.isoformat(),
            "conversation_length": len(self.conversation_history),
            "is_dm": self.is_dm,
            "thread_id": self.thread_id,
            "rate_limit_count": self.rate_limit_count,
            "conversation_active": self.conversation_active,
            "conversation_started_at": self.conversation_started_at.isoformat() if self.conversation_started_at else None
        }


class DiscordSessionManager:
    """
    Manages user sessions and conversation state for Discord bot
    """
    
    def __init__(self, 
                 session_timeout: int = 1800,  # 30 minutes
                 max_sessions: int = 100,
                 cleanup_interval: int = 300,  # 5 minutes
                 rate_limit_requests: int = 5,
                 rate_limit_window: int = 60):
        self.session_timeout = session_timeout
        self.max_sessions = max_sessions
        self.cleanup_interval = cleanup_interval
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window = rate_limit_window
        
        self._sessions: Dict[str, UserSession] = {}  # user_id -> UserSession
        self._active_threads: Set[str] = set()  # Track active thread IDs
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False
    
    async def start(self):
        """Start session manager"""
        if not self._is_running:
            self._is_running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Discord Session Manager started")
    
    async def stop(self):
        """Stop session manager"""
        self._is_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self._sessions.clear()
        self._active_threads.clear()
        logger.info("Discord Session Manager stopped")
    
    def get_or_create_session(self, user_id: str, channel_id: str, user_email: str, is_dm: bool = False) -> UserSession:
        """Get existing session or create new one"""
        if user_id in self._sessions:
            session = self._sessions[user_id]
            session.update_activity()
            
            # Update channel if different (user switched channels)
            if session.channel_id != channel_id:
                session.channel_id = channel_id
                session.is_dm = is_dm
                logger.info(f"Updated session channel for user {user_id}: {channel_id}")
            
            return session
        
        # Check session limit
        if len(self._sessions) >= self.max_sessions:
            self._remove_oldest_session()
        
        # Create new session
        session = UserSession(
            user_id=user_id,
            channel_id=channel_id,
            user_email=user_email,
            is_dm=is_dm
        )
        
        self._sessions[user_id] = session
        logger.info(f"Created new session for user {user_id} in channel {channel_id}")
        
        return session
    
    def get_session(self, user_id: str) -> Optional[UserSession]:
        """Get existing session"""
        session = self._sessions.get(user_id)
        if session:
            session.update_activity()
        return session
    
    def update_conversation_history(self, user_id: str, history: List[Dict[str, Any]]):
        """Update conversation history for user"""
        session = self._sessions.get(user_id)
        if session:
            session.conversation_history = history
            session.update_activity()
    
    def reset_conversation(self, user_id: str) -> bool:
        """Reset conversation history for user"""
        session = self._sessions.get(user_id)
        if session:
            session.conversation_history = []
            session.update_activity()
            logger.info(f"Reset conversation for user {user_id}")
            return True
        return False
    
    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits"""
        session = self._sessions.get(user_id)
        if not session:
            return True  # Allow first message
        
        return session.check_rate_limit(self.rate_limit_requests, self.rate_limit_window)
    
    def start_conversation(self, user_id: str) -> bool:
        """Start an active conversation for user"""
        session = self._sessions.get(user_id)
        if session:
            session.start_conversation()
            logger.info(f"Started conversation for user {user_id} in channel {session.channel_id}")
            return True
        return False
    
    def end_conversation(self, user_id: str) -> bool:
        """End the active conversation for user"""
        session = self._sessions.get(user_id)
        if session:
            session.end_conversation()
            logger.info(f"Ended conversation for user {user_id}")
            return True
        return False
    
    def is_conversation_active(self, user_id: str) -> bool:
        """Check if user has an active conversation"""
        session = self._sessions.get(user_id)
        if not session:
            return False
        return session.conversation_active
    
    def is_conversation_expired(self, user_id: str, timeout_seconds: int) -> bool:
        """Check if user's conversation has expired"""
        session = self._sessions.get(user_id)
        if not session:
            return False
        return session.is_conversation_expired(timeout_seconds)
    
    def set_thread_id(self, user_id: str, thread_id: str):
        """Set thread ID for user session"""
        session = self._sessions.get(user_id)
        if session:
            session.thread_id = thread_id
            self._active_threads.add(thread_id)
            logger.info(f"Set thread {thread_id} for user {user_id}")
    
    def get_thread_user(self, thread_id: str) -> Optional[str]:
        """Get user ID associated with thread"""
        for user_id, session in self._sessions.items():
            if session.thread_id == thread_id:
                return user_id
        return None
    
    def remove_session(self, user_id: str) -> bool:
        """Remove user session"""
        session = self._sessions.pop(user_id, None)
        if session:
            if session.thread_id:
                self._active_threads.discard(session.thread_id)
            logger.info(f"Removed session for user {user_id}")
            return True
        return False
    
    def _remove_oldest_session(self):
        """Remove the oldest session to make room"""
        if not self._sessions:
            return
        
        oldest_user = min(
            self._sessions.items(), 
            key=lambda x: x[1].last_activity
        )[0]
        
        self.remove_session(oldest_user)
        logger.info(f"Removed oldest session for user {oldest_user} due to session limit")
    
    async def _cleanup_loop(self):
        """Periodic cleanup of expired sessions"""
        while self._is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                current_time = datetime.now()
                expired_users = []
                
                # Find expired sessions
                for user_id, session in self._sessions.items():
                    if session.is_expired(self.session_timeout):
                        expired_users.append(user_id)
                
                # Remove expired sessions
                for user_id in expired_users:
                    self.remove_session(user_id)
                
                if expired_users:
                    logger.info(f"Cleaned up {len(expired_users)} expired sessions")
                
                # Also cleanup expired conversations (they will remain as sessions but conversation state ends)
                self._cleanup_expired_conversations()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
    
    def _cleanup_expired_conversations(self, conversation_timeout: int = 90):
        """Clean up expired conversations while keeping sessions alive"""
        expired_conversations = []
        
        for user_id, session in self._sessions.items():
            if session.conversation_active and session.is_conversation_expired(conversation_timeout):
                session.end_conversation()
                expired_conversations.append(user_id)
        
        if expired_conversations:
            logger.info(f"Ended {len(expired_conversations)} expired conversations")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session manager statistics"""
        active_sessions = len(self._sessions)
        dm_sessions = sum(1 for s in self._sessions.values() if s.is_dm)
        server_sessions = active_sessions - dm_sessions
        
        return {
            "active_sessions": active_sessions,
            "dm_sessions": dm_sessions,
            "server_sessions": server_sessions,
            "active_threads": len(self._active_threads),
            "max_sessions": self.max_sessions,
            "session_timeout": self.session_timeout,
            "is_running": self._is_running
        }
    
    def get_session_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific session"""
        session = self._sessions.get(user_id)
        return session.get_session_info() if session else None
    
    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """Get list of all active sessions"""
        return [session.get_session_info() for session in self._sessions.values()]
    
    def cleanup_thread(self, thread_id: str):
        """Clean up thread-related data"""
        self._active_threads.discard(thread_id)
        
        # Find and update session
        for session in self._sessions.values():
            if session.thread_id == thread_id:
                session.thread_id = None
                break
    
    def get_conversation_context(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history for user"""
        session = self._sessions.get(user_id)
        if not session:
            return []
        
        return session.conversation_history[-limit:] if limit > 0 else session.conversation_history