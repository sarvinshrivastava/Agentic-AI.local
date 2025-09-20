# 🤖 Calendar Assistant Pro Discord Bot

**An intelligent Discord bot that integrates your existing Calendar Assistant Pro with Discord, providing seamless calendar and workspace management without modifying your core codebase.**

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Discord Commands](#-discord-commands)
- [Deployment](#-deployment)
- [Development](#-development)
- [Security](#-security)
- [Monitoring](#-monitoring)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

## 🎯 Overview

This Discord bot acts as a sophisticated middleware layer that connects Discord users with your existing `CalendarAssistantPro` system. It preserves your current architecture while adding powerful Discord integration capabilities.

### Key Benefits

- ✅ **Zero Code Modification** - Your existing `CalendarAssistantPro` remains unchanged
- 🔒 **Enterprise Security** - Built-in authentication, rate limiting, and audit logging
- 🚀 **Production Ready** - Docker deployment, monitoring, and health checks
- 💬 **Discord Native** - Rich embeds, slash commands, threads, and reactions
- 🏗️ **Modular Architecture** - Clean separation of concerns with extensible design

### Architecture Flow

```
Discord User → Discord Bot → Message Adapter → Calendar Assistant Service → CalendarAssistantPro → MCP Orchestrator → Google Calendar/Notion
```

## 🏗️ Architecture

### Core Components

| Component                           | Purpose                | Key Features                                          |
| ----------------------------------- | ---------------------- | ----------------------------------------------------- |
| **`discord_bot.py`**                | Main bot interface     | Message routing, event handling, slash commands       |
| **`discord_message_adapter.py`**    | Message transformation | Discord ↔ Assistant format conversion, embed creation |
| **`discord_session_manager.py`**    | Session tracking       | User sessions, conversation history, cleanup          |
| **`calendar_assistant_service.py`** | Service wrapper        | Programmatic interface to CalendarAssistantPro        |
| **`discord_security.py`**           | Security layer         | Authentication, permissions, audit logging            |
| **`discord_bot_config.py`**         | Configuration          | Environment-based settings, validation                |

### Data Flow

1. **Discord Message** → Bot receives mention/DM
2. **Permission Check** → Security manager validates user
3. **Session Management** → Get/create user session with conversation history
4. **Message Adaptation** → Convert Discord message to assistant format
5. **AI Processing** → CalendarAssistantPro processes request via MCP
6. **Response Formatting** → Convert AI response to Discord embeds/messages
7. **Thread Management** → Create/use Discord threads for complex conversations

## ✨ Features

### 🗓️ Calendar Management

- **Event Operations**: Create, read, update, delete calendar events
- **Smart Scheduling**: AI-powered meeting scheduling and conflict detection
- **Time Zone Support**: Automatic IST handling with user-friendly formatting
- **Recurring Events**: Full support for recurring event patterns

### 📝 Notion Integration

- **Document Search**: Intelligent search across Notion workspace
- **Content Retrieval**: Fetch and display document content
- **Meeting Context**: Link calendar events with related documents

### 💬 Discord Features

- **Rich Embeds**: Beautiful calendar event displays with color coding
- **Slash Commands**: Modern Discord command interface (`/help`, `/status`, `/reset`)
- **Thread Support**: Automatic thread creation for complex conversations
- **Direct Messages**: Private calendar management via DMs
- **Mention Detection**: Responds to @mentions in channels

### 🔒 Security & Administration

- **Permission Levels**: Basic, Trusted, Admin user roles
- **Rate Limiting**: Per-user request throttling (5 req/min default)
- **Audit Logging**: Comprehensive security event tracking
- **Data Sanitization**: Automatic removal of sensitive information
- **Server Restrictions**: Whitelist allowed Discord servers

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Discord Developer Account
- OpenAI API Key
- Running Google Calendar MCP Server
- Notion MCP Server (optional)

### 1. Clone and Setup

```bash
# Navigate to your existing project directory
cd "e:\Projects\Project~ AI Cohort\AI-Cohort-13-09"

# Install dependencies
pip install -r requirements.txt
```

### 2. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create New Application → Bot
3. Copy Bot Token and Application ID
4. Enable **Message Content Intent** in Bot settings
5. Generate OAuth2 URL with scopes: `bot`, `applications.commands`
6. Required permissions: `Send Messages`, `Use Slash Commands`, `Create Public Threads`, `Embed Links`

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_APPLICATION_ID=your_app_id_here
OPENAI_API_KEY=your_openai_key_here
DEFAULT_USER_EMAIL=your_email@gmail.com
```

### 4. Start the Bot

```bash
# Run directly
python main.py

# Or with Docker
docker-compose up discord-bot
```

### 5. Test Integration

1. Invite bot to your Discord server
2. Mention the bot: `@CalendarAssistantPro what's on my calendar today?`
3. Try slash commands: `/help`, `/status`
4. Send a DM for private calendar access

## ⚙️ Configuration

### Environment Variables

| Variable                  | Required | Default | Description                                |
| ------------------------- | -------- | ------- | ------------------------------------------ |
| `DISCORD_BOT_TOKEN`       | ✅       | -       | Discord bot authentication token           |
| `OPENAI_API_KEY`          | ✅       | -       | OpenAI API key for AI processing           |
| `DEFAULT_USER_EMAIL`      | ✅       | -       | Default email for calendar operations      |
| `DISCORD_COMMAND_PREFIX`  | ❌       | `!`     | Prefix for traditional commands            |
| `SESSION_TIMEOUT`         | ❌       | `1800`  | Session timeout in seconds                 |
| `MAX_CONCURRENT_SESSIONS` | ❌       | `100`   | Maximum concurrent user sessions           |
| `ADMIN_USERS`             | ❌       | -       | Comma-separated list of admin Discord IDs  |
| `ALLOWED_SERVERS`         | ❌       | -       | Comma-separated list of allowed server IDs |

### Feature Toggles

```env
ENABLE_SLASH_COMMANDS=true    # Enable /command interface
USE_EMBEDS=true               # Use rich message embeds
USE_THREADS=true              # Create conversation threads
ENABLE_CALENDAR_EMBEDS=true   # Rich calendar event displays
```

### Security Settings

```env
RATE_LIMIT_REQUESTS=5         # Requests per minute per user
RATE_LIMIT_WINDOW=60          # Rate limit window (seconds)
LOG_LEVEL=INFO                # Logging verbosity
AUDIT_LOG_CHANNEL=            # Discord channel for audit logs
```

## 💬 Discord Commands

### Slash Commands

| Command   | Description                 | Usage     |
| --------- | --------------------------- | --------- |
| `/help`   | Show help information       | `/help`   |
| `/status` | Check system health         | `/status` |
| `/reset`  | Reset conversation history  | `/reset`  |
| `/stats`  | Show bot statistics (admin) | `/stats`  |

### Natural Language

The bot responds to natural language when mentioned or in DMs:

```
# Calendar Operations
@CalendarAssistantPro show my events this week
@CalendarAssistantPro create a meeting tomorrow at 2 PM with John
@CalendarAssistantPro what's my schedule for Friday?
@CalendarAssistantPro reschedule my 3 PM meeting to 4 PM

# Notion Operations
@CalendarAssistantPro search for documents about Q4 planning
@CalendarAssistantPro show me meeting notes from last week
@CalendarAssistantPro find all project documentation

# Combined Operations
@CalendarAssistantPro I have a budget meeting tomorrow, show me the financial reports
@CalendarAssistantPro schedule a project review and pull related documents
```

### Traditional Commands

```bash
!help     # Show help
!status   # System status
!reset    # Reset conversation
```

## 🐳 Deployment

### Docker Deployment (Recommended)

```bash
# Production deployment
docker-compose up -d discord-bot

# With monitoring stack
docker-compose up -d

# Development mode
docker-compose --profile dev up discord-bot-dev
```

### Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run with process manager (PM2, systemd, etc.)
python main.py
```

### Production Considerations

1. **Environment Variables**: Use secure secret management
2. **Resource Limits**: Configure memory/CPU limits (512MB/0.5 CPU recommended)
3. **Health Checks**: Ensure health check endpoints are accessible
4. **Logging**: Configure log rotation and retention
5. **Monitoring**: Set up Prometheus/Grafana dashboard
6. **Backup**: Regular backup of audit logs and session data

## 👨‍💻 Development

### Setup Development Environment

```bash
# Install development dependencies
pip install pytest pytest-asyncio pytest-mock black flake8 mypy

# Run tests
python -m pytest test_discord_integration.py -v

# Code formatting
black *.py

# Type checking
mypy discord_bot.py
```

### Development with Docker

```bash
# Start development container
docker-compose --profile dev up -d discord-bot-dev

# Execute commands in container
docker-compose exec discord-bot-dev python -m pytest -v
docker-compose exec discord-bot-dev black *.py
```

### File Structure

```
e:\Projects\Project~ AI Cohort\AI-Cohort-13-09\
├── calendarassistantpro.py           # Original (unchanged)
├── mcp_orchestrator_pro.py           # Original (unchanged)
├── discord_bot.py                    # Main Discord bot
├── discord_message_adapter.py        # Message format conversion
├── discord_session_manager.py        # Session management
├── discord_security.py               # Security and permissions
├── calendar_assistant_service.py     # Service wrapper
├── discord_bot_config.py             # Configuration management
├── main.py                          # Startup script
├── test_discord_integration.py      # Test suite
├── requirements.txt                 # Dependencies
├── Dockerfile                       # Container definition
├── docker-compose.yml              # Multi-service deployment
├── .env.example                     # Environment template
└── monitoring/                      # Monitoring configuration
    ├── prometheus.yml
    ├── loki-config.yml
    └── grafana/
```

### Testing

```bash
# Run all tests
python test_discord_integration.py

# Run specific test class
python -m pytest test_discord_integration.py::TestDiscordSessionManager -v

# Run with coverage
python -m pytest --cov=discord_bot test_discord_integration.py
```

## 🔒 Security

### Authentication & Authorization

- **Permission Levels**: Basic (default), Trusted, Admin
- **Rate Limiting**: 5 requests/minute per user (configurable)
- **Server Restrictions**: Whitelist allowed Discord servers
- **Admin Commands**: Restricted to configured admin users
- **Data Sanitization**: Automatic removal of sensitive data from responses

### Audit Logging

All security events are logged:

- User authentication attempts
- Permission changes
- Rate limit violations
- Suspicious activity detection
- Admin actions

### Best Practices

1. **Use Environment Variables** for all secrets
2. **Enable Server Restrictions** for production deployment
3. **Configure Admin Users** properly
4. **Monitor Audit Logs** regularly
5. **Keep Dependencies Updated**
6. **Use HTTPS** for webhook endpoints (if implemented)

## 📊 Monitoring

### Health Checks

The bot includes comprehensive health monitoring:

- **Service Health**: Calendar and Notion MCP connectivity
- **Resource Usage**: Memory and CPU monitoring
- **Session Statistics**: Active users and sessions
- **Error Tracking**: Exception rates and types

### Metrics (Prometheus)

Available metrics:

- `discord_bot_sessions_active`
- `discord_bot_requests_total`
- `discord_bot_errors_total`
- `discord_bot_response_time_seconds`

### Dashboards

Access monitoring at:

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Logs**: http://localhost:3100 (Loki)

## 🔧 Troubleshooting

### Common Issues

#### Bot Not Responding

```bash
# Check bot status
docker-compose logs discord-bot

# Verify environment variables
python -c "from discord_bot_config import config; print(config.validate())"

# Test Discord token
python -c "import discord; print('Token valid' if len('BOT_TOKEN') > 50 else 'Invalid token')"
```

#### Permission Errors

- Ensure bot has required Discord permissions
- Check `ADMIN_USERS` configuration
- Verify server is in `ALLOWED_SERVERS` (if configured)

#### Calendar/Notion Integration Issues

```bash
# Check MCP server connectivity
python -c "
import asyncio
from calendar_assistant_service import CalendarAssistantService
async def test():
    service = CalendarAssistantService('test@example.com')
    health = await service.get_health_status()
    print(health)
asyncio.run(test())
"
```

#### High Memory Usage

- Check session cleanup configuration
- Monitor `MAX_CONCURRENT_SESSIONS`
- Review conversation history limits

### Debug Mode

Enable debug logging:

```env
LOG_LEVEL=DEBUG
```

### Error Codes

| Code         | Description                  | Solution                |
| ------------ | ---------------------------- | ----------------------- |
| `CONFIG_001` | Missing environment variable | Check `.env` file       |
| `AUTH_001`   | Invalid Discord token        | Verify bot token        |
| `MCP_001`    | Calendar server unreachable  | Check MCP server status |
| `RATE_001`   | Rate limit exceeded          | Wait or adjust limits   |
| `PERM_001`   | Insufficient permissions     | Check user permissions  |

## 🤝 Contributing

### Development Workflow

1. **Fork** the repository
2. **Create** feature branch (`git checkout -b feature/amazing-feature`)
3. **Test** your changes (`python test_discord_integration.py`)
4. **Format** code (`black *.py`)
5. **Commit** changes (`git commit -m 'Add amazing feature'`)
6. **Push** branch (`git push origin feature/amazing-feature`)
7. **Create** Pull Request

### Code Standards

- **PEP 8** compliance (enforced by Black)
- **Type hints** for all functions
- **Comprehensive tests** for new features
- **Documentation** for public APIs
- **Error handling** for all external calls

### Architecture Guidelines

- **No modifications** to existing `CalendarAssistantPro` code
- **Loose coupling** between Discord and Calendar components
- **Async/await** for all I/O operations
- **Configuration-driven** feature toggles
- **Security-first** design patterns

## 📄 License

This project extends the existing Calendar Assistant Pro with Discord integration capabilities while maintaining compatibility and not modifying the original codebase.

---

## 📞 Support

For issues and questions:

1. **Check Documentation** - Most common issues are covered here
2. **Review Logs** - Enable debug logging for detailed information
3. **Test Connectivity** - Verify MCP servers and Discord API access
4. **Check Configuration** - Validate environment variables and permissions

**Created with ❤️ for seamless Discord integration while preserving your existing Calendar Assistant Pro architecture.**
