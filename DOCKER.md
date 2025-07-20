# Docker Deployment Guide

This guide explains how to build and run the AWS Health MCP Server using Docker.

## Quick Start

1. **Configure AWS Credentials**:
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials
   ```

2. **Build and Run**:
   ```bash
   ./docker-build.sh
   ```

3. **View Logs**:
   ```bash
   ./docker-build.sh logs
   ```

## Docker Files Overview

- `Dockerfile` - Multi-stage build for the MCP server
- `docker-compose.yml` - Orchestration with AWS credentials
- `.dockerignore` - Excludes unnecessary files from build
- `.env.example` - Template for environment variables
- `docker-build.sh` - Automated build and deployment script

## Build Options

### Option 1: Using the Build Script (Recommended)
```bash
# Build and run everything
./docker-build.sh

# Individual commands
./docker-build.sh build    # Build image only
./docker-build.sh run      # Run container only
./docker-build.sh logs     # View logs
./docker-build.sh stop     # Stop container
./docker-build.sh clean    # Remove container and image
```

### Option 2: Using Docker Compose
```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Option 3: Using Docker Commands Directly
```bash
# Build
docker build -t aws-health-mcp-server .

# Run
docker run -d \
  --name aws-health-mcp-server \
  --env-file .env \
  -v ~/.aws:/home/appuser/.aws:ro \
  -p 8000:8000 \
  aws-health-mcp-server
```

## AWS Credentials Configuration

### Method 1: Environment Variables (.env file)
```bash
# Copy and edit the example file
cp .env.example .env

# Edit with your credentials
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
```

### Method 2: AWS CLI Profile
```bash
# Configure AWS CLI first
aws configure

# Then use profile in .env
AWS_PROFILE=default
AWS_DEFAULT_REGION=us-east-1
```

### Method 3: IAM Roles (for EC2/ECS deployment)
When running on AWS infrastructure, the container can use IAM roles automatically.

## Container Features

- **Security**: Runs as non-root user
- **Health Checks**: Built-in container health monitoring
- **Logging**: Structured logging with configurable levels
- **Resource Limits**: Optimized for minimal resource usage
- **AWS Integration**: Supports all AWS credential methods

## Troubleshooting

### Container Won't Start
```bash
# Check container logs
docker logs aws-health-mcp-server

# Check if AWS credentials are configured
docker exec aws-health-mcp-server python -c "import boto3; print(boto3.Session().get_credentials())"
```

### AWS Credentials Issues
```bash
# Verify credentials in container
docker exec -it aws-health-mcp-server aws sts get-caller-identity

# Check mounted AWS config
docker exec -it aws-health-mcp-server ls -la /home/appuser/.aws/
```

### Permission Issues
```bash
# Check file permissions
ls -la ~/.aws/
# Should be readable by your user

# Fix permissions if needed
chmod 600 ~/.aws/credentials
chmod 644 ~/.aws/config
```

## Production Deployment

### Docker Swarm
```yaml
version: '3.8'
services:
  aws-health-mcp-server:
    image: aws-health-mcp-server:latest
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
    environment:
      - AWS_DEFAULT_REGION=us-east-1
    secrets:
      - aws_access_key_id
      - aws_secret_access_key
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aws-health-mcp-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: aws-health-mcp-server
  template:
    metadata:
      labels:
        app: aws-health-mcp-server
    spec:
      containers:
      - name: aws-health-mcp-server
        image: aws-health-mcp-server:latest
        env:
        - name: AWS_DEFAULT_REGION
          value: "us-east-1"
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: aws-credentials
              key: access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: aws-credentials
              key: secret-access-key
```

## Monitoring

### Health Checks
The container includes built-in health checks:
```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' aws-health-mcp-server
```

### Metrics
Monitor container resource usage:
```bash
# Resource usage
docker stats aws-health-mcp-server

# Detailed container info
docker inspect aws-health-mcp-server
```

## Security Considerations

1. **Credentials**: Never include AWS credentials in the Docker image
2. **Network**: Use Docker networks to isolate containers
3. **Updates**: Regularly update the base Python image
4. **Scanning**: Scan images for vulnerabilities before deployment

```bash
# Example security scan
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image aws-health-mcp-server:latest
```
