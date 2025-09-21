#!/usr/bin/env python3
"""
Discord Security Manager - Handles authentication, permissions, and audit logging
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import hmac

import discord
from discord_bot_config import config

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Permission levels for users"""
    BANNED = 0
    BASIC = 1
    TRUSTED = 2
    ADMIN = 3


@dataclass
class UserPermissions:
    """User permission and security information"""
    user_id: str
    permission_level: PermissionLevel = PermissionLevel.BASIC
    email_verified: bool = False
    user_email: Optional[str] = None
    allowed_commands: Set[str] = field(default_factory=set)
    restricted_until: Optional[datetime] = None
    total_requests: int = 0
    last_activity: datetime = field(default_factory=datetime.now)
    
    def is_restricted(self) -> bool:
        """Check if user is currently restricted"""
        if self.permission_level == PermissionLevel.BANNED:
            return True
        if self.restricted_until and datetime.now() < self.restricted_until:
            return True
        return False
    
    def can_use_command(self, command: str) -> bool:
        """Check if user can use specific command"""
        if self.is_restricted():
            return False
        
        if command in config.discord.restricted_commands:
            return self.permission_level.value >= PermissionLevel.TRUSTED.value
        
        return True
    
    def update_activity(self):
        """Update last activity and increment request counter"""
        self.last_activity = datetime.now()
        self.total_requests += 1


@dataclass
class AuditLogEntry:
    """Audit log entry for security events"""
    timestamp: datetime
    user_id: str
    action: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    channel_id: Optional[str] = None
    guild_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "details": self.details,
            "ip_address": self.ip_address,
            "channel_id": self.channel_id,
            "guild_id": self.guild_id
        }


class SecurityManager:
    """
    Handles security, authentication, and audit logging for Discord bot
    """
    
    def __init__(self):
        self._user_permissions: Dict[str, UserPermissions] = {}
        self._audit_logs: List[AuditLogEntry] = []
        self._failed_attempts: Dict[str, List[datetime]] = {}  # user_id -> [timestamps]
        self._suspicious_activity: Set[str] = set()
        self._rate_limits: Dict[str, datetime] = {}  # user_id -> next_allowed_time
        
        # Load admin users from config
        for admin_id in config.discord.admin_users:
            self._user_permissions[admin_id] = UserPermissions(
                user_id=admin_id,
                permission_level=PermissionLevel.ADMIN
            )
    
    async def check_user_permissions(self, user: discord.User, command: str = None) -> bool:
        """
        Check if user has permission to interact with bot
        
        Args:
            user: Discord user object
            command: Specific command being attempted (optional)
            
        Returns:
            True if user has permission, False otherwise
        """
        user_id = str(user.id)
        
        # Get or create user permissions
        permissions = self._get_or_create_permissions(user_id)
        
        # Check if user is restricted
        if permissions.is_restricted():
            await self._log_security_event(
                user_id, 
                "ACCESS_DENIED_RESTRICTED",
                {"reason": "User is restricted or banned"}
            )
            return False
        
        # Check command-specific permissions
        if command and not permissions.can_use_command(command):
            await self._log_security_event(
                user_id,
                "ACCESS_DENIED_COMMAND",
                {"command": command, "permission_level": permissions.permission_level.name}
            )
            return False
        
        # Check rate limits
        if not await self._check_rate_limit(user_id):
            return False
        
        # Update activity
        permissions.update_activity()
        
        return True
    
    async def authenticate_user_email(self, user_id: str, email: str) -> bool:
        """
        Authenticate user email (placeholder for future OAuth integration)
        
        Args:
            user_id: Discord user ID
            email: Email to authenticate
            
        Returns:
            True if authenticated successfully
        """
        permissions = self._get_or_create_permissions(user_id)
        
        # TODO: Implement actual email verification
        # For now, just store the email and mark as verified
        permissions.user_email = email
        permissions.email_verified = True
        
        await self._log_security_event(
            user_id,
            "EMAIL_AUTHENTICATED", 
            {"email": email}
        )
        
        return True
    
    async def set_user_permission_level(self, admin_id: str, target_user_id: str, level: PermissionLevel) -> bool:
        """
        Set user permission level (admin only)
        
        Args:
            admin_id: ID of admin performing action
            target_user_id: ID of user to modify
            level: New permission level
            
        Returns:
            True if successful
        """
        # Check admin permissions
        admin_permissions = self._get_or_create_permissions(admin_id)
        if admin_permissions.permission_level != PermissionLevel.ADMIN:
            return False
        
        # Update target user permissions
        target_permissions = self._get_or_create_permissions(target_user_id)
        old_level = target_permissions.permission_level
        target_permissions.permission_level = level
        
        await self._log_security_event(
            admin_id,
            "PERMISSION_CHANGE",
            {
                "target_user": target_user_id,
                "old_level": old_level.name,
                "new_level": level.name
            }
        )
        
        return True
    
    async def restrict_user(self, admin_id: str, target_user_id: str, duration_minutes: int, reason: str) -> bool:
        """
        Temporarily restrict a user
        
        Args:
            admin_id: ID of admin performing action
            target_user_id: ID of user to restrict
            duration_minutes: Duration of restriction in minutes
            reason: Reason for restriction
            
        Returns:
            True if successful
        """
        admin_permissions = self._get_or_create_permissions(admin_id)
        if admin_permissions.permission_level != PermissionLevel.ADMIN:
            return False
        
        target_permissions = self._get_or_create_permissions(target_user_id)
        target_permissions.restricted_until = datetime.now() + timedelta(minutes=duration_minutes)
        
        await self._log_security_event(
            admin_id,
            "USER_RESTRICTED",
            {
                "target_user": target_user_id,
                "duration_minutes": duration_minutes,
                "reason": reason,
                "restricted_until": target_permissions.restricted_until.isoformat()
            }
        )
        
        return True
    
    async def ban_user(self, admin_id: str, target_user_id: str, reason: str) -> bool:
        """
        Permanently ban a user
        
        Args:
            admin_id: ID of admin performing action
            target_user_id: ID of user to ban
            reason: Reason for ban
            
        Returns:
            True if successful
        """
        admin_permissions = self._get_or_create_permissions(admin_id)
        if admin_permissions.permission_level != PermissionLevel.ADMIN:
            return False
        
        target_permissions = self._get_or_create_permissions(target_user_id)
        target_permissions.permission_level = PermissionLevel.BANNED
        
        await self._log_security_event(
            admin_id,
            "USER_BANNED",
            {
                "target_user": target_user_id,
                "reason": reason
            }
        )
        
        return True
    
    async def report_suspicious_activity(self, user_id: str, activity_type: str, details: Dict[str, Any]):
        """
        Report suspicious activity
        
        Args:
            user_id: User ID involved in suspicious activity
            activity_type: Type of suspicious activity
            details: Additional details about the activity
        """
        self._suspicious_activity.add(user_id)
        
        await self._log_security_event(
            user_id,
            f"SUSPICIOUS_ACTIVITY_{activity_type.upper()}",
            details
        )
        
        # Auto-restrict for severe suspicious activity
        if activity_type in ["RAPID_REQUESTS", "MALICIOUS_INPUT"]:
            permissions = self._get_or_create_permissions(user_id)
            permissions.restricted_until = datetime.now() + timedelta(minutes=15)  # 15 minute timeout
    
    async def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits"""
        now = datetime.now()
        
        # Check if user is currently rate limited
        if user_id in self._rate_limits and now < self._rate_limits[user_id]:
            return False
        
        # Track failed attempts for potential abuse
        if user_id not in self._failed_attempts:
            self._failed_attempts[user_id] = []
        
        # Clean old attempts (older than 5 minutes)
        cutoff = now - timedelta(minutes=5)
        self._failed_attempts[user_id] = [
            attempt for attempt in self._failed_attempts[user_id] 
            if attempt > cutoff
        ]
        
        # Check for too many recent attempts
        if len(self._failed_attempts[user_id]) >= 10:  # 10 attempts in 5 minutes
            # Rate limit for 5 minutes
            self._rate_limits[user_id] = now + timedelta(minutes=5)
            
            await self.report_suspicious_activity(
                user_id,
                "RAPID_REQUESTS",
                {"attempt_count": len(self._failed_attempts[user_id])}
            )
            
            return False
        
        return True
    
    def _get_or_create_permissions(self, user_id: str) -> UserPermissions:
        """Get or create user permissions"""
        if user_id not in self._user_permissions:
            self._user_permissions[user_id] = UserPermissions(user_id=user_id)
        return self._user_permissions[user_id]
    
    async def _log_security_event(self, user_id: str, action: str, details: Dict[str, Any], 
                                 channel_id: str = None, guild_id: str = None):
        """Log security event"""
        entry = AuditLogEntry(
            timestamp=datetime.now(),
            user_id=user_id,
            action=action,
            details=details,
            channel_id=channel_id,
            guild_id=guild_id
        )
        
        self._audit_logs.append(entry)
        
        # Log to file/database (implement as needed)
        logger.info(f"Security Event - {action}: User {user_id} - {details}")
        
        # Clean old logs (keep last 1000 entries)
        if len(self._audit_logs) > 1000:
            self._audit_logs = self._audit_logs[-1000:]
    
    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user security information"""
        if user_id not in self._user_permissions:
            return None
        
        permissions = self._user_permissions[user_id]
        return {
            "user_id": user_id,
            "permission_level": permissions.permission_level.name,
            "email_verified": permissions.email_verified,
            "user_email": permissions.user_email,
            "is_restricted": permissions.is_restricted(),
            "restricted_until": permissions.restricted_until.isoformat() if permissions.restricted_until else None,
            "total_requests": permissions.total_requests,
            "last_activity": permissions.last_activity.isoformat(),
            "is_suspicious": user_id in self._suspicious_activity
        }
    
    def get_audit_logs(self, user_id: str = None, action: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit logs with optional filtering"""
        logs = self._audit_logs
        
        # Filter by user
        if user_id:
            logs = [log for log in logs if log.user_id == user_id]
        
        # Filter by action
        if action:
            logs = [log for log in logs if action.lower() in log.action.lower()]
        
        # Limit results
        logs = logs[-limit:] if limit > 0 else logs
        
        return [log.to_dict() for log in reversed(logs)]
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics"""
        total_users = len(self._user_permissions)
        admin_users = sum(1 for p in self._user_permissions.values() if p.permission_level == PermissionLevel.ADMIN)
        restricted_users = sum(1 for p in self._user_permissions.values() if p.is_restricted())
        suspicious_users = len(self._suspicious_activity)
        
        return {
            "total_users": total_users,
            "admin_users": admin_users,
            "restricted_users": restricted_users,
            "banned_users": sum(1 for p in self._user_permissions.values() if p.permission_level == PermissionLevel.BANNED),
            "suspicious_users": suspicious_users,
            "total_audit_logs": len(self._audit_logs),
            "rate_limited_users": len(self._rate_limits)
        }


class SecureDataHandler:
    """
    Handles secure data operations for sensitive information
    """
    
    def __init__(self, encryption_key: str = None):
        self.encryption_key = encryption_key or "default_key_change_in_production"
    
    def sanitize_calendar_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize calendar data before sending to Discord
        Remove sensitive information that shouldn't be displayed
        """
        sanitized = data.copy()
        
        # Remove sensitive fields
        sensitive_fields = [
            "access_token", "refresh_token", "auth", "credentials",
            "private_key", "client_secret", "api_key"
        ]
        
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = "[REDACTED]"
        
        # Sanitize nested objects
        if isinstance(sanitized, dict):
            for key, value in sanitized.items():
                if isinstance(value, dict):
                    sanitized[key] = self.sanitize_calendar_data(value)
                elif isinstance(value, list):
                    sanitized[key] = [
                        self.sanitize_calendar_data(item) if isinstance(item, dict) else item
                        for item in value
                    ]
        
        return sanitized
    
    def hash_user_data(self, data: str) -> str:
        """
        Create secure hash of user data for logging/tracking
        """
        return hashlib.sha256(f"{data}{self.encryption_key}".encode()).hexdigest()[:16]
    
    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """
        Verify webhook signature for secure communications
        """
        expected = hmac.new(
            self.encryption_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)