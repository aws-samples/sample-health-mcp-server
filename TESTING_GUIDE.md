# 🧪 Testing Guide for AWS Health MCP Server

This guide provides comprehensive testing instructions for your containerized AWS Health MCP Server.

## 🚀 Quick Start Testing

### 1. **Run All Tests (Recommended)**
```bash
./run-tests.sh
```

This runs the complete test suite including:
- Container health checks
- MCP functionality tests  
- Integration tests
- Performance benchmarks

### 2. **Quick Tests Only**
```bash
./run-tests.sh quick
```

Runs essential tests (container + MCP functionality) in under 30 seconds.

## 📋 Individual Test Scripts

### Container Health Tests
```bash
./test-container.sh
```

**What it tests:**
- ✅ Docker image exists
- ✅ Container is running
- ✅ Container health status
- ✅ Container logs for errors
- ✅ Python module imports
- ✅ AWS credentials configuration
- ✅ MCP server startup

### MCP Functionality Tests
```bash
python3 test-mcp-client.py
```

**What it tests:**
- ✅ MCP server module import
- ✅ MCP tools availability
- ✅ AWS credentials detection
- ✅ Health API accessibility
- ✅ Server startup without errors

### Integration Tests
```bash
python3 test-integration.py
```

**What it tests:**
- ✅ End-to-end MCP protocol simulation
- ✅ Real AWS Health API calls (if credentials available)
- ✅ Tool availability and functionality
- ✅ Performance benchmarks

## 🔧 Test Configuration

### Environment Setup
Before testing, ensure you have:

1. **Docker running**:
   ```bash
   docker info
   ```

2. **Container built and running**:
   ```bash
   ./docker-build.sh
   ```

3. **AWS credentials configured** (optional but recommended):
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials
   ```

### Test Parameters
You can customize tests with parameters:

```bash
# Use different container name
./run-tests.sh --container-name my-custom-mcp-server

# Skip prerequisites check
./run-tests.sh --skip-prereq

# Run specific test type
./run-tests.sh container    # Container tests only
./run-tests.sh mcp         # MCP tests only
./run-tests.sh integration # Integration tests only
```

## 📊 Understanding Test Results

### ✅ **All Tests Pass**
Your MCP server is ready for production use!

### ⚠️ **Some Tests Fail**
Common issues and solutions:

| Issue | Solution |
|-------|----------|
| Container not running | Run `./docker-build.sh run` |
| AWS credentials missing | Configure `.env` file or AWS CLI |
| Health API access denied | Requires AWS Business/Enterprise support |
| Import errors | Check container logs: `docker logs aws-health-mcp-server` |
| Permission errors | Ensure Docker has proper permissions |

### 🔍 **Detailed Diagnostics**

#### Check Container Status
```bash
docker ps --filter name=aws-health-mcp-server
docker logs aws-health-mcp-server
```

#### Test AWS Credentials
```bash
docker exec aws-health-mcp-server python -c "
import boto3
try:
    sts = boto3.client('sts')
    print('Account:', sts.get_caller_identity()['Account'])
except Exception as e:
    print('Error:', e)
"
```

#### Test MCP Tools
```bash
docker exec aws-health-mcp-server python -c "
import sys
sys.path.insert(0, '/app')
from awslabs.aws_health_mcp_server.server import app
tools = app.list_tools()
print(f'Available tools: {len(tools)}')
for tool in tools:
    print(f'  - {tool.name}')
"
```

## 🎯 Test Scenarios

### Scenario 1: Development Testing
```bash
# Quick validation during development
./run-tests.sh quick
```

### Scenario 2: Pre-deployment Testing
```bash
# Full test suite before production deployment
./run-tests.sh all
```

### Scenario 3: Production Health Check
```bash
# Container health only (for monitoring)
./test-container.sh
```

### Scenario 4: AWS Integration Testing
```bash
# Focus on AWS API integration
python3 test-integration.py
```

## 🚨 Troubleshooting Common Issues

### Issue: "Container not found"
```bash
# Check if container exists
docker ps -a | grep aws-health-mcp-server

# If not found, build and run
./docker-build.sh
```

### Issue: "AWS credentials not configured"
```bash
# Option 1: Use .env file
cp .env.example .env
# Edit .env with your credentials

# Option 2: Use AWS CLI
aws configure

# Option 3: Use environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

### Issue: "Health API access denied"
This is expected if you don't have AWS Business or Enterprise support. The MCP server will still work for other AWS services.

### Issue: "Python import errors"
```bash
# Check container Python environment
docker exec aws-health-mcp-server python -c "
import sys
print('Python version:', sys.version)
print('Python path:', sys.path)
"

# Rebuild container if needed
docker-compose down
./docker-build.sh build
```

## 📈 Performance Expectations

### Normal Performance Ranges:
- **Container startup**: < 5 seconds
- **Module import**: < 1 second
- **Tool listing**: < 0.5 seconds
- **AWS API call**: 1-3 seconds (network dependent)

### Performance Issues:
If tests are significantly slower:
1. Check Docker resource allocation
2. Verify network connectivity to AWS
3. Check container resource usage: `docker stats aws-health-mcp-server`

## 🔄 Continuous Testing

### Automated Testing in CI/CD
```bash
# Add to your CI/CD pipeline
./run-tests.sh --skip-prereq quick
```

### Monitoring in Production
```bash
# Health check endpoint (if implemented)
curl http://localhost:8000/health

# Or use container health check
docker inspect --format='{{.State.Health.Status}}' aws-health-mcp-server
```

## 📝 Test Reports

Tests generate detailed output including:
- ✅ Pass/fail status for each test
- 📊 Performance metrics
- 🔍 Diagnostic information
- 💡 Suggested fixes for failures

Save test results for debugging:
```bash
./run-tests.sh > test-results.log 2>&1
```

## 🆘 Getting Help

If tests continue to fail:

1. **Check the logs**: `docker logs aws-health-mcp-server`
2. **Review the test output**: Look for specific error messages
3. **Verify prerequisites**: Docker, Python, AWS credentials
4. **Check AWS service status**: [AWS Health Dashboard](https://health.aws.amazon.com/health/status)
5. **Review AWS permissions**: Ensure your credentials have Health API access

Your MCP server should pass most tests even without AWS credentials - the core functionality tests don't require external API access.
