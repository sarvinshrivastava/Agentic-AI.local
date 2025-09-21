#!/usr/bin/env python3
"""
Main startup script for Calendar Assistant Pro Discord Bot
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add current directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from discord_bot import run_bot
from discord_bot_config import config

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.discord.log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('discord_bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def check_requirements():
    """Check if all required dependencies are installed"""
    # Map pip package names to import names
    required_packages = {
        'discord': 'discord.py',
        'openai': 'openai', 
        'dotenv': 'python-dotenv',
        'fastmcp': 'fastmcp'
    }
    
    missing_packages = []
    for import_name, pip_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(pip_name)
    
    if missing_packages:
        logger.error(f"Missing required packages: {', '.join(missing_packages)}")
        logger.error("Please install with: pip install -r requirements.txt")
        return False
    
    return True


def check_environment():
    """Check if required environment variables are set"""
    required_vars = [
        'DISCORD_BOT_TOKEN',
        'OPENAI_API_KEY',
        'DEFAULT_USER_EMAIL'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file or set these variables")
        return False
    
    return True


def show_startup_info():
    """Display startup information"""
    logger.info("=" * 70)
    logger.info("🤖 Calendar Assistant Pro Discord Bot")
    logger.info("=" * 70)
    logger.info(f"📧 Default User Email: {config.assistant.default_user_email}")
    logger.info(f"🔧 Command Prefix: {config.discord.command_prefix}")
    logger.info(f"⏰ Session Timeout: {config.discord.session_timeout}s")
    logger.info(f"👥 Max Sessions: {config.discord.max_concurrent_sessions}")
    logger.info(f"📊 Rate Limit: {config.discord.rate_limit_requests} req/min")
    logger.info(f"✨ Features: Slash Commands={config.discord.enable_slash_commands}, "
                f"Embeds={config.discord.use_embeds}, Threads={config.discord.use_threads}")
    logger.info("=" * 70)


async def main():
    """Main function"""
    try:
        logger.info("Starting Calendar Assistant Pro Discord Bot...")
        
        # Check requirements
        if not check_requirements():
            sys.exit(1)
        
        if not check_environment():
            sys.exit(1)
        
        # Show startup info
        show_startup_info()
        
        # Run the bot
        await run_bot()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Calendar Assistant Pro Discord Bot stopped")


if __name__ == "__main__":
    # Handle Windows-specific event loop policy
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())