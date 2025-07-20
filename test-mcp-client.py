#!/usr/bin/env python3
"""
MCP Client Test Script for AWS Health MCP Server

This script tests the MCP server functionality by connecting to it
and testing various tool calls.
"""

import asyncio
import json
import sys
from typing import Any, Dict, List
import subprocess
import time

# Colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_header(text: str):
    print(f"{Colors.BLUE}{'=' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}{text}{Colors.NC}")
    print(f"{Colors.BLUE}{'=' * 50}{Colors.NC}")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.NC}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.NC}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.NC}")

class MCPTester:
    def __init__(self, container_name: str = "aws-health-mcp-server"):
        self.container_name = container_name
        self.test_results = []

    def run_test(self, test_name: str, test_func):
        """Run a test and record the result."""
        print_header(f"Test: {test_name}")
        try:
            result = test_func()
            if result:
                print_success(f"{test_name} passed")
                self.test_results.append((test_name, True, None))
            else:
                print_warning(f"{test_name} failed")
                self.test_results.append((test_name, False, "Test returned False"))
        except Exception as e:
            print_error(f"{test_name} failed with error: {e}")
            self.test_results.append((test_name, False, str(e)))
        print()

    def test_container_running(self) -> bool:
        """Test if the container is running."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={self.container_name}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True
            )
            return self.container_name in result.stdout
        except subprocess.CalledProcessError:
            return False

    def test_mcp_server_import(self) -> bool:
        """Test if the MCP server module can be imported."""
        try:
            result = subprocess.run([
                "docker", "exec", self.container_name,
                "python", "-c", "import awslabs.aws_health_mcp_server; print('Import successful')"
            ], capture_output=True, text=True, check=True)
            return "Import successful" in result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Import error: {e.stderr}")
            return False

    def test_mcp_tools_list(self) -> bool:
        """Test if we can list MCP tools."""
        try:
            # This is a simplified test - in a real scenario, you'd use the MCP protocol
            result = subprocess.run([
                "docker", "exec", self.container_name,
                "python", "-c", """
import sys
sys.path.insert(0, '/app')
from awslabs.aws_health_mcp_server.server import app
print('Tools available:', len(app.list_tools()))
"""
            ], capture_output=True, text=True, timeout=10)
            
            return "Tools available:" in result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"Tools list error: {e}")
            return False

    def test_aws_credentials_available(self) -> bool:
        """Test if AWS credentials are configured."""
        try:
            result = subprocess.run([
                "docker", "exec", self.container_name,
                "python", "-c", """
import boto3
try:
    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials:
        print('Credentials available')
    else:
        print('No credentials')
except Exception as e:
    print(f'Error: {e}')
"""
            ], capture_output=True, text=True, check=True)
            
            return "Credentials available" in result.stdout
        except subprocess.CalledProcessError:
            return False

    def test_health_api_access(self) -> bool:
        """Test if we can access AWS Health API (requires valid credentials)."""
        try:
            result = subprocess.run([
                "docker", "exec", self.container_name,
                "python", "-c", """
import boto3
try:
    health = boto3.client('health', region_name='us-east-1')
    # This is a simple test that doesn't require special permissions
    response = health.describe_events(maxResults=1)
    print('Health API accessible')
except Exception as e:
    print(f'Health API error: {e}')
"""
            ], capture_output=True, text=True, timeout=15)
            
            if "Health API accessible" in result.stdout:
                return True
            elif "Health API error:" in result.stdout:
                print(f"Health API test result: {result.stdout.strip()}")
                # This might fail due to permissions, which is expected
                return False
            else:
                return False
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    def test_mcp_server_startup(self) -> bool:
        """Test if the MCP server can start without errors."""
        try:
            # Test server startup with a timeout
            result = subprocess.run([
                "docker", "exec", self.container_name,
                "timeout", "5", "python", "-m", "awslabs.aws_health_mcp_server"
            ], capture_output=True, text=True)
            
            # Timeout is expected, but we want to check for import/startup errors
            if result.returncode == 124:  # Timeout exit code
                print("Server started successfully (timed out as expected)")
                return True
            elif "Error:" in result.stderr or "Exception:" in result.stderr:
                print(f"Server startup error: {result.stderr}")
                return False
            else:
                return True
        except subprocess.CalledProcessError as e:
            print(f"Server startup failed: {e}")
            return False

    def run_all_tests(self):
        """Run all tests and print summary."""
        print_header("MCP Server Functionality Tests")
        
        tests = [
            ("Container Running", self.test_container_running),
            ("MCP Server Import", self.test_mcp_server_import),
            ("MCP Tools List", self.test_mcp_tools_list),
            ("AWS Credentials", self.test_aws_credentials_available),
            ("Health API Access", self.test_health_api_access),
            ("MCP Server Startup", self.test_mcp_server_startup),
        ]
        
        for test_name, test_func in tests:
            self.run_test(test_name, test_func)
        
        # Print summary
        passed = sum(1 for _, success, _ in self.test_results if success)
        total = len(self.test_results)
        
        print_header("Test Summary")
        print(f"{Colors.BLUE}Results: {passed}/{total} tests passed{Colors.NC}")
        
        if passed == total:
            print_success("All tests passed! 🎉")
            print("\nYour MCP server is ready for use!")
            print("Next steps:")
            print("1. Configure your MCP client to connect to this server")
            print("2. Test with real AWS Health API calls")
        else:
            print_warning(f"{total - passed} tests failed")
            print("\nFailed tests:")
            for test_name, success, error in self.test_results:
                if not success:
                    print(f"  - {test_name}: {error or 'Unknown error'}")
            
            print("\nCommon solutions:")
            print("1. Ensure container is running: ./docker-build.sh run")
            print("2. Configure AWS credentials in .env file")
            print("3. Check if you have AWS Health API access (requires Business/Enterprise support)")

def main():
    if len(sys.argv) > 1:
        container_name = sys.argv[1]
    else:
        container_name = "aws-health-mcp-server"
    
    tester = MCPTester(container_name)
    tester.run_all_tests()

if __name__ == "__main__":
    main()
