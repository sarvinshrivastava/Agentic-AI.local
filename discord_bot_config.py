#!/usr/bin/env python3
"""
Discord Bot Configuration - Centralized configuration management for Discord integration
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DiscordConfig:
    """Configuration for Discord bot settings"""
    # Discord Bot Credentials
    bot_token: str = field(default_factory=lambda: os.getenv("DISCORD_BOT_TOKEN", ""))
    application_id: str = field(default_factory=lambda: os.getenv("DISCORD_APPLICATION_ID", ""))
    
    # Bot Behavior
    command_prefix: str = "!"
    mention_trigger: bool = True  # Respond to @mentions
    dm_trigger: bool = True      # Respond to DMs
    
    # Conversation Flow
    conversation_flow_enabled: bool = True  # Enable continuous conversation after mention
    conversation_flow_timeout: int = 90     # Seconds before conversation expires
    conversation_end_commands: List[str] = field(default_factory=lambda: ["end", "stop"])
    
    # Session Management
    session_timeout: int = 1800  # 30 minutes in seconds
    max_concurrent_sessions: int = 100
    session_cleanup_interval: int = 300  # 5 minutes
    
    # Rate Limiting
    rate_limit_requests: int = 5  # requests per minute per user
    rate_limit_window: int = 60   # window in seconds
    
    # Response Settings
    max_response_length: int = 2000  # Discord message limit
    use_embeds: bool = True
    use_threads: bool = True  # Create threads for complex conversations
    
    # Permissions
    allowed_servers: List[str] = field(default_factory=list)  # Empty = all servers
    admin_users: List[str] = field(default_factory=list)
    restricted_commands: List[str] = field(default_factory=lambda: ["delete-event"])
    
    # Feature Toggles
    enable_slash_commands: bool = True
    enable_calendar_embeds: bool = True
    enable_file_attachments: bool = False  # For future document sharing
    enable_voice_responses: bool = False   # For future voice integration
    
    # Logging & Monitoring
    log_level: str = "INFO"
    audit_log_channel: Optional[str] = None  # Channel ID for audit logs
    error_log_channel: Optional[str] = None  # Channel ID for error reports


@dataclass
class CalendarAssistantConfig:
    """Configuration for Calendar Assistant integration"""
    # Default user settings
    default_user_email: str = field(default_factory=lambda: os.getenv("DEFAULT_USER_EMAIL", "sarvin5124@gmail.com"))
    timezone: str = "Asia/Kolkata"  # IST
    
    # AI Model Settings
    openai_model: str = "gpt-4o"
    max_iterations: int = 10
    conversation_history_limit: int = 10
    
    # MCP Settings
    calendar_url: str = "http://localhost:3000/mcp"
    notion_url: str = "https://mcp.notion.com/mcp"
    health_check_interval: int = 300  # 5 minutes


@dataclass
class IntegrationConfig:
    """Combined configuration for Discord bot integration"""
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    assistant: CalendarAssistantConfig = field(default_factory=CalendarAssistantConfig)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        if not self.discord.bot_token:
            issues.append("DISCORD_BOT_TOKEN environment variable is required")
        
        if not os.getenv("OPENAI_API_KEY"):
            issues.append("OPENAI_API_KEY environment variable is required")
        
        if self.discord.session_timeout < 60:
            issues.append("Session timeout should be at least 60 seconds")
            
        if self.discord.max_concurrent_sessions < 1:
            issues.append("Max concurrent sessions should be at least 1")
        
        return issues
    
    @classmethod
    def load_from_env(cls) -> 'IntegrationConfig':
        """Load configuration from environment variables"""
        config = cls()
        
        # Override with environment variables if present
        if os.getenv("DISCORD_COMMAND_PREFIX"):
            config.discord.command_prefix = os.getenv("DISCORD_COMMAND_PREFIX")
        
        if os.getenv("SESSION_TIMEOUT"):
            config.discord.session_timeout = int(os.getenv("SESSION_TIMEOUT"))
        
        if os.getenv("MAX_CONCURRENT_SESSIONS"):
            config.discord.max_concurrent_sessions = int(os.getenv("MAX_CONCURRENT_SESSIONS"))
        
        if os.getenv("ALLOWED_SERVERS"):
            config.discord.allowed_servers = os.getenv("ALLOWED_SERVERS").split(",")
        
        if os.getenv("ADMIN_USERS"):
            config.discord.admin_users = os.getenv("ADMIN_USERS").split(",")
        
        return config


# Global configuration instance
config = IntegrationConfig.load_from_env()