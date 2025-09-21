#!/usr/bin/env python3
"""
Discord Bot Interface - Main Discord bot implementation for Calendar Assistant Pro
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import traceback

import discord
from discord.ext import commands, tasks

from discord_bot_config import config
from calendar_assistant_service import CalendarAssistantServicePool
from discord_session_manager import DiscordSessionManager
from discord_message_adapter import MessageAdapter

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.discord.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CalendarAssistantBot(commands.Bot):
    """
    Discord bot for Calendar Assistant Pro integration
    """
    
    def __init__(self):
        # Setup bot intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True  # Fixed: use dm_messages instead of direct_messages
        
        super().__init__(
            command_prefix=config.discord.command_prefix,
            intents=intents,
            help_command=None  # We'll create a custom help command
        )
        
        # Initialize components
        self.service_pool = CalendarAssistantServicePool(
            max_instances=config.discord.max_concurrent_sessions,
            cleanup_interval=config.discord.session_cleanup_interval
        )
        
        self.session_manager = DiscordSessionManager(
            session_timeout=config.discord.session_timeout,
            max_sessions=config.discord.max_concurrent_sessions,
            cleanup_interval=config.discord.session_cleanup_interval,
            rate_limit_requests=config.discord.rate_limit_requests,
            rate_limit_window=config.discord.rate_limit_window
        )
        
        self.message_adapter = MessageAdapter()
        self._is_ready = False
    
    async def setup_hook(self):
        """Setup hook called when bot starts"""
        logger.info("Setting up Calendar Assistant Bot...")
        
        # Start service components
        await self.service_pool.start()
        await self.session_manager.start()
        
        # Setup slash commands if enabled
        if config.discord.enable_slash_commands:
            await self.setup_slash_commands()
        
        # Start background tasks
        self.health_check_task.start()
        
        logger.info("Calendar Assistant Bot setup completed")
    
    async def on_ready(self):
        """Called when bot is ready"""
        self._is_ready = True
        logger.info(f"✅ {self.user} is ready and online!")
        logger.info(f"Bot ID: {self.user.id}")
        logger.info(f"Servers: {len(self.guilds)}")
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="your calendar | @me for help"
        )
        await self.change_presence(activity=activity, status=discord.Status.online)
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if message should trigger bot response
        should_respond = await self._should_respond_to_message(message)
        if not should_respond:
            await self.process_commands(message)
            return
        
        # Process the message
        await self._handle_assistant_message(message)
    
    async def _should_respond_to_message(self, message: discord.Message) -> bool:
        """Determine if bot should respond to the message"""
        user_id = str(message.author.id)
        message_content = message.content.strip().lower()
        
        # Check for conversation end commands first
        if message_content in [f"!{cmd}" for cmd in config.discord.conversation_end_commands] + \
                              [f"/{cmd}" for cmd in config.discord.conversation_end_commands] + \
                              config.discord.conversation_end_commands:
            # End the conversation if it's active
            if self.session_manager.is_conversation_active(user_id):
                self.session_manager.end_conversation(user_id)
                await message.reply("✅ Conversation ended. Mention me again to start a new conversation!", mention_author=False)
            return False  # Don't process the end command as a regular message
        
        # Always respond to DMs if enabled
        if isinstance(message.channel, discord.DMChannel):
            return config.discord.dm_trigger
        
        # Check for mentions if enabled (this starts a new conversation)
        if config.discord.mention_trigger and self.user in message.mentions:
            # Start conversation flow if enabled
            if config.discord.conversation_flow_enabled:
                session = self.session_manager.get_session(user_id)
                if session:
                    self.session_manager.start_conversation(user_id)
            return True
        
        # Check if user has an active conversation in this channel
        if config.discord.conversation_flow_enabled:
            session = self.session_manager.get_session(user_id)
            if session and session.conversation_active and session.channel_id == str(message.channel.id):
                # Check if conversation has expired
                if self.session_manager.is_conversation_expired(user_id, config.discord.conversation_flow_timeout):
                    self.session_manager.end_conversation(user_id)
                    await message.reply("⏰ Conversation expired due to inactivity. Mention me again to start a new conversation!", mention_author=False)
                    return False
                # Conversation is active and valid, continue responding
                return True
        
        # Check if in a thread created by the bot
        if isinstance(message.channel, discord.Thread):
            session = self.session_manager.get_session(user_id)
            if session and session.thread_id == str(message.channel.id):
                return True
        
        return False
    
    async def _handle_assistant_message(self, message: discord.Message):
        """Handle message that should be processed by assistant"""
        user_id = str(message.author.id)
        channel_id = str(message.channel.id)
        is_dm = isinstance(message.channel, discord.DMChannel)
        
        try:
            # Check rate limits
            if not self.session_manager.check_rate_limit(user_id):
                await message.reply(
                    "⏰ You're sending messages too quickly. Please wait a moment before trying again.",
                    mention_author=False
                )
                return
            
            # Check server permissions
            if not await self._check_permissions(message):
                return
            
            # Get or create user session
            user_email = await self._get_user_email(message.author)
            session = self.session_manager.get_or_create_session(
                user_id, channel_id, user_email, is_dm
            )
            
            # Show typing indicator
            async with message.channel.typing():
                # Convert Discord message to assistant format
                assistant_message = self.message_adapter.discord_to_assistant(message)
                
                # Get assistant service for user
                assistant_service = await self.service_pool.get_service(user_email)
                
                # Process message with assistant
                response, conversation_history = await assistant_service.process_message(
                    assistant_message, 
                    session.conversation_history
                )
                
                # Update session with new conversation history
                self.session_manager.update_conversation_history(user_id, conversation_history)
                
                # Convert response to Discord format
                discord_response = self.message_adapter.assistant_to_discord(
                    response, 
                    config.discord.use_embeds
                )
                
                # Send response
                await self._send_response(message, discord_response, session)
        
        except Exception as e:
            logger.error(f"Error handling message from {user_id}: {e}")
            logger.error(traceback.format_exc())
            
            await message.reply(
                "❌ I encountered an error processing your request. Please try again later.",
                mention_author=False
            )
    
    async def _send_response(self, original_message: discord.Message, response_data: Dict[str, Any], session):
        """Send response to Discord channel"""
        try:
            # Create thread for complex conversations if enabled and not in DM
            if (config.discord.use_threads and 
                not isinstance(original_message.channel, discord.DMChannel) and 
                not session.thread_id and
                len(session.conversation_history) > 2):
                
                thread = await original_message.create_thread(
                    name=f"Calendar Chat - {original_message.author.display_name}",
                    auto_archive_duration=1440  # 24 hours
                )
                self.session_manager.set_thread_id(str(original_message.author.id), str(thread.id))
                channel = thread
            else:
                channel = original_message.channel
            
            # Send main response
            if "embeds" in response_data:
                await channel.send(embeds=response_data["embeds"])
            elif "content" in response_data:
                await channel.send(response_data["content"])
            
            # Send follow-up messages if any
            if "follow_up" in response_data:
                for follow_up in response_data["follow_up"]:
                    await channel.send(follow_up)
        
        except Exception as e:
            logger.error(f"Error sending response: {e}")
            await original_message.reply(
                "❌ I had trouble sending my response. Please try again.",
                mention_author=False
            )
    
    async def _check_permissions(self, message: discord.Message) -> bool:
        """Check if user has permission to use the bot"""
        # Check allowed servers
        if (config.discord.allowed_servers and 
            message.guild and 
            str(message.guild.id) not in config.discord.allowed_servers):
            await message.reply(
                "❌ This bot is not authorized for use in this server.",
                mention_author=False
            )
            return False
        
        return True
    
    async def _get_user_email(self, user: discord.User) -> str:
        """Get user email (for now, use default)"""
        # TODO: Implement user email mapping system
        return config.assistant.default_user_email
    
    # =============================================================================
    # Slash Commands
    # =============================================================================
    
    async def setup_slash_commands(self):
        """Setup slash commands"""
        @self.tree.command(name="help", description="Get help with Calendar Assistant Pro")
        async def help_command(interaction: discord.Interaction):
            embed = self.message_adapter.format_help_message()
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @self.tree.command(name="status", description="Check system status")
        async def status_command(interaction: discord.Interaction):
            user_email = await self._get_user_email(interaction.user)
            service = await self.service_pool.get_service(user_email)
            health_status = await service.get_health_status()
            
            embed = self.message_adapter.format_status_embed(health_status)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @self.tree.command(name="reset", description="Reset your conversation history")
        async def reset_command(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            if self.session_manager.reset_conversation(user_id):
                await interaction.response.send_message(
                    "✅ Your conversation history has been reset!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "ℹ️ No active conversation found to reset.",
                    ephemeral=True
                )
        
        @self.tree.command(name="stats", description="Show bot statistics (admin only)")
        async def stats_command(interaction: discord.Interaction):
            if str(interaction.user.id) not in config.discord.admin_users:
                await interaction.response.send_message(
                    "❌ You don't have permission to view statistics.",
                    ephemeral=True
                )
                return
            
            session_stats = self.session_manager.get_stats()
            service_stats = self.service_pool.get_stats()
            
            embed = discord.Embed(
                title="📊 Bot Statistics",
                color=0x00a8ff,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Sessions",
                value=f"Active: {session_stats['active_sessions']}\nDM: {session_stats['dm_sessions']}\nServer: {session_stats['server_sessions']}",
                inline=True
            )
            
            embed.add_field(
                name="Services",
                value=f"Active: {service_stats['active_services']}\nMax: {service_stats['max_instances']}",
                inline=True
            )
            
            embed.add_field(
                name="Threads",
                value=f"Active: {session_stats['active_threads']}",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @self.tree.command(name="end", description="End active conversation with the bot")
        async def end_conversation_command(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            if self.session_manager.is_conversation_active(user_id):
                self.session_manager.end_conversation(user_id)
                await interaction.response.send_message(
                    "✅ Conversation ended! Mention me again to start a new conversation.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "ℹ️ No active conversation found to end.",
                    ephemeral=True
                )
        
        # Sync slash commands
        await self.tree.sync()
        logger.info("Slash commands synced")
    
    # =============================================================================
    # Traditional Commands
    # =============================================================================
    
    @commands.command(name="help")
    async def help_command(self, ctx):
        """Help command"""
        embed = self.message_adapter.format_help_message()
        await ctx.send(embed=embed)
    
    @commands.command(name="status")
    async def status_command(self, ctx):
        """Status command"""
        user_email = await self._get_user_email(ctx.author)
        service = await self.service_pool.get_service(user_email)
        health_status = await service.get_health_status()
        
        embed = self.message_adapter.format_status_embed(health_status)
        await ctx.send(embed=embed)
    
    @commands.command(name="reset")
    async def reset_command(self, ctx):
        """Reset conversation command"""
        user_id = str(ctx.author.id)
        if self.session_manager.reset_conversation(user_id):
            await ctx.send("✅ Your conversation history has been reset!")
        else:
            await ctx.send("ℹ️ No active conversation found to reset.")
    
    @commands.command(name="end")
    async def end_conversation_command(self, ctx):
        """End active conversation command"""
        user_id = str(ctx.author.id)
        if self.session_manager.is_conversation_active(user_id):
            self.session_manager.end_conversation(user_id)
            await ctx.send("✅ Conversation ended! Mention me again to start a new conversation.")
        else:
            await ctx.send("ℹ️ No active conversation found to end.")
    
    # =============================================================================
    # Background Tasks
    # =============================================================================
    
    @tasks.loop(seconds=300)  # 5 minutes
    async def health_check_task(self):
        """Periodic health check"""
        if not self._is_ready:
            return
        
        try:
            # Clean up expired conversations
            self.session_manager._cleanup_expired_conversations(config.discord.conversation_flow_timeout)
            
            # This is a basic health check - could be expanded
            logger.debug("Health check completed")
        except Exception as e:
            logger.error(f"Health check failed: {e}")
    
    @health_check_task.before_loop
    async def before_health_check(self):
        """Wait until bot is ready"""
        await self.wait_until_ready()
    
    # =============================================================================
    # Event Handlers
    # =============================================================================
    
    async def on_thread_delete(self, thread):
        """Handle thread deletion"""
        thread_id = str(thread.id)
        self.session_manager.cleanup_thread(thread_id)
    
    async def on_guild_join(self, guild):
        """Handle joining new guild"""
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        
        # Send welcome message to system channel if available
        if guild.system_channel:
            embed = discord.Embed(
                title="👋 Calendar Assistant Pro",
                description="Thanks for adding me! I'm here to help with calendar and workspace management.",
                color=0x00a8ff
            )
            embed.add_field(
                name="Getting Started",
                value="• Mention me (@CalendarAssistantPro) to start a conversation\n• Use `/help` for available commands\n• I can help with Google Calendar and Notion integration",
                inline=False
            )
            
            try:
                await guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"Cannot send welcome message in {guild.name} - no permission")
    
    async def on_error(self, event, *args, **kwargs):
        """Handle bot errors"""
        logger.error(f"Bot error in event {event}: {traceback.format_exc()}")
    
    async def close(self):
        """Clean shutdown"""
        logger.info("Shutting down Calendar Assistant Bot...")
        
        # Stop background tasks
        self.health_check_task.cancel()
        
        # Stop services
        await self.service_pool.stop()
        await self.session_manager.stop()
        
        await super().close()
        logger.info("Calendar Assistant Bot shut down completed")


# =============================================================================
# Bot Instance and Runner
# =============================================================================

def create_bot() -> CalendarAssistantBot:
    """Create and return bot instance"""
    return CalendarAssistantBot()


async def run_bot():
    """Run the Discord bot"""
    # Validate configuration
    config_issues = config.validate()
    if config_issues:
        logger.error("Configuration issues found:")
        for issue in config_issues:
            logger.error(f"  - {issue}")
        return
    
    # Create and run bot
    bot = create_bot()
    
    try:
        await bot.start(config.discord.bot_token)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Bot encountered error: {e}")
        logger.error(traceback.format_exc())
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(run_bot())