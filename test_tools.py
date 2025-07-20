#!/usr/bin/env python3
"""Test all tools in the AWS Health MCP Server."""

import sys
import asyncio
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_all_tools():
    """Test all available tools in the MCP server."""
    print("🧪 TESTING ALL AWS HEALTH MCP SERVER TOOLS")
    print("=" * 60)
    
    try:
        from awslabs.aws_health_mcp_server.server import mcp
        
        # Get all available tools
        tools = await mcp.list_tools()
        print(f"Found {len(tools)} tools to test\n")
        
        # Test each tool
        for i, tool in enumerate(tools, 1):
            print(f"🛠️  Testing Tool {i}/{len(tools)}: {tool.name}")
            print("-" * 50)
            print(f"Description: {tool.description.split('.')[0]}.")
            
            try:
                # Prepare arguments based on tool requirements
                args = {}
                
                if tool.name == "get_service_events":
                    args = {"service": "EC2"}
                elif tool.name == "get_completed_events":
                    args = {"service": "EC2"}
                elif tool.name == "get_org_health_events":
                    args = {"status": "active"}
                
                # Call the tool
                print(f"Calling with args: {args}")
                result = await mcp.call_tool(tool.name, args)
                
                # Display result
                if hasattr(result, 'content'):
                    content = result.content
                    if isinstance(content, list) and content:
                        # Handle list of content items
                        for item in content:
                            if hasattr(item, 'text'):
                                text = item.text
                                # Truncate long responses for readability
                                if len(text) > 500:
                                    print(f"✅ Result (truncated): {text[:500]}...")
                                else:
                                    print(f"✅ Result: {text}")
                            else:
                                print(f"✅ Result: {item}")
                    else:
                        print(f"✅ Result: {content}")
                else:
                    print(f"✅ Result: {result}")
                    
            except Exception as e:
                print(f"❌ Error calling {tool.name}: {e}")
                # Print more details for debugging
                import traceback
                print(f"   Details: {traceback.format_exc().split('Traceback')[-1].strip()}")
            
            print("\n")
        
        print("🎉 Tool testing completed!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test tools: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_all_tools())
    
    if success:
        print("\n✅ All tools tested successfully!")
    else:
        print("\n❌ Some tools failed testing.")
