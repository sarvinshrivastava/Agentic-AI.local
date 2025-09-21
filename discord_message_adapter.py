#!/usr/bin/env python3
"""
Discord Message Adapter - Handles message format conversion between Discord and Calendar Assistant
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class MessageAdapter:
    """
    Handles conversion between Discord messages and Calendar Assistant format
    """
    
    def __init__(self):
        self.max_embed_length = 2048
        self.max_field_value_length = 1024
    
    def discord_to_assistant(self, message: discord.Message) -> str:
        """
        Convert Discord message to format suitable for Calendar Assistant
        
        Args:
            message: Discord message object
            
        Returns:
            Formatted string for Calendar Assistant
        """
        content = message.content.strip()
        
        # Remove bot mentions from the message
        content = self._remove_bot_mentions(content, message)
        
        # Handle different message types
        if message.attachments:
            content += self._format_attachments(message.attachments)
        
        if message.embeds:
            content += self._format_embeds_to_text(message.embeds)
        
        # Add context about the Discord environment if helpful
        context_info = []
        if message.guild:
            context_info.append(f"Server: {message.guild.name}")
        if hasattr(message.channel, 'name'):
            context_info.append(f"Channel: #{message.channel.name}")
        
        if context_info:
            content = f"[Context: {', '.join(context_info)}]\n{content}"
        
        return content.strip()
    
    def assistant_to_discord(self, response: str, use_embeds: bool = True) -> Dict[str, Any]:
        """
        Convert Calendar Assistant response to Discord message format
        
        Args:
            response: AI assistant response text
            use_embeds: Whether to use rich embeds for formatting
            
        Returns:
            Dictionary with Discord message parameters
        """
        if not response:
            return {"content": "I encountered an issue processing your request. Please try again."}
        
        # Check for special formatting patterns
        calendar_events = self._extract_calendar_events(response)
        error_messages = self._extract_error_messages(response)
        
        if use_embeds and (calendar_events or error_messages):
            return self._create_embed_response(response, calendar_events, error_messages)
        else:
            return self._create_text_response(response)
    
    def _remove_bot_mentions(self, content: str, message: discord.Message) -> str:
        """Remove bot mentions from message content"""
        # Remove @bot mentions
        content = re.sub(r'<@!?\d+>', '', content).strip()
        
        # Remove bot name mentions if present
        if message.guild and message.guild.me:
            bot_name = message.guild.me.display_name
            content = re.sub(rf'@{re.escape(bot_name)}', '', content, flags=re.IGNORECASE).strip()
        
        return content
    
    def _format_attachments(self, attachments: List[discord.Attachment]) -> str:
        """Format attachment information"""
        if not attachments:
            return ""
        
        attachment_info = []
        for attachment in attachments:
            if attachment.content_type and attachment.content_type.startswith('image/'):
                attachment_info.append(f"📷 Image: {attachment.filename}")
            elif attachment.content_type and attachment.content_type.startswith('text/'):
                attachment_info.append(f"📄 Document: {attachment.filename}")
            else:
                attachment_info.append(f"📎 File: {attachment.filename}")
        
        return f"\n[Attachments: {', '.join(attachment_info)}]"
    
    def _format_embeds_to_text(self, embeds: List[discord.Embed]) -> str:
        """Convert Discord embeds to text format"""
        if not embeds:
            return ""
        
        embed_text = []
        for embed in embeds:
            if embed.title:
                embed_text.append(f"**{embed.title}**")
            if embed.description:
                embed_text.append(embed.description)
            
            for field in embed.fields:
                embed_text.append(f"**{field.name}:** {field.value}")
        
        return f"\n[Embedded Content: {' | '.join(embed_text)}]" if embed_text else ""
    
    def _extract_calendar_events(self, response: str) -> List[Dict[str, Any]]:
        """Extract calendar event information from response"""
        events = []
        
        # Look for event creation confirmations
        event_patterns = [
            r"Created event:\s*(.+?)(?:\n|$)",
            r"Event created:\s*(.+?)(?:\n|$)",
            r"Scheduled:\s*(.+?)(?:\n|$)",
        ]
        
        for pattern in event_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                events.append({
                    "type": "created",
                    "title": match.strip(),
                    "raw_text": match
                })
        
        # Look for upcoming events
        if "upcoming events" in response.lower() or "your calendar" in response.lower():
            # This could be enhanced to parse structured event data
            events.append({
                "type": "list",
                "title": "Calendar Events",
                "raw_text": response
            })
        
        return events
    
    def _extract_error_messages(self, response: str) -> List[str]:
        """Extract error messages from response"""
        error_patterns = [
            r"Error:\s*(.+?)(?:\n|$)",
            r"❌\s*(.+?)(?:\n|$)",
            r"Failed to\s*(.+?)(?:\n|$)",
        ]
        
        errors = []
        for pattern in error_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE | re.MULTILINE)
            errors.extend([match.strip() for match in matches])
        
        return errors
    
    def _create_embed_response(self, response: str, calendar_events: List[Dict[str, Any]], error_messages: List[str]) -> Dict[str, Any]:
        """Create Discord embed response"""
        embeds = []
        
        # Main response embed
        main_embed = discord.Embed(
            title="🗓️ Calendar Assistant Pro",
            description=self._truncate_text(response, self.max_embed_length),
            color=0x00a8ff,  # Blue color
            timestamp=datetime.now()
        )
        
        # Add footer
        main_embed.set_footer(text="Calendar Assistant Pro", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
        
        # Handle calendar events
        if calendar_events:
            for event in calendar_events[:3]:  # Limit to 3 events to avoid embed limits
                if event["type"] == "created":
                    main_embed.add_field(
                        name="✅ Event Created",
                        value=self._truncate_text(event["title"], self.max_field_value_length),
                        inline=False
                    )
                elif event["type"] == "list":
                    # Create separate embed for event lists
                    event_embed = discord.Embed(
                        title="📅 Your Calendar",
                        description=self._truncate_text(event["raw_text"], self.max_embed_length),
                        color=0x00d4aa,  # Green color
                    )
                    embeds.append(event_embed)
        
        # Handle errors
        if error_messages:
            error_text = "\n".join(error_messages[:3])  # Limit to 3 errors
            main_embed.add_field(
                name="⚠️ Issues",
                value=self._truncate_text(error_text, self.max_field_value_length),
                inline=False
            )
            main_embed.color = 0xff6b6b  # Red color for errors
        
        embeds.insert(0, main_embed)
        
        return {"embeds": embeds}
    
    def _create_text_response(self, response: str) -> Dict[str, Any]:
        """Create plain text Discord response"""
        # Split long messages
        if len(response) <= 2000:
            return {"content": response}
        else:
            # Split into multiple messages
            chunks = self._split_message(response, 2000)
            return {"content": chunks[0], "follow_up": chunks[1:]}
    
    def _split_message(self, message: str, max_length: int) -> List[str]:
        """Split long message into chunks"""
        if len(message) <= max_length:
            return [message]
        
        chunks = []
        current_chunk = ""
        
        # Try to split on newlines first
        lines = message.split('\n')
        for line in lines:
            if len(current_chunk) + len(line) + 1 <= max_length:
                current_chunk += line + '\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = line + '\n'
                else:
                    # Line is too long, split it
                    words = line.split()
                    for word in words:
                        if len(current_chunk) + len(word) + 1 <= max_length:
                            current_chunk += word + ' '
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = word + ' '
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to fit Discord limits"""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
    def format_help_message(self) -> discord.Embed:
        """Create formatted help message embed"""
        embed = discord.Embed(
            title="🗓️ Calendar Assistant Pro - Help",
            description="I'm your AI-powered calendar and workspace assistant!",
            color=0x00a8ff
        )
        
        # Calendar operations
        embed.add_field(
            name="📅 Calendar Operations",
            value=(
                "• `Show my events this week`\n"
                "• `Create a meeting tomorrow at 2 PM`\n"
                "• `What's on my calendar for Friday?`\n"
                "• `Schedule a team meeting next Monday`\n"
                "• `Update my 3 PM meeting to 4 PM`"
            ),
            inline=False
        )
        
        # Notion operations
        embed.add_field(
            name="📝 Notion Operations",
            value=(
                "• `Search for documents about financial reports`\n"
                "• `Show me my project planning documents`\n"
                "• `Find notes from last week's meeting`\n"
                "• `What documents do I have about marketing?`"
            ),
            inline=False
        )
        
        # Combined operations
        embed.add_field(
            name="🔗 Smart Integration",
            value=(
                "• `I have a meeting about Q4 planning - show me relevant docs`\n"
                "• `Create a meeting for the marketing campaign and find related documents`\n"
                "• `Schedule a follow-up meeting and pull the project notes`"
            ),
            inline=False
        )
        
        # Usage tips
        embed.add_field(
            name="💡 Usage Tips",
            value=(
                "• Mention me (@CalendarAssistantPro) to start a conversation\n"
                "• After mentioning me, I'll respond to your next messages for 90 seconds\n"
                "• Use `!end`, `/end`, or `end` to stop the conversation early\n"
                "• Send me a DM for private assistance\n"
                "• Use natural language - I understand context!\n"
                "• All times are in IST (Indian Standard Time)"
            ),
            inline=False
        )
        
        embed.set_footer(text="Calendar Assistant Pro | Powered by OpenAI & MCP")
        embed.timestamp = datetime.now()
        
        return embed
    
    def format_status_embed(self, health_status: Dict[str, Any]) -> discord.Embed:
        """Create system status embed"""
        color = 0x00d4aa if health_status.get("calendar") or health_status.get("notion") else 0xff6b6b
        
        embed = discord.Embed(
            title="🔍 System Status",
            color=color,
            timestamp=datetime.now()
        )
        
        # Service status
        calendar_status = "✅ Online" if health_status.get("calendar") else "❌ Offline"
        notion_status = "✅ Online" if health_status.get("notion") else "❌ Offline"
        
        embed.add_field(name="📅 Calendar Service", value=calendar_status, inline=True)
        embed.add_field(name="📝 Notion Service", value=notion_status, inline=True)
        embed.add_field(name="🤖 AI Service", value="✅ Online", inline=True)
        
        # User info
        if health_status.get("user_email"):
            embed.add_field(
                name="👤 Default User",
                value=health_status["user_email"],
                inline=False
            )
        
        # Error info
        if health_status.get("error"):
            embed.add_field(
                name="⚠️ Error",
                value=self._truncate_text(health_status["error"], self.max_field_value_length),
                inline=False
            )
        
        embed.set_footer(text="System Health Check")
        
        return embed