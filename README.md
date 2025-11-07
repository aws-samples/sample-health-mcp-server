# AWS Health MCP Server

A production-ready MCP (Model Context Protocol) server for AWS Health API that provides comprehensive visibility into AWS service health events across both individual accounts and entire AWS Organizations.

## Features

- **Account-Level Health Monitoring**: View current AWS service health events, affected resources, and service-specific issues
- **Organization-Level Health Monitoring**: Monitor health events across all accounts in your AWS Organization
- **Production Features**: Comprehensive error handling, retry logic, structured logging, and health checks
- **Easy Integration**: Simple setup with Q CLI, Claude Desktop, or any MCP-compatible client

## Prerequisites

- Python 3.8+
- AWS credentials with appropriate permissions
- AWS Business or Enterprise Support plan (required for Health API access)
- For organization features: AWS Organizations enabled with proper permissions

## Quick Start

### 1. Install

```bash
pip install aws-health-mcp-server
```

### 2. Configure AWS Credentials

```bash
aws configure
```

### 3. Add to MCP Client

Add to your MCP configuration (e.g., Claude Desktop, Q CLI):

```json
{
  "mcpServers": {
    "aws-health": {
      "command": "aws-health-mcp-server",
      "args": [],
      "env": {
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

### 4. Start Using

Ask your MCP client:
- "What's the current AWS service health status?"
- "Show me any active AWS incidents"
- "Are there any scheduled AWS maintenance events?"

## Available Tools

### Account-Level Tools
- `get_service_health()` - Current AWS service health events
- `get_affected_entities()` - Resources affected by health events
- `get_service_events(service)` - Health events for specific services
- `get_completed_events()` - Recently resolved incidents
- `get_scheduled_changes()` - Upcoming maintenance events

### Organization-Level Tools
- `get_org_health_events()` - Health events across your organization
- `get_org_service_health()` - Organization-wide service health
- `get_org_affected_entities()` - Affected entities across accounts
- `get_org_service_events(service)` - Service events across organization
- `get_org_account_events(account_id)` - Events for specific accounts
- `get_org_scheduled_changes()` - Organization-wide scheduled changes

## Configuration

### Environment Variables

```bash
# AWS Configuration
export AWS_REGION=us-east-1
export AWS_PROFILE=my-profile  # Optional

# Logging
export LOG_LEVEL=INFO

# API Configuration  
export HEALTH_API_TIMEOUT=30
```

### Example Configurations

#### Q CLI Configuration
```json
{
  "mcpServers": {
    "aws-health": {
      "command": "aws-health-mcp-server",
      "args": [],
      "env": {
        "LOG_LEVEL": "INFO",
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

#### Claude Desktop Configuration
```json
{
  "mcpServers": {
    "aws-health": {
      "command": "aws-health-mcp-server",
      "args": []
    }
  }
}
```

## Development

### Install from Source

```bash
git clone https://github.com/jsanketh/aws-health-mcp-server.git
cd aws-health-mcp-server
pip install -e ".[dev]"
```

### Build Package

```bash
python -m build
```

### Run Tests

```bash
pytest tests/
```

## Troubleshooting

### Common Issues

**"SubscriptionRequiredException"**
- Solution: Upgrade to AWS Business or Enterprise Support plan

**"AccessDeniedException"**  
- Solution: Ensure your AWS credentials have Health API permissions

**Organization features not working**
- Solution: Enable Health service access for your organization from the management account

### Debug Mode

```bash
LOG_LEVEL=DEBUG aws-health-mcp-server
```

## Requirements

- AWS Business or Enterprise Support subscription
- IAM permissions for AWS Health API
- For organization features: Health service enabled for AWS Organizations

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

- [GitHub Issues](https://github.com/jsanketh/aws-health-mcp-server/issues)
- [Documentation](https://github.com/jsanketh/aws-health-mcp-server)

---

Built with ❤️ 
