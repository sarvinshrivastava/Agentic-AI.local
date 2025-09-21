#!/usr/bin/env python3
"""
Test suite for Discord Bot Integration
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

# Import modules to test
from discord_session_manager import DiscordSessionManager, UserSession
from discord_message_adapter import MessageAdapter
from discord_security import SecurityManager, PermissionLevel
from calendar_assistant_service import CalendarAssistantService, CalendarAssistantServicePool
from discord_bot_config import DiscordConfig, CalendarAssistantConfig, IntegrationConfig


class TestUserSession(unittest.TestCase):
    """Test UserSession class"""
    
    def setUp(self):
        self.session = UserSession(
            user_id="123456789",
            channel_id="987654321",
            user_email="test@example.com"
        )
    
    def test_session_creation(self):
        """Test basic session creation"""
        self.assertEqual(self.session.user_id, "123456789")
        self.assertEqual(self.session.channel_id, "987654321")
        self.assertEqual(self.session.user_email, "test@example.com")
        self.assertIsInstance(self.session.last_activity, datetime)
    
    def test_update_activity(self):
        """Test activity update"""
        old_time = self.session.last_activity
        self.session.update_activity()
        self.assertGreater(self.session.last_activity, old_time)
    
    def test_session_expiry(self):
        """Test session expiry logic"""
        # Test non-expired session
        self.assertFalse(self.session.is_expired(1800))  # 30 minutes
        
        # Test expired session
        self.session.last_activity = datetime.now() - timedelta(seconds=2000)
        self.assertTrue(self.session.is_expired(1800))
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        # First 5 requests should succeed
        for i in range(5):
            self.assertTrue(self.session.check_rate_limit(5, 60))
        
        # 6th request should fail
        self.assertFalse(self.session.check_rate_limit(5, 60))


class TestDiscordSessionManager(unittest.IsolatedAsyncioTestCase):
    """Test DiscordSessionManager class"""
    
    async def asyncSetUp(self):
        self.manager = DiscordSessionManager(
            session_timeout=1800,
            max_sessions=10,
            cleanup_interval=300
        )
        await self.manager.start()
    
    async def asyncTearDown(self):
        await self.manager.stop()
    
    async def test_session_creation(self):
        """Test session creation and retrieval"""
        session = self.manager.get_or_create_session(
            "user123", "channel456", "test@example.com"
        )
        
        self.assertEqual(session.user_id, "user123")
        self.assertEqual(session.channel_id, "channel456")
        self.assertEqual(session.user_email, "test@example.com")
    
    async def test_session_reuse(self):
        """Test that same user gets same session"""
        session1 = self.manager.get_or_create_session(
            "user123", "channel456", "test@example.com"
        )
        session2 = self.manager.get_or_create_session(
            "user123", "channel789", "test@example.com"
        )
        
        self.assertEqual(session1.user_id, session2.user_id)
        # Channel should update
        self.assertEqual(session2.channel_id, "channel789")
    
    async def test_conversation_reset(self):
        """Test conversation reset functionality"""
        session = self.manager.get_or_create_session(
            "user123", "channel456", "test@example.com"
        )
        session.conversation_history = [{"role": "user", "content": "test"}]
        
        result = self.manager.reset_conversation("user123")
        self.assertTrue(result)
        self.assertEqual(len(session.conversation_history), 0)
    
    async def test_rate_limiting(self):
        """Test rate limiting integration"""
        # Create session first
        self.manager.get_or_create_session(
            "user123", "channel456", "test@example.com"
        )
        
        # First few requests should pass
        for i in range(5):
            self.assertTrue(self.manager.check_rate_limit("user123"))
        
        # Subsequent requests should fail
        self.assertFalse(self.manager.check_rate_limit("user123"))


class TestMessageAdapter(unittest.TestCase):
    """Test MessageAdapter class"""
    
    def setUp(self):
        self.adapter = MessageAdapter()
        
        # Mock Discord message
        self.mock_message = Mock()
        self.mock_message.content = "Hello @bot, schedule a meeting"
        self.mock_message.attachments = []
        self.mock_message.embeds = []
        self.mock_message.guild = Mock()
        self.mock_message.guild.name = "Test Server"
        self.mock_message.channel = Mock()
        self.mock_message.channel.name = "general"
    
    def test_discord_to_assistant_conversion(self):
        """Test conversion from Discord message to assistant format"""
        result = self.adapter.discord_to_assistant(self.mock_message)
        
        self.assertIsInstance(result, str)
        self.assertIn("Hello", result)
        self.assertIn("Test Server", result)
        self.assertIn("general", result)
    
    def test_assistant_to_discord_conversion(self):
        """Test conversion from assistant response to Discord format"""
        response = "I've scheduled your meeting for tomorrow at 2 PM."
        result = self.adapter.assistant_to_discord(response, use_embeds=True)
        
        self.assertIsInstance(result, dict)
        self.assertTrue("embeds" in result or "content" in result)
    
    def test_message_splitting(self):
        """Test long message splitting"""
        long_message = "A" * 3000  # Longer than Discord limit
        chunks = self.adapter._split_message(long_message, 2000)
        
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 2000)
    
    def test_help_message_creation(self):
        """Test help message embed creation"""
        embed = self.adapter.format_help_message()
        
        # Should be Discord Embed object (mock for testing)
        self.assertIsNotNone(embed)


class TestSecurityManager(unittest.IsolatedAsyncioTestCase):
    """Test SecurityManager class"""
    
    async def asyncSetUp(self):
        self.security = SecurityManager()
    
    async def test_user_permission_creation(self):
        """Test user permission creation"""
        mock_user = Mock()
        mock_user.id = 123456789
        
        result = await self.security.check_user_permissions(mock_user)
        self.assertTrue(result)
        
        # Check if permissions were created
        permissions = self.security._get_or_create_permissions("123456789")
        self.assertEqual(permissions.permission_level, PermissionLevel.BASIC)
    
    async def test_admin_permissions(self):
        """Test admin user permissions"""
        # Mock admin user (from config)
        if self.security._user_permissions:
            admin_id = list(self.security._user_permissions.keys())[0]
            permissions = self.security._user_permissions[admin_id]
            self.assertEqual(permissions.permission_level, PermissionLevel.ADMIN)
    
    async def test_user_restriction(self):
        """Test user restriction functionality"""
        admin_id = "admin123"
        target_id = "user456"
        
        # Create admin permissions manually for test
        self.security._user_permissions[admin_id] = Mock()
        self.security._user_permissions[admin_id].permission_level = PermissionLevel.ADMIN
        
        result = await self.security.restrict_user(admin_id, target_id, 30, "Testing")
        self.assertTrue(result)
    
    async def test_suspicious_activity_reporting(self):
        """Test suspicious activity reporting"""
        await self.security.report_suspicious_activity(
            "user123", 
            "RAPID_REQUESTS", 
            {"count": 20}
        )
        
        self.assertIn("user123", self.security._suspicious_activity)
    
    def test_audit_log_retrieval(self):
        """Test audit log functionality"""
        logs = self.security.get_audit_logs(limit=10)
        self.assertIsInstance(logs, list)


class TestCalendarAssistantService(unittest.IsolatedAsyncioTestCase):
    """Test CalendarAssistantService class"""
    
    async def asyncSetUp(self):
        with patch('calendar_assistant_service.CalendarAssistantPro'):
            with patch('calendar_assistant_service.MCPOrchestratorPro'):
                self.service = CalendarAssistantService("test@example.com")
    
    @patch('calendar_assistant_service.MCPOrchestratorPro')
    async def test_service_initialization(self, mock_orchestrator):
        """Test service initialization"""
        mock_orchestrator_instance = AsyncMock()
        mock_orchestrator_instance.health_check.return_value = {
            "calendar": True, "notion": True
        }
        mock_orchestrator.return_value = mock_orchestrator_instance
        
        result = await self.service.initialize()
        self.assertTrue(result)
    
    @patch('calendar_assistant_service.CalendarAssistantPro')
    @patch('calendar_assistant_service.MCPOrchestratorPro')
    async def test_message_processing(self, mock_orchestrator, mock_assistant):
        """Test message processing"""
        # Mock the assistant and orchestrator
        mock_assistant_instance = Mock()
        mock_assistant_instance.conversation_history = []
        mock_assistant_instance.system_prompt = "test prompt"
        mock_assistant_instance.openai_client = Mock()
        mock_assistant_instance.max_iterations = 10
        
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        
        mock_assistant_instance.openai_client.chat.completions.create.return_value = mock_response
        mock_assistant.return_value = mock_assistant_instance
        
        # Mock orchestrator
        mock_orchestrator_instance = AsyncMock()
        mock_orchestrator_instance.get_all_tool_specs.return_value = []
        mock_orchestrator.return_value = mock_orchestrator_instance
        
        self.service._assistant = mock_assistant_instance
        self.service._orchestrator = mock_orchestrator_instance
        self.service._is_initialized = True
        
        response, history = await self.service.process_message("Test message")
        
        self.assertIsInstance(response, str)
        self.assertIsInstance(history, list)


class TestCalendarAssistantServicePool(unittest.IsolatedAsyncioTestCase):
    """Test CalendarAssistantServicePool class"""
    
    async def asyncSetUp(self):
        self.pool = CalendarAssistantServicePool(max_instances=5, cleanup_interval=60)
        await self.pool.start()
    
    async def asyncTearDown(self):
        await self.pool.stop()
    
    @patch('calendar_assistant_service.CalendarAssistantService')
    async def test_service_creation(self, mock_service_class):
        """Test service creation in pool"""
        mock_service = AsyncMock()
        mock_service.initialize.return_value = True
        mock_service_class.return_value = mock_service
        
        service = await self.pool.get_service("test@example.com")
        self.assertIsNotNone(service)
    
    def test_pool_statistics(self):
        """Test pool statistics"""
        stats = self.pool.get_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn("active_services", stats)
        self.assertIn("max_instances", stats)


class TestIntegrationConfig(unittest.TestCase):
    """Test configuration classes"""
    
    def test_config_creation(self):
        """Test configuration object creation"""
        config = IntegrationConfig()
        
        self.assertIsInstance(config.discord, DiscordConfig)
        self.assertIsInstance(config.assistant, CalendarAssistantConfig)
    
    def test_config_validation(self):
        """Test configuration validation"""
        config = IntegrationConfig()
        
        # Should have validation issues (missing tokens)
        issues = config.validate()
        self.assertGreater(len(issues), 0)
    
    @patch.dict('os.environ', {
        'DISCORD_BOT_TOKEN': 'test_token',
        'OPENAI_API_KEY': 'test_key'
    })
    def test_config_from_env(self):
        """Test loading configuration from environment"""
        config = IntegrationConfig.load_from_env()
        
        self.assertEqual(config.discord.bot_token, 'test_token')


class MockDiscordObjects:
    """Helper class for creating mock Discord objects"""
    
    @staticmethod
    def create_mock_user(user_id: int = 123456789, username: str = "testuser"):
        """Create a mock Discord user"""
        user = Mock()
        user.id = user_id
        user.name = username
        user.display_name = username
        user.bot = False
        return user
    
    @staticmethod
    def create_mock_guild(guild_id: int = 987654321, name: str = "Test Server"):
        """Create a mock Discord guild"""
        guild = Mock()
        guild.id = guild_id
        guild.name = name
        guild.system_channel = Mock()
        return guild
    
    @staticmethod
    def create_mock_channel(channel_id: int = 555666777, name: str = "general"):
        """Create a mock Discord channel"""
        channel = Mock()
        channel.id = channel_id
        channel.name = name
        return channel
    
    @staticmethod
    def create_mock_message(content: str = "Hello bot!", 
                           user_id: int = 123456789,
                           channel_id: int = 555666777):
        """Create a mock Discord message"""
        message = Mock()
        message.content = content
        message.author = MockDiscordObjects.create_mock_user(user_id)
        message.channel = MockDiscordObjects.create_mock_channel(channel_id)
        message.guild = MockDiscordObjects.create_mock_guild()
        message.attachments = []
        message.embeds = []
        message.mentions = []
        return message


# Integration tests
class TestFullIntegration(unittest.IsolatedAsyncioTestCase):
    """Test full integration scenarios"""
    
    async def asyncSetUp(self):
        self.session_manager = DiscordSessionManager()
        self.message_adapter = MessageAdapter()
        self.security_manager = SecurityManager()
        
        await self.session_manager.start()
    
    async def asyncTearDown(self):
        await self.session_manager.stop()
    
    async def test_user_workflow(self):
        """Test complete user interaction workflow"""
        # Create mock user and message
        mock_user = MockDiscordObjects.create_mock_user()
        mock_message = MockDiscordObjects.create_mock_message()
        
        # Check permissions
        can_use = await self.security_manager.check_user_permissions(mock_user)
        self.assertTrue(can_use)
        
        # Create session
        session = self.session_manager.get_or_create_session(
            str(mock_user.id), 
            str(mock_message.channel.id),
            "test@example.com"
        )
        self.assertIsNotNone(session)
        
        # Process message
        assistant_message = self.message_adapter.discord_to_assistant(mock_message)
        self.assertIsInstance(assistant_message, str)
        
        # Convert response back to Discord format
        response_data = self.message_adapter.assistant_to_discord(
            "Test response from assistant"
        )
        self.assertIsInstance(response_data, dict)


if __name__ == "__main__":
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test cases
    test_classes = [
        TestUserSession,
        TestDiscordSessionManager,
        TestMessageAdapter,
        TestSecurityManager,
        TestCalendarAssistantService,
        TestCalendarAssistantServicePool,
        TestIntegrationConfig,
        TestFullIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Exit with error code if tests failed
    exit(0 if result.wasSuccessful() else 1)