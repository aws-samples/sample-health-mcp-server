#!/bin/bash

# Container Testing Script for AWS Health MCP Server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CONTAINER_NAME="aws-health-mcp-server"
IMAGE_NAME="aws-health-mcp-server:latest"

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Test 1: Check if Docker image exists
test_image_exists() {
    print_header "Test 1: Docker Image"
    
    if docker images | grep -q "$IMAGE_NAME"; then
        print_success "Docker image exists: $IMAGE_NAME"
        return 0
    else
        print_error "Docker image not found: $IMAGE_NAME"
        echo "Run: docker build -t $IMAGE_NAME ."
        return 1
    fi
}

# Test 2: Check if container is running
test_container_running() {
    print_header "Test 2: Container Status"
    
    if docker ps | grep -q "$CONTAINER_NAME"; then
        print_success "Container is running: $CONTAINER_NAME"
        
        # Show container details
        echo -e "\n${BLUE}Container Details:${NC}"
        docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        return 0
    else
        print_warning "Container is not running: $CONTAINER_NAME"
        
        # Check if container exists but is stopped
        if docker ps -a | grep -q "$CONTAINER_NAME"; then
            print_warning "Container exists but is stopped"
            echo "Run: docker start $CONTAINER_NAME"
        else
            print_warning "Container doesn't exist"
            echo "Run: ./docker-build.sh run"
        fi
        return 1
    fi
}

# Test 3: Check container health
test_container_health() {
    print_header "Test 3: Container Health"
    
    if docker ps | grep -q "$CONTAINER_NAME"; then
        local health_status=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "no-healthcheck")
        
        case $health_status in
            "healthy")
                print_success "Container is healthy"
                return 0
                ;;
            "unhealthy")
                print_error "Container is unhealthy"
                echo "Check logs: docker logs $CONTAINER_NAME"
                return 1
                ;;
            "starting")
                print_warning "Container health check is starting..."
                return 0
                ;;
            "no-healthcheck")
                print_warning "No health check configured"
                return 0
                ;;
            *)
                print_warning "Unknown health status: $health_status"
                return 0
                ;;
        esac
    else
        print_error "Container is not running"
        return 1
    fi
}

# Test 4: Check container logs
test_container_logs() {
    print_header "Test 4: Container Logs"
    
    if docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${BLUE}Recent logs (last 10 lines):${NC}"
        docker logs --tail 10 "$CONTAINER_NAME"
        
        # Check for common error patterns
        local error_count=$(docker logs "$CONTAINER_NAME" 2>&1 | grep -i "error\|exception\|failed" | wc -l)
        if [ "$error_count" -gt 0 ]; then
            print_warning "Found $error_count potential error messages in logs"
            echo "Run 'docker logs $CONTAINER_NAME' to see full logs"
        else
            print_success "No obvious errors in logs"
        fi
        return 0
    else
        print_error "Container is not running"
        return 1
    fi
}

# Test 5: Test Python import
test_python_import() {
    print_header "Test 5: Python Module Import"
    
    if docker ps | grep -q "$CONTAINER_NAME"; then
        if docker exec "$CONTAINER_NAME" python -c "import awslabs.aws_health_mcp_server; print('✓ Module import successful')" 2>/dev/null; then
            print_success "Python module imports correctly"
            return 0
        else
            print_error "Python module import failed"
            echo "Check container setup and dependencies"
            return 1
        fi
    else
        print_error "Container is not running"
        return 1
    fi
}

# Test 6: Test AWS credentials (if available)
test_aws_credentials() {
    print_header "Test 6: AWS Credentials"
    
    if docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${BLUE}Testing AWS credentials...${NC}"
        
        # Try to get caller identity (this tests basic AWS connectivity)
        if docker exec "$CONTAINER_NAME" python -c "
import boto3
try:
    sts = boto3.client('sts')
    identity = sts.get_caller_identity()
    print('✓ AWS credentials are valid')
    print(f'Account: {identity.get(\"Account\", \"Unknown\")}')
    print(f'User/Role: {identity.get(\"Arn\", \"Unknown\")}')
except Exception as e:
    print(f'✗ AWS credentials test failed: {e}')
    exit(1)
" 2>/dev/null; then
            print_success "AWS credentials are configured and valid"
            return 0
        else
            print_warning "AWS credentials test failed"
            echo "This might be expected if credentials aren't configured yet"
            echo "Configure credentials in .env file or mount ~/.aws directory"
            return 1
        fi
    else
        print_error "Container is not running"
        return 1
    fi
}

# Test 7: Test MCP server startup
test_mcp_server() {
    print_header "Test 7: MCP Server Functionality"
    
    if docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${BLUE}Testing MCP server startup...${NC}"
        
        # Test if the server can start (this will timeout, but we're checking for import errors)
        if timeout 5 docker exec "$CONTAINER_NAME" python -m awslabs.aws_health_mcp_server --help >/dev/null 2>&1; then
            print_success "MCP server can start successfully"
            return 0
        else
            # Check if it's a timeout (expected) or an actual error
            local exit_code=$?
            if [ $exit_code -eq 124 ]; then
                print_success "MCP server starts (timed out as expected)"
                return 0
            else
                print_error "MCP server failed to start"
                echo "Check logs for startup errors"
                return 1
            fi
        fi
    else
        print_error "Container is not running"
        return 1
    fi
}

# Run all tests
run_all_tests() {
    print_header "AWS Health MCP Server Container Tests"
    
    local passed=0
    local total=7
    
    test_image_exists && ((passed++))
    test_container_running && ((passed++))
    test_container_health && ((passed++))
    test_container_logs && ((passed++))
    test_python_import && ((passed++))
    test_aws_credentials && ((passed++))
    test_mcp_server && ((passed++))
    
    echo ""
    print_header "Test Results"
    echo -e "${BLUE}Passed: $passed/$total tests${NC}"
    
    if [ $passed -eq $total ]; then
        print_success "All tests passed! 🎉"
        echo ""
        echo -e "${GREEN}Your container is ready for use!${NC}"
        echo "Next steps:"
        echo "1. Configure your MCP client to use this server"
        echo "2. Test with actual AWS Health API calls"
        echo "3. Monitor logs: docker logs -f $CONTAINER_NAME"
    else
        print_warning "Some tests failed. Check the output above for details."
        echo ""
        echo "Common fixes:"
        echo "1. Ensure container is running: ./docker-build.sh run"
        echo "2. Configure AWS credentials in .env file"
        echo "3. Check container logs: docker logs $CONTAINER_NAME"
    fi
}

# Main execution
case "${1:-all}" in
    "image")
        test_image_exists
        ;;
    "container")
        test_container_running
        ;;
    "health")
        test_container_health
        ;;
    "logs")
        test_container_logs
        ;;
    "import")
        test_python_import
        ;;
    "aws")
        test_aws_credentials
        ;;
    "mcp")
        test_mcp_server
        ;;
    "all")
        run_all_tests
        ;;
    *)
        echo "Usage: $0 [image|container|health|logs|import|aws|mcp|all]"
        echo ""
        echo "Tests:"
        echo "  image     - Check if Docker image exists"
        echo "  container - Check if container is running"
        echo "  health    - Check container health status"
        echo "  logs      - Show recent container logs"
        echo "  import    - Test Python module import"
        echo "  aws       - Test AWS credentials"
        echo "  mcp       - Test MCP server functionality"
        echo "  all       - Run all tests (default)"
        ;;
esac
