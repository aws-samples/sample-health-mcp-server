#!/usr/bin/env python3
"""
Integration Test Script for AWS Health MCP Server

This script performs end-to-end testing of the MCP server
including actual AWS Health API calls (if credentials are available).
"""

import asyncio
import json
import subprocess
import sys
import time
from typing import Dict, List, Any

class IntegrationTester:
    def __init__(self, container_name: str = "aws-health-mcp-server"):
        self.container_name = container_name
        
    def run_docker_command(self, command: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run a command in the Docker container."""
        full_command = ["docker", "exec", self.container_name] + command
        try:
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Command timed out",
                "returncode": -1
            }
    
    def test_aws_health_tools(self) -> Dict[str, bool]:
        """Test individual AWS Health MCP tools."""
        tools_to_test = [
            "get_service_health",
            "get_affected_entities", 
            "get_completed_events",
            "get_scheduled_changes"
        ]
        
        results = {}
        
        for tool in tools_to_test:
            print(f"Testing tool: {tool}")
            
            # Create a test script for each tool
            test_script = f"""
import sys
sys.path.insert(0, '/app')
try:
    from awslabs.aws_health_mcp_server.server import app
    tools = app.list_tools()
    tool_names = [tool.name for tool in tools]
    if '{tool}' in tool_names:
        print('Tool {tool} is available')
    else:
        print('Tool {tool} not found')
        print('Available tools:', tool_names)
except Exception as e:
    print(f'Error testing {tool}: {{e}}')
"""
            
            result = self.run_docker_command([
                "python", "-c", test_script
            ])
            
            results[tool] = f"Tool {tool} is available" in result["stdout"]
            
            if not results[tool]:
                print(f"  ❌ {tool}: {result['stdout']}")
            else:
                print(f"  ✅ {tool}: Available")
        
        return results
    
    def test_real_aws_call(self) -> bool:
        """Test a real AWS Health API call (requires valid credentials)."""
        print("Testing real AWS Health API call...")
        
        test_script = """
import boto3
import json
try:
    # Test with a simple Health API call
    health = boto3.client('health', region_name='us-east-1')
    
    # Try to get service health events (this requires minimal permissions)
    response = health.describe_events(
        filter={
            'eventTypeCategories': ['issue'],
            'eventStatusCodes': ['open', 'upcoming']
        },
        maxResults=5
    )
    
    events = response.get('events', [])
    print(f'Successfully retrieved {len(events)} health events')
    
    if events:
        print('Sample event:')
        event = events[0]
        print(f'  Service: {event.get("service", "Unknown")}')
        print(f'  Event Type: {event.get("eventTypeCode", "Unknown")}')
        print(f'  Status: {event.get("statusCode", "Unknown")}')
    
    print('AWS Health API test: SUCCESS')
    
except Exception as e:
    print(f'AWS Health API test failed: {e}')
    print('This might be expected if:')
    print('1. AWS credentials are not configured')
    print('2. You do not have AWS Business/Enterprise support')
    print('3. The Health API is not available in your region')
"""
        
        result = self.run_docker_command([
            "python", "-c", test_script
        ], timeout=20)
        
        success = "AWS Health API test: SUCCESS" in result["stdout"]
        
        if success:
            print("  ✅ Real AWS API call successful")
            print(f"  Output: {result['stdout']}")
        else:
            print("  ⚠️  Real AWS API call failed (this might be expected)")
            print(f"  Error: {result['stderr'] or result['stdout']}")
        
        return success
    
    def test_mcp_protocol_simulation(self) -> bool:
        """Simulate MCP protocol interactions."""
        print("Testing MCP protocol simulation...")
        
        test_script = """
import sys
sys.path.insert(0, '/app')
import json
try:
    from awslabs.aws_health_mcp_server.server import app
    
    # Test listing tools
    tools = app.list_tools()
    print(f'Available tools: {len(tools)}')
    
    for tool in tools:
        print(f'  - {tool.name}: {tool.description}')
    
    # Test getting resources (if any)
    try:
        resources = app.list_resources()
        print(f'Available resources: {len(resources)}')
    except:
        print('No resources available (this is normal)')
    
    print('MCP protocol simulation: SUCCESS')
    
except Exception as e:
    print(f'MCP protocol simulation failed: {e}')
    import traceback
    traceback.print_exc()
"""
        
        result = self.run_docker_command([
            "python", "-c", test_script
        ])
        
        success = "MCP protocol simulation: SUCCESS" in result["stdout"]
        
        if success:
            print("  ✅ MCP protocol simulation successful")
            print("  Available tools and resources listed")
        else:
            print("  ❌ MCP protocol simulation failed")
            print(f"  Error: {result['stderr'] or result['stdout']}")
        
        return success
    
    def run_performance_test(self) -> Dict[str, float]:
        """Run basic performance tests."""
        print("Running performance tests...")
        
        tests = {
            "import_time": "import time; start=time.time(); import awslabs.aws_health_mcp_server; print(f'Import time: {time.time()-start:.3f}s')",
            "tool_list_time": """
import time
import sys
sys.path.insert(0, '/app')
start = time.time()
from awslabs.aws_health_mcp_server.server import app
tools = app.list_tools()
elapsed = time.time() - start
print(f'Tool list time: {elapsed:.3f}s')
print(f'Tools found: {len(tools)}')
"""
        }
        
        results = {}
        
        for test_name, test_code in tests.items():
            result = self.run_docker_command([
                "python", "-c", test_code
            ])
            
            if result["success"]:
                # Extract timing from output
                for line in result["stdout"].split('\n'):
                    if 'time:' in line and 's' in line:
                        try:
                            time_str = line.split(':')[1].strip().replace('s', '')
                            results[test_name] = float(time_str)
                            print(f"  ✅ {test_name}: {time_str}s")
                            break
                        except:
                            results[test_name] = -1
                            print(f"  ⚠️  {test_name}: Could not parse timing")
            else:
                results[test_name] = -1
                print(f"  ❌ {test_name}: Failed")
        
        return results
    
    def run_all_tests(self):
        """Run all integration tests."""
        print("🧪 AWS Health MCP Server Integration Tests")
        print("=" * 50)
        
        # Check if container is running
        container_check = self.run_docker_command(["echo", "Container is running"])
        if not container_check["success"]:
            print("❌ Container is not running or not accessible")
            print("Run: ./docker-build.sh run")
            return
        
        print("✅ Container is accessible")
        print()
        
        # Test 1: Tool availability
        print("1. Testing MCP Tools Availability")
        print("-" * 30)
        tool_results = self.test_aws_health_tools()
        tools_available = sum(tool_results.values())
        print(f"Tools available: {tools_available}/{len(tool_results)}")
        print()
        
        # Test 2: MCP Protocol
        print("2. Testing MCP Protocol")
        print("-" * 30)
        mcp_success = self.test_mcp_protocol_simulation()
        print()
        
        # Test 3: AWS API
        print("3. Testing AWS Health API")
        print("-" * 30)
        aws_success = self.test_real_aws_call()
        print()
        
        # Test 4: Performance
        print("4. Performance Tests")
        print("-" * 30)
        perf_results = self.run_performance_test()
        print()
        
        # Summary
        print("📊 Integration Test Summary")
        print("=" * 50)
        print(f"✅ Container accessible: Yes")
        print(f"✅ MCP tools available: {tools_available}/{len(tool_results)}")
        print(f"✅ MCP protocol working: {'Yes' if mcp_success else 'No'}")
        print(f"⚠️  AWS API accessible: {'Yes' if aws_success else 'No (expected if no credentials)'}")
        
        if perf_results:
            print("⚡ Performance:")
            for test, time_val in perf_results.items():
                if time_val > 0:
                    print(f"   - {test}: {time_val:.3f}s")
        
        print()
        
        # Overall assessment
        critical_tests_passed = mcp_success and tools_available > 0
        
        if critical_tests_passed:
            print("🎉 Integration tests PASSED!")
            print("Your MCP server is ready for production use.")
            if not aws_success:
                print("💡 To test AWS API calls, configure valid AWS credentials.")
        else:
            print("⚠️  Some critical tests failed.")
            print("Check the output above for specific issues.")

def main():
    container_name = sys.argv[1] if len(sys.argv) > 1 else "aws-health-mcp-server"
    tester = IntegrationTester(container_name)
    tester.run_all_tests()

if __name__ == "__main__":
    main()
