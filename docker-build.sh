#!/bin/bash

# AWS Health MCP Server Docker Build and Run Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="aws-health-mcp-server"
CONTAINER_NAME="aws-health-mcp-server"
TAG="latest"

# Functions
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

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is running"
}

# Build Docker image
build_image() {
    print_header "Building Docker Image"
    
    if docker build -t "${IMAGE_NAME}:${TAG}" .; then
        print_success "Docker image built successfully: ${IMAGE_NAME}:${TAG}"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
}

# Check AWS credentials
check_aws_credentials() {
    print_header "Checking AWS Credentials"
    
    if [ -f ".env" ]; then
        print_success "Found .env file"
    elif [ -d "$HOME/.aws" ]; then
        print_success "Found AWS credentials directory"
    elif [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
        print_success "Found AWS credentials in environment variables"
    else
        print_warning "No AWS credentials found. Please configure:"
        echo "  1. Create .env file from .env.example"
        echo "  2. Or run 'aws configure'"
        echo "  3. Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables"
    fi
}

# Run container
run_container() {
    print_header "Running Container"
    
    # Stop existing container if running
    if docker ps -q -f name="${CONTAINER_NAME}" | grep -q .; then
        print_warning "Stopping existing container..."
        docker stop "${CONTAINER_NAME}" > /dev/null 2>&1
        docker rm "${CONTAINER_NAME}" > /dev/null 2>&1
    fi
    
    # Run with docker-compose if available, otherwise use docker run
    if [ -f "docker-compose.yml" ]; then
        print_success "Using docker-compose..."
        docker-compose up -d
    else
        print_success "Using docker run..."
        docker run -d \
            --name "${CONTAINER_NAME}" \
            --env-file .env \
            -v "$HOME/.aws:/home/appuser/.aws:ro" \
            -p 8000:8000 \
            "${IMAGE_NAME}:${TAG}"
    fi
    
    print_success "Container started successfully"
}

# Show container logs
show_logs() {
    print_header "Container Logs"
    docker logs -f "${CONTAINER_NAME}"
}

# Show usage
usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build     Build the Docker image"
    echo "  run       Run the container"
    echo "  logs      Show container logs"
    echo "  stop      Stop the container"
    echo "  restart   Restart the container"
    echo "  clean     Remove container and image"
    echo "  all       Build and run (default)"
    echo ""
}

# Main script
main() {
    case "${1:-all}" in
        "build")
            check_docker
            build_image
            ;;
        "run")
            check_docker
            check_aws_credentials
            run_container
            ;;
        "logs")
            show_logs
            ;;
        "stop")
            print_header "Stopping Container"
            docker-compose down 2>/dev/null || docker stop "${CONTAINER_NAME}" 2>/dev/null || true
            print_success "Container stopped"
            ;;
        "restart")
            print_header "Restarting Container"
            docker-compose restart 2>/dev/null || docker restart "${CONTAINER_NAME}" 2>/dev/null
            print_success "Container restarted"
            ;;
        "clean")
            print_header "Cleaning Up"
            docker-compose down 2>/dev/null || docker stop "${CONTAINER_NAME}" 2>/dev/null || true
            docker rm "${CONTAINER_NAME}" 2>/dev/null || true
            docker rmi "${IMAGE_NAME}:${TAG}" 2>/dev/null || true
            print_success "Cleanup completed"
            ;;
        "all")
            check_docker
            build_image
            check_aws_credentials
            run_container
            echo ""
            print_success "Setup completed! Use '$0 logs' to view container logs"
            ;;
        "help"|"-h"|"--help")
            usage
            ;;
        *)
            print_error "Unknown command: $1"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
