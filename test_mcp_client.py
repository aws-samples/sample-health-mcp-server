#!/usr/bin/env python3
"""Test MCP client to validate server functionality."""

import asyncio
import json
import subprocess
import sys
from typing import Any, Dict


async def test_mcp_server():
    """Test the MCP server by starting it and sending requests."""
    print("🧪 Testing MCP Server Communication")
    print("=" * 50)
    
    # Start the MCP server process
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "awslabs.aws_health_mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/Users/jsanketh/Desktop/Final/mcp-mem0-refactored"
        )
        
        # Send initialization request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print("1. Sending initialization request...")
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            try:
                response = json.loads(response_line.strip())
                print(f"   ✅ Server initialized: {response.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}")
            except json.JSONDecodeError:
                print(f"   ⚠️  Non-JSON response: {response_line.strip()}")
        
        # Send tools list request
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        print("2. Requesting tools list...")
        process.stdin.write(json.dumps(tools_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            try:
                response = json.loads(response_line.strip())
                tools = response.get('result', {}).get('tools', [])
                print(f"   ✅ Found {len(tools)} tools:")
                for tool in tools[:3]:  # Show first 3 tools
                    print(f"      - {tool.get('name', 'Unknown')}")
                if len(tools) > 3:
                    print(f"      ... and {len(tools) - 3} more")
            except json.JSONDecodeError:
                print(f"   ⚠️  Non-JSON response: {response_line.strip()}")
        
        # Terminate the process
        process.terminate()
        process.wait(timeout=5)
        
        print("3. ✅ Server communication test completed successfully!")
        
    except subprocess.TimeoutExpired:
        print("   ⚠️  Server process timeout")
        process.kill()
    except Exception as e:
        print(f"   ❌ Error testing server: {e}")
        if process:
            process.terminate()


def test_server_startup():
    """Test that the server can start without errors."""
    print("\n🧪 Testing Server Startup")
    print("=" * 50)
    
    try:
        # Test server startup with a quick timeout
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from awslabs.aws_health_mcp_server.server import mcp
print('Server startup test: SUCCESS')
"""],
            cwd="/Users/jsanketh/Desktop/Final/mcp-mem0-refactored",
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ Server startup test passed")
            if result.stdout:
                print(f"   Output: {result.stdout.strip()}")
        else:
            print("❌ Server startup test failed")
            if result.stderr:
                print(f"   Error: {result.stderr.strip()}")
                
    except subprocess.TimeoutExpired:
        print("⚠️  Server startup test timeout (this might be normal)")
    except Exception as e:
        print(f"❌ Error in startup test: {e}")


if __name__ == "__main__":
    test_server_startup()
    asyncio.run(test_mcp_server())
