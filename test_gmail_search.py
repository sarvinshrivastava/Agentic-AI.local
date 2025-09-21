"""
Test Gmail MCP integration directly
"""
import asyncio
from gmail_mcp_client import GmailMCPClient

async def test_gmail_search():
    gmail_client = GmailMCPClient()
    
    try:
        await gmail_client.connect()
        print("✅ Connected to Gmail MCP")
        
        # Test search for unread emails in last 7 days
        query = "is:unread newer_than:7d"
        result = await gmail_client.search_gmail(query, max_results=5)
        print(f"📧 Search result: {result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await gmail_client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_gmail_search())