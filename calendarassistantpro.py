#!/usr/bin/env python3
"""
Calendar Assistant Pro - Enhanced conversational AI assistant for Google Calendar 
and Notion workspace management using MCP (Model Context Protocol) and OpenAI.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

from mcp_orchestrator_pro import MCPOrchestratorPro

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

class CalendarAssistantPro:
    def __init__(self, user_email: str = "sarvin5124@gmail.com", gmail_url: str = "http://localhost:3001"):
        self.user_email = user_email
        self.gmail_url = gmail_url
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_iterations = 10  # Prevent infinite loops
        
        # System prompt for the enhanced calendar assistant
        self.system_prompt = f"""You are Calendar Assistant Pro, an advanced AI assistant for {user_email} that can manage Google Calendar, Notion workspace, and Gmail email operations.

## 🗓️ **Calendar Management Capabilities:**
1. **Reading Calendar Data:**
   - List upcoming events for any time period
   - Search for specific events by keywords
   - Get details of specific events
   - Check free/busy status
   - List available calendars

2. **Managing Events:**
   - Create new events with all details (title, time, location, attendees, etc.)
   - Update existing events (change time, location, attendees, etc.)
   - Delete events
   - Handle recurring events
   - Before creating/updating events, always first get the current time to make sure you are booking for right dates.

3. **Calendar Operations:**
   - Find time slots for meetings
   - Check for conflicts
   - Suggest meeting times
   - Manage event colors and reminders

## 📝 **Notion Workspace Management:**
1. **Document Search:**
   - Search for documents by keywords or topics
   - Find documents related to specific meetings or projects
   - List recent documents

2. **Document Access:**
   - Fetch full content of specific documents
   - Read meeting notes, project plans, and other documents
   - Access document metadata (title, URL, timestamp)

3. **Integration:**
   - Link calendar events to related Notion documents
   - Provide context from documents when discussing meetings
   - Combine information from both calendar and Notion for comprehensive responses

## 📧 **Gmail Email Management:**
1. **Reading Emails:**
   - Search emails by keywords, sender, subject, date range
   - Read email content including threads and attachments
   - List emails with filtering options
   - Get email metadata (sender, recipients, date, subject)

2. **Sending Emails:**
   - Send new emails with text or HTML content
   - Reply to existing emails
   - Forward emails to other recipients
   - Add attachments to outgoing emails

3. **Email Organization:**
   - List and manage Gmail labels
   - Apply labels to emails for organization
   - Create and manage email filters
   - Archive, delete, or mark emails as read/unread

4. **Email-Calendar Integration:**
   - Send meeting invites via email after creating calendar events
   - Email event details to participants
   - Find emails related to calendar events
   - Extract meeting information from emails to create calendar events

## 🎯 **Key Features:**
- **Contextual Responses**: Use information from calendar, Notion, and Gmail to provide comprehensive answers
- **Multi-step Operations**: Handle complex requests that involve calendar, document, and email operations
- **Smart Integration**: Connect calendar events with related emails and documents
- **Error Handling**: If any tool fails, explain the error to the user and suggest alternatives
- **Smart Tool Selection**: Choose the appropriate tools based on user requests

## 🔧 **Important Guidelines:**
- Always use the user's primary calendar ({user_email}) unless specifically asked about other calendars
- The timings provided by the user will all be in IST. You should also always use same timezone for all the operations.
- When creating/updating events, use proper ISO 8601 datetime format (YYYY-MM-DDTHH:MM:SS)
- For Notion searches, use relevant keywords and try different query types if needed
- For Gmail operations, use appropriate search queries and handle email threads properly
- When user mentions documents, topics, or queries, use the appropriate Notion tools to search and fetch content
- When user mentions emails, use Gmail tools to search, read, or send emails
- Provide helpful context by combining information from calendar, Notion, and Gmail
- If a tool call fails, explain the error and suggest what the user can do instead
- Be conversational and helpful, not robotic

## 🚀 **Example Interactions:**
- "I have a meeting on financial reports tomorrow" → Use notion__search + calendar__list-events + gmail__search for related emails
- "Create a meeting about project planning and email the team" → Use notion__search + calendar__create-event + gmail__send
- "What emails did I receive about Q4 planning?" → Use gmail__search + notion__search for related documents
- "Schedule a follow-up meeting for the marketing campaign and send invites" → Use notion__search + calendar__create-event + gmail__send
- "Find emails from my manager this week" → Use gmail__search with sender and date filters
- "Send a summary of today's meeting to the team" → Use notion__search for meeting notes + gmail__send

You have access to calendar, Notion, and Gmail tools. Use them intelligently based on what the user is asking for to provide comprehensive assistance!"""

    async def _call_tool_safely(self, orchestrator: MCPOrchestratorPro, tool_name: str, args: Dict[str, Any], tool_call_id: str) -> Dict[str, Any]:
        """Safely call a tool and return a standardized result."""
        try:
            server, result = await orchestrator.call_tool_by_fullname(tool_name, args)
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": tool_name,
                "content": str(result)
            }
        except Exception as e:
            return {
                "tool_call_id": tool_call_id,
                "role": "tool", 
                "name": tool_name,
                "content": f"Error: {str(e)}"
            }

    async def _execute_tool_calls(self, orchestrator: MCPOrchestratorPro, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """Execute multiple tool calls in parallel and return results."""
        tasks = []
        for tc in tool_calls:
            tool_name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            task = self._call_tool_safely(orchestrator, tool_name, args, tc.id)
            tasks.append(task)
        
        return await asyncio.gather(*tasks)


    async def run_chat(self):
        """Main chat loop for Calendar Assistant Pro."""
        print("🗓️📝📧 Calendar Assistant Pro - Enhanced with Notion & Gmail Integration")
        print("=" * 75)
        print(f"Managing calendar, Notion workspace, and Gmail for: {self.user_email}")
        print("Type 'quit' to exit, 'help' for commands")
        print("=" * 75)

        async with MCPOrchestratorPro(gmail_url=self.gmail_url) as orchestrator:
            # Health check
            health = await orchestrator.health_check()
            print(f"🔍 Service Status: Calendar: {'✅' if health['calendar'] else '❌'}, Notion: {'✅' if health['notion'] else '❌'}, Gmail: {'✅' if health['gmail'] else '❌'}")
            
            if not health['calendar']:
                print("⚠️  Warning: Google Calendar MCP server is not accessible. Calendar features will be limited.")
            if not health['notion']:
                print("⚠️  Warning: Notion MCP server is not accessible. Document features will be limited.")
            if not health['gmail']:
                print("⚠️  Warning: Gmail MCP server is not accessible. Email features will be limited.")
            
            print()

            while True:
                try:
                    user_input = input("\n👤 You: ").strip()
                    
                    if user_input.lower() in ['quit', 'exit', 'bye']:
                        print("👋 Goodbye! Calendar Assistant Pro signing off.")
                        break
                    
                    if user_input.lower() == 'help':
                        self._show_help()
                        continue
                    
                    if not user_input:
                        continue

                    # Add user message to conversation
                    self.conversation_history.append({
                        "role": "user",
                        "content": user_input
                    })

                    # Get available tools from both calendar and notion
                    tool_specs = await orchestrator.get_all_tool_specs()
                    
                    # Prepare messages for OpenAI
                    messages = [{"role": "system", "content": self.system_prompt}]
                    
                    # Add conversation history
                    messages.extend(self.conversation_history[-10:])  # Keep last 10 messages for context

                    # Call OpenAI with function calling
                    response = self.openai_client.chat.completions.create(
                        model=MODEL,
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

                    message = response.choices[0].message
                    
                    # Add assistant message to conversation
                    assistant_message = {
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": getattr(message, "tool_calls", None)
                    }
                    self.conversation_history.append(assistant_message)

                    # Handle tool calls
                    if message.tool_calls:
                        print(f"🔧 Executing {len(message.tool_calls)} tool call(s)...")
                        
                        # Execute all tool calls in parallel
                        tool_messages = await self._execute_tool_calls(orchestrator, list(message.tool_calls))
                        
                        # Add tool results to conversation
                        self.conversation_history.extend(tool_messages)
                        
                        # Continue conversation until we get a final text response
                        iteration = 0
                        while iteration < self.max_iterations:
                            iteration += 1
                            
                            # Prepare messages for follow-up - build clean message flow
                            follow_up_messages = [{"role": "system", "content": self.system_prompt}]
                            
                            # Add recent conversation history (last 10 messages to avoid token limits)
                            recent_history = self.conversation_history[-10:]
                            follow_up_messages.extend(recent_history)
                            
                            follow_up_response = self.openai_client.chat.completions.create(
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
                                print(f"🔧 Executing {len(follow_up_message.tool_calls)} additional tool call(s)...")
                                additional_tool_messages = await self._execute_tool_calls(orchestrator, list(follow_up_message.tool_calls))
                                
                                # Add assistant message with tool calls
                                self.conversation_history.append({
                                    "role": "assistant",
                                    "content": follow_up_message.content or "",
                                    "tool_calls": getattr(follow_up_message, "tool_calls", None)
                                })
                                
                                # Add tool results
                                self.conversation_history.extend(additional_tool_messages)
                            else:
                                # Final response received
                                self.conversation_history.append({
                                    "role": "assistant",
                                    "content": follow_up_message.content or ""
                                })
                                
                                if follow_up_message.content:
                                    print(f"\n🤖 Calendar Assistant Pro: {follow_up_message.content}")
                                break
                        else:
                            print("\n🤖 Calendar Assistant Pro: I've completed the requested operations. Is there anything else I can help you with?")
                    else:
                        # Simple text response
                        print(f"\n🤖 Calendar Assistant Pro: {message.content}")

                except KeyboardInterrupt:
                    print("\n\n👋 Goodbye! Calendar Assistant Pro signing off.")
                    break
                except Exception as e:
                    print(f"\n❌ Error: {str(e)}")
                    print("Please try again or type 'help' for assistance.")

    def _show_help(self):
        """Display help information."""
        print("\n📋 **Calendar Assistant Pro - Available Commands:**")
        print("=" * 60)
        print("🗓️ **Calendar Operations:**")
        print("  • 'Show my events this week'")
        print("  • 'Create a meeting tomorrow at 2 PM'")
        print("  • 'What's on my calendar for Friday?'")
        print("  • 'Schedule a team meeting next Monday'")
        print("  • 'Update my 3 PM meeting to 4 PM'")
        print()
        print("📝 **Notion Document Operations:**")
        print("  • 'Search for documents about financial reports'")
        print("  • 'Show me my project planning documents'")
        print("  • 'Find notes from last week's meeting'")
        print("  • 'What documents do I have about marketing?'")
        print()
        print("� **Gmail Email Operations:**")
        print("  • 'Check my emails from today'")
        print("  • 'Send an email to john@example.com'")
        print("  • 'Find emails about project updates'")
        print("  • 'Show me unread emails'")
        print("  • 'List my Gmail labels'")
        print()
        print("🔗 **Integrated Operations:**")
        print("  • 'I have a meeting about Q4 planning - show me relevant docs and emails'")
        print("  • 'Create a meeting for the marketing campaign and send invites'")
        print("  • 'Schedule a follow-up meeting and email the details to the team'")
        print("  • 'Find emails about the project and create a meeting to discuss'")
        print()
        print("🛠️ **System Commands:**")
        print("  • 'help' - Show this help message")
        print("  • 'quit' - Exit the assistant")
        print("=" * 60)
        print("💡 **Note:** I can intelligently combine calendar, Notion, and Gmail operations based on your requests!")


async def main():
    """Main entry point."""
    assistant = CalendarAssistantPro()
    await assistant.run_chat()


if __name__ == "__main__":
    asyncio.run(main())
