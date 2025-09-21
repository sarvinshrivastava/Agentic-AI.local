#!/usr/bin/env python3
"""
Calendar Assistant Service - Service wrapper for CalendarAssistantPro
Provides programmatic interface without modifying the original class
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

from calendarassistantpro import CalendarAssistantPro
from mcp_orchestrator_pro import MCPOrchestratorPro


logger = logging.getLogger(__name__)


class CalendarAssistantService:
    """
    Service wrapper for CalendarAssistantPro that provides programmatic interface
    without modifying the original interactive chat implementation.
    """
    
    def __init__(self, user_email: str):
        """Initialize service with user email"""
        self.user_email = user_email
        self._assistant = CalendarAssistantPro(user_email=user_email)
        self._orchestrator: Optional[MCPOrchestratorPro] = None
        self._is_initialized = False
    
    async def initialize(self) -> bool:
        """Initialize the MCP orchestrator and check health"""
        try:
            self._orchestrator = MCPOrchestratorPro()
            await self._orchestrator.__aenter__()
            
            # Health check
            health = await self._orchestrator.health_check()
            self._is_initialized = True
            
            logger.info(f"Calendar Assistant Service initialized for {self.user_email}")
            logger.info(f"Service health: Calendar={health.get('calendar', False)}, Notion={health.get('notion', False)}")
            
            return health.get('calendar', False) or health.get('notion', False)
        except Exception as e:
            logger.error(f"Failed to initialize Calendar Assistant Service: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup resources"""
        if self._orchestrator:
            try:
                await self._orchestrator.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        self._is_initialized = False
    
    async def process_message(self, message: str, conversation_history: List[Dict[str, Any]] = None) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Process a user message and return AI response with updated conversation history
        
        Args:
            message: User input message
            conversation_history: Previous conversation context
            
        Returns:
            Tuple of (ai_response, updated_conversation_history)
        """
        if not self._is_initialized or not self._orchestrator:
            await self.initialize()
        
        if not self._orchestrator:
            raise RuntimeError("Calendar Assistant Service not properly initialized")
        
        # Initialize conversation history if not provided
        if conversation_history is None:
            conversation_history = []
        
        # Set conversation history in assistant
        self._assistant.conversation_history = conversation_history.copy()
        
        try:
            # Add user message to conversation
            self._assistant.conversation_history.append({
                "role": "user",
                "content": message
            })

            # Get available tools
            tool_specs = await self._orchestrator.get_all_tool_specs()
            
            # Prepare messages for OpenAI
            messages = [{"role": "system", "content": self._assistant.system_prompt}]
            messages.extend(self._assistant.conversation_history[-10:])  # Keep last 10 messages

            # Call OpenAI with function calling
            response = self._assistant.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=[{
                    "type": "function",
                    "function": {
                        "name": spec["name"],
                        "description": spec["description"],
                        "parameters": spec["inputSchema"]
                    }
                } for spec in tool_specs],
                tool_choice="auto"
            )

            message_obj = response.choices[0].message
            
            # Add assistant message to conversation
            assistant_message = {
                "role": "assistant",
                "content": message_obj.content or "",
                "tool_calls": getattr(message_obj, "tool_calls", None)
            }
            self._assistant.conversation_history.append(assistant_message)

            # Handle tool calls if present
            final_response = message_obj.content or ""
            
            if message_obj.tool_calls:
                logger.info(f"Processing {len(message_obj.tool_calls)} tool calls")
                
                # Execute tool calls
                tool_messages = await self._assistant._execute_tool_calls(
                    self._orchestrator, 
                    list(message_obj.tool_calls)
                )
                
                # Add tool results to conversation
                self._assistant.conversation_history.extend(tool_messages)
                
                # Get final response from AI
                iteration = 0
                while iteration < self._assistant.max_iterations:
                    iteration += 1
                    
                    follow_up_messages = [{"role": "system", "content": self._assistant.system_prompt}]
                    follow_up_messages.extend(self._assistant.conversation_history[-10:])
                    
                    follow_up_response = self._assistant.openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=follow_up_messages,
                        tools=[{
                            "type": "function",
                            "function": {
                                "name": spec["name"],
                                "description": spec["description"],
                                "parameters": spec["inputSchema"]
                            }
                        } for spec in tool_specs],
                        tool_choice="auto"
                    )
                    
                    follow_up_message = follow_up_response.choices[0].message
                    
                    if follow_up_message.tool_calls:
                        # More tool calls needed
                        additional_tool_messages = await self._assistant._execute_tool_calls(
                            self._orchestrator, 
                            list(follow_up_message.tool_calls)
                        )
                        
                        self._assistant.conversation_history.append({
                            "role": "assistant",
                            "content": follow_up_message.content or "",
                            "tool_calls": getattr(follow_up_message, "tool_calls", None)
                        })
                        
                        self._assistant.conversation_history.extend(additional_tool_messages)
                    else:
                        # Final response received
                        self._assistant.conversation_history.append({
                            "role": "assistant",
                            "content": follow_up_message.content or ""
                        })
                        
                        final_response = follow_up_message.content or "Task completed successfully!"
                        break
                else:
                    final_response = "Task completed successfully! Is there anything else I can help you with?"
            
            return final_response, self._assistant.conversation_history
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            error_response = f"I apologize, but I encountered an error while processing your request: {str(e)}"
            
            # Add error to conversation history
            self._assistant.conversation_history.append({
                "role": "assistant",
                "content": error_response
            })
            
            return error_response, self._assistant.conversation_history
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the service"""
        if not self._orchestrator:
            return {
                "initialized": False,
                "calendar": False,
                "notion": False,
                "error": "Service not initialized"
            }
        
        try:
            health = await self._orchestrator.health_check()
            return {
                "initialized": self._is_initialized,
                "calendar": health.get("calendar", False),
                "notion": health.get("notion", False),
                "user_email": self.user_email,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "initialized": self._is_initialized,
                "calendar": False,
                "notion": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def reset_conversation(self):
        """Reset conversation history"""
        self._assistant.conversation_history = []
        logger.info(f"Conversation reset for user {self.user_email}")


class CalendarAssistantServicePool:
    """
    Pool manager for CalendarAssistantService instances to handle multiple users
    """
    
    def __init__(self, max_instances: int = 100, cleanup_interval: int = 300):
        self.max_instances = max_instances
        self.cleanup_interval = cleanup_interval
        self._services: Dict[str, CalendarAssistantService] = {}
        self._last_used: Dict[str, datetime] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False
    
    async def start(self):
        """Start the service pool"""
        if not self._is_running:
            self._is_running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("CalendarAssistantServicePool started")
    
    async def stop(self):
        """Stop the service pool and cleanup all instances"""
        self._is_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup all services
        for service in self._services.values():
            await service.cleanup()
        
        self._services.clear()
        self._last_used.clear()
        logger.info("CalendarAssistantServicePool stopped")
    
    async def get_service(self, user_email: str) -> CalendarAssistantService:
        """Get or create a service instance for a user"""
        if user_email not in self._services:
            if len(self._services) >= self.max_instances:
                # Remove oldest unused service
                oldest_user = min(self._last_used.items(), key=lambda x: x[1])[0]
                await self._remove_service(oldest_user)
            
            # Create new service
            service = CalendarAssistantService(user_email)
            await service.initialize()
            self._services[user_email] = service
            logger.info(f"Created new service instance for {user_email}")
        
        self._last_used[user_email] = datetime.now()
        return self._services[user_email]
    
    async def _remove_service(self, user_email: str):
        """Remove and cleanup a service instance"""
        if user_email in self._services:
            await self._services[user_email].cleanup()
            del self._services[user_email]
            del self._last_used[user_email]
            logger.info(f"Removed service instance for {user_email}")
    
    async def _cleanup_loop(self):
        """Periodic cleanup of unused service instances"""
        while self._is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                current_time = datetime.now()
                
                # Find services to cleanup (unused for more than session_timeout)
                to_remove = []
                for user_email, last_used in self._last_used.items():
                    if (current_time - last_used).seconds > 1800:  # 30 minutes timeout
                        to_remove.append(user_email)
                
                # Remove old services
                for user_email in to_remove:
                    await self._remove_service(user_email)
                
                if to_remove:
                    logger.info(f"Cleaned up {len(to_remove)} unused service instances")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        return {
            "active_services": len(self._services),
            "max_instances": self.max_instances,
            "cleanup_interval": self.cleanup_interval,
            "is_running": self._is_running,
            "users": list(self._services.keys())
        }