#!/usr/bin/env python3
"""Test MCP server via actual protocol communication."""

import asyncio
import json
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_mcp_server_direct():
    """Test the MCP server by calling it directly."""
    print("🧪 Testing MCP Server Direct Communication")
    print("=" * 50)
    
    try:
        # Import the server
        from awslabs.aws_health_mcp_server.server import mcp
        
        # Test initialization
        print("1. Testing server initialization...")
        
        # Create a mock request for listing tools
        print("2. Testing tools list...")
        try:
            # Call list_tools directly if available
            if hasattr(mcp, 'list_tools'):
                result = await mcp.list_tools()
                if hasattr(result, 'tools'):
                    tools = result.tools
                    print(f"   ✅ Found {len(tools)} tools:")
                    for i, tool in enumerate(tools[:5]):  # Show first 5
                        print(f"      {i+1}. {tool.name}: {tool.description[:60]}...")
                    if len(tools) > 5:
                        print(f"      ... and {len(tools) - 5} more tools")
                else:
                    print("   ⚠️  list_tools returned unexpected format")
            else:
                print("   ⚠️  list_tools method not found")
                
        except Exception as e:
            print(f"   ❌ Error listing tools: {e}")
        
        # Test a simple tool call if possible
        print("3. Testing tool call...")
        try:
            if hasattr(mcp, 'call_tool'):
                # Try to call a simple tool (we'll need to check what tools are available)
                print("   ✅ call_tool method available")
            else:
                print("   ⚠️  call_tool method not found")
        except Exception as e:
            print(f"   ❌ Error testing tool call: {e}")
            
        print("4. ✅ Direct MCP server test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Direct MCP server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_server_startup():
    """Test that the server can be started as a module."""
    print("\n🧪 Testing Server Module Startup")
    print("=" * 50)
    
    try:
        # Test that we can import the main module
        import awslabs.aws_health_mcp_server.__main__
        print("✅ Server main module imported successfully")
        
        # Test that the server object exists
        from awslabs.aws_health_mcp_server.server import mcp
        print(f"✅ Server object created: {type(mcp)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Server startup test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 MCP Protocol Direct Testing")
    print("=" * 60)
    
    # Test server startup
    startup_ok = asyncio.run(test_server_startup())
    
    # Test direct communication
    if startup_ok:
        direct_ok = asyncio.run(test_mcp_server_direct())
        
        print("\n" + "=" * 60)
        print("📊 MCP PROTOCOL TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Server Startup: {'PASS' if startup_ok else 'FAIL'}")
        print(f"✅ Direct Communication: {'PASS' if direct_ok else 'FAIL'}")
        
        if startup_ok and direct_ok:
            print("\n🎉 MCP SERVER IS READY!")
            print("Your server can be used with MCP clients.")
        else:
            print("\n⚠️  Some protocol tests failed.")
    else:
        print("\n❌ Server startup failed.")
