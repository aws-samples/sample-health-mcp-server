#!/bin/bash

# Master Test Runner for AWS Health MCP Server
# This script runs all available tests in the correct order

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                 AWS Health MCP Server Tests                  ║"
    echo "║                     Complete Test Suite                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_section() {
    echo -e "${BLUE}"
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│ $1"
    echo "└─────────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
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

# Configuration
CONTAINER_NAME="aws-health-mcp-server"
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Test functions
run_container_tests() {
    print_section "Phase 1: Container Health Tests"
    
    if [ -f "$TEST_DIR/test-container.sh" ]; then
        echo "Running container health tests..."
        if "$TEST_DIR/test-container.sh" all; then
            print_success "Container tests completed"
            return 0
        else
            print_warning "Some container tests failed"
            return 1
        fi
    else
        print_error "Container test script not found"
        return 1
    fi
}

run_mcp_tests() {
    print_section "Phase 2: MCP Functionality Tests"
    
    if [ -f "$TEST_DIR/test-mcp-client.py" ]; then
        echo "Running MCP functionality tests..."
        if python3 "$TEST_DIR/test-mcp-client.py" "$CONTAINER_NAME"; then
            print_success "MCP tests completed"
            return 0
        else
            print_warning "Some MCP tests failed"
            return 1
        fi
    else
        print_error "MCP test script not found"
        return 1
    fi
}

run_integration_tests() {
    print_section "Phase 3: Integration Tests"
    
    if [ -f "$TEST_DIR/test-integration.py" ]; then
        echo "Running integration tests..."
        if python3 "$TEST_DIR/test-integration.py" "$CONTAINER_NAME"; then
            print_success "Integration tests completed"
            return 0
        else
            print_warning "Some integration tests failed"
            return 1
        fi
    else
        print_error "Integration test script not found"
        return 1
    fi
}

check_prerequisites() {
    print_section "Prerequisites Check"
    
    local all_good=true
    
    # Check Docker
    if command -v docker >/dev/null 2>&1; then
        if docker info >/dev/null 2>&1; then
            print_success "Docker is running"
        else
            print_error "Docker is not running"
            all_good=false
        fi
    else
        print_error "Docker is not installed"
        all_good=false
    fi
    
    # Check Python
    if command -v python3 >/dev/null 2>&1; then
        print_success "Python 3 is available"
    else
        print_error "Python 3 is not installed"
        all_good=false
    fi
    
    # Check if container exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            print_success "Container is running"
        else
            print_warning "Container exists but is not running"
            echo "Starting container..."
            if docker start "$CONTAINER_NAME" >/dev/null 2>&1; then
                print_success "Container started"
                sleep 3  # Give it time to start
            else
                print_error "Failed to start container"
                all_good=false
            fi
        fi
    else
        print_warning "Container does not exist"
        echo "You may need to run: ./docker-build.sh"
        all_good=false
    fi
    
    if [ "$all_good" = true ]; then
        print_success "All prerequisites met"
        return 0
    else
        print_error "Prerequisites not met"
        return 1
    fi
}

show_usage() {
    echo "Usage: $0 [OPTIONS] [TEST_TYPE]"
    echo ""
    echo "Test Types:"
    echo "  all           Run all tests (default)"
    echo "  container     Run container health tests only"
    echo "  mcp           Run MCP functionality tests only"
    echo "  integration   Run integration tests only"
    echo "  quick         Run quick tests (container + mcp)"
    echo ""
    echo "Options:"
    echo "  --container-name NAME   Use specific container name (default: aws-health-mcp-server)"
    echo "  --skip-prereq          Skip prerequisites check"
    echo "  --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                     # Run all tests"
    echo "  $0 quick              # Run quick tests only"
    echo "  $0 --container-name my-mcp-server all"
}

# Parse command line arguments
SKIP_PREREQ=false
TEST_TYPE="all"

while [[ $# -gt 0 ]]; do
    case $1 in
        --container-name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --skip-prereq)
            SKIP_PREREQ=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        all|container|mcp|integration|quick)
            TEST_TYPE="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_banner
    
    echo "Container: $CONTAINER_NAME"
    echo "Test Type: $TEST_TYPE"
    echo ""
    
    # Check prerequisites unless skipped
    if [ "$SKIP_PREREQ" = false ]; then
        if ! check_prerequisites; then
            echo ""
            print_error "Prerequisites check failed. Fix the issues above and try again."
            echo "Or use --skip-prereq to skip this check."
            exit 1
        fi
        echo ""
    fi
    
    # Track test results
    local container_result=0
    local mcp_result=0
    local integration_result=0
    
    # Run tests based on type
    case $TEST_TYPE in
        "container")
            run_container_tests
            container_result=$?
            ;;
        "mcp")
            run_mcp_tests
            mcp_result=$?
            ;;
        "integration")
            run_integration_tests
            integration_result=$?
            ;;
        "quick")
            run_container_tests
            container_result=$?
            echo ""
            run_mcp_tests
            mcp_result=$?
            ;;
        "all")
            run_container_tests
            container_result=$?
            echo ""
            run_mcp_tests
            mcp_result=$?
            echo ""
            run_integration_tests
            integration_result=$?
            ;;
    esac
    
    # Final summary
    echo ""
    print_section "Final Test Summary"
    
    local total_phases=0
    local passed_phases=0
    
    if [[ "$TEST_TYPE" == "all" || "$TEST_TYPE" == "quick" || "$TEST_TYPE" == "container" ]]; then
        total_phases=$((total_phases + 1))
        if [ $container_result -eq 0 ]; then
            print_success "Container tests: PASSED"
            passed_phases=$((passed_phases + 1))
        else
            print_warning "Container tests: FAILED"
        fi
    fi
    
    if [[ "$TEST_TYPE" == "all" || "$TEST_TYPE" == "quick" || "$TEST_TYPE" == "mcp" ]]; then
        total_phases=$((total_phases + 1))
        if [ $mcp_result -eq 0 ]; then
            print_success "MCP tests: PASSED"
            passed_phases=$((passed_phases + 1))
        else
            print_warning "MCP tests: FAILED"
        fi
    fi
    
    if [[ "$TEST_TYPE" == "all" || "$TEST_TYPE" == "integration" ]]; then
        total_phases=$((total_phases + 1))
        if [ $integration_result -eq 0 ]; then
            print_success "Integration tests: PASSED"
            passed_phases=$((passed_phases + 1))
        else
            print_warning "Integration tests: FAILED"
        fi
    fi
    
    echo ""
    echo -e "${BLUE}Overall Result: $passed_phases/$total_phases test phases passed${NC}"
    
    if [ $passed_phases -eq $total_phases ]; then
        echo -e "${GREEN}"
        echo "🎉 ALL TESTS PASSED! 🎉"
        echo "Your AWS Health MCP Server is ready for production use!"
        echo -e "${NC}"
        exit 0
    else
        echo -e "${YELLOW}"
        echo "⚠️  Some tests failed. Check the output above for details."
        echo "Common solutions:"
        echo "1. Ensure container is running: ./docker-build.sh run"
        echo "2. Configure AWS credentials in .env file"
        echo "3. Check container logs: docker logs $CONTAINER_NAME"
        echo -e "${NC}"
        exit 1
    fi
}

# Run main function
main "$@"
