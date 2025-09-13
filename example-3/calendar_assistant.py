#!/usr/bin/env python3
"""
Calendar Assistant - A conversational AI assistant for Google Calendar management
using MCP (Model Context Protocol) and OpenAI.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from openai import OpenAI
from fastmcp import Client
from dotenv import load_dotenv

load_dotenv()

class CalendarAssistant:
    def __init__(self, mcp_url: str = "http://localhost:3000/mcp", user_email: str = "vivek176iitv@gmail.com"):
        self.mcp_url = mcp_url
        self.user_email = user_email
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_iterations = 10  # Prevent infinite loops
        
        # System prompt for the calendar assistant
        self.system_prompt = f"""You are a helpful Calendar Assistant for {user_email}. You can help with:

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

**Important Guidelines:**
- Always use the user's primary calendar ({user_email}) unless specifically asked about other calendars
- When creating/updating events, use proper ISO 8601 datetime format (YYYY-MM-DDTHH:MM:SS)
- For all-day events, use date format (YYYY-MM-DD)
- The timings provided by the user will all be in IST.
- Be proactive in suggesting meeting times and checking for conflicts
- When updating events, you may need to first search/find the event, then update it
- Always confirm important changes before executing them
- If you need to make multiple tool calls, execute them all before responding to the user

**Available Tools:**
- list-calendars: List all available calendars
- list-events: List events from a calendar in a time range
- search-events: Search for events by text query
- get-event: Get details of a specific event
- create-event: Create a new calendar event
- update-event: Update an existing event
- delete-event: Delete an event
- get-freebusy: Check free/busy status
- list-colors: List available event colors
- get-current-time: Get current time and timezone info

Always be helpful, accurate, and proactive in managing the user's calendar."""

    def _tool_result_to_text(self, result: Any) -> str:
        """Convert fastmcp CallToolResult to a plain string for OpenAI tool message."""
        try:
            sc = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
            if sc is not None:
                return json.dumps(sc)
            content = getattr(result, "content", None)
            if isinstance(content, (list, tuple)):
                texts: List[str] = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    else:  # fastmcp TextContent dataclass
                        t = getattr(block, "text", None)
                        if isinstance(t, str):
                            texts.append(t)
                if texts:
                    return "\n".join(texts)
            return str(result)
        except Exception:
            return str(result)

    def _build_openai_tools_schema(self, tools: List[Any]) -> List[Dict[str, Any]]:
        """Convert MCP tools to OpenAI function calling format."""
        openai_tools = []
        for tool in tools:
            try:
                input_schema = getattr(tool, "inputSchema", {}) or {}
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": getattr(tool, "description", ""),
                        "parameters": input_schema
                    }
                }
                openai_tools.append(openai_tool)
            except Exception as e:
                print(f"Warning: Could not convert tool {tool.name}: {e}")
        return openai_tools

    async def _execute_tool_calls(self, mcp_client: Client, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """Execute multiple tool calls in parallel and return results."""
        tasks = []
        for tc in tool_calls:
            if getattr(tc, "type", None) == "function":
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                
                # Create task for parallel execution
                task = self._call_tool_safely(mcp_client, name, args, tc.id)
                tasks.append(task)
        
        # Execute all tools in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Format results for OpenAI
        tool_messages = []
        for i, result in enumerate(results):
            tc = tool_calls[i]
            if isinstance(result, Exception):
                content = f"Error executing {tc.function.name}: {str(result)}"
            else:
                content = self._tool_result_to_text(result)
            
            tool_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.function.name,
                "content": content
            })
        
        return tool_messages

    async def _call_tool_safely(self, mcp_client: Client, tool_name: str, args: Dict[str, Any], tool_call_id: str) -> Any:
        """Safely call a tool and return the result or exception."""
        try:
            print(f"🔧 Executing: {tool_name}({args})")
            result = await mcp_client.call_tool(tool_name, args)
            print(f"✅ Result: {self._tool_result_to_text(result)[:200]}...")
            return result
        except Exception as e:
            print(f"❌ Error in {tool_name}: {e}")
            return e

    async def chat(self, user_input: str) -> None:
        """Main chat method that handles conversation with the user."""
        async with Client(self.mcp_url) as mcp_client:
            # Get available tools
            tools = await mcp_client.list_tools()
            openai_tools = self._build_openai_tools_schema(tools)
            
            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            
            # Build messages for OpenAI (system + conversation history)
            messages = [{"role": "system", "content": self.system_prompt}] + self.conversation_history
            
            iteration = 0
            while iteration < self.max_iterations:
                iteration += 1
                
                try:
                    # Call OpenAI
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto",
                        temperature=0.1
                    )
                    
                    message = response.choices[0].message
                    
                    # Add assistant's message to conversation history
                    assistant_message = {
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": getattr(message, "tool_calls", None)
                    }
                    self.conversation_history.append(assistant_message)
                    messages.append(assistant_message)
                    
                    # If there are tool calls, execute them
                    if getattr(message, "tool_calls", None):
                        print(f"\n🤖 Assistant is executing {len(message.tool_calls)} tool(s)...")
                        
                        # Execute all tool calls in parallel
                        tool_messages = await self._execute_tool_calls(mcp_client, list(message.tool_calls))
                        
                        # Add tool results to conversation history and messages
                        self.conversation_history.extend(tool_messages)
                        messages.extend(tool_messages)
                        
                        # Continue the loop to get the assistant's response to tool results
                        continue
                    
                    # If no tool calls, this is the final response
                    if message.content:
                        print(f"\n🤖 Assistant: {message.content}")
                        return
                    else:
                        print("\n🤖 Assistant: (No response generated)")
                        return
                        
                except Exception as e:
                    print(f"\n❌ Error in chat iteration {iteration}: {e}")
                    return
            
            print(f"\n⚠️ Reached maximum iterations ({self.max_iterations}). Stopping.")

    def reset_conversation(self):
        """Reset the conversation history."""
        self.conversation_history = []
        print("🔄 Conversation history reset.")

    def show_conversation_history(self):
        """Display the current conversation history."""
        if not self.conversation_history:
            print("No conversation history.")
            return
        
        print("\n📜 Conversation History:")
        for i, msg in enumerate(self.conversation_history):
            role = msg["role"]
            if role == "user":
                print(f"\n👤 You: {msg['content']}")
            elif role == "assistant":
                content = msg.get("content", "")
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    print(f"\n🤖 Assistant: [Executed {len(tool_calls)} tool(s)]")
                    for tc in tool_calls:
                        print(f"  🔧 {tc['function']['name']}({tc['function']['arguments']})")
                if content:
                    print(f"🤖 Assistant: {content}")
            elif role == "tool":
                print(f"  🔧 Tool Result: {msg['content'][:100]}...")

async def main():
    """Main function to run the calendar assistant."""
    print("🗓️ Welcome to Calendar Assistant!")
    print("Type 'help' for commands, 'quit' to exit, 'reset' to clear history")
    print("-" * 50)
    
    assistant = CalendarAssistant()
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            elif user_input.lower() == 'help':
                print("""
Available commands:
- Ask about your calendar: "What's on my schedule today?"
- Create events: "Schedule a meeting with John tomorrow at 2 PM"
- Update events: "Move my 3 PM meeting to 4 PM"
- Search events: "Find all meetings with Sarah"
- Check availability: "Am I free on Friday afternoon?"
- quit/exit/q: Exit the assistant
- reset: Clear conversation history
- history: Show conversation history
                """)
                continue
            elif user_input.lower() == 'reset':
                assistant.reset_conversation()
                continue
            elif user_input.lower() == 'history':
                assistant.show_conversation_history()
                continue
            elif not user_input:
                continue
            
            # Process the user input
            await assistant.chat(user_input)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
