# AWS Health MCP Server

An MCP (Model Context Protocol) server for AWS Health API that provides comprehensive visibility into AWS service health events across both individual accounts and entire AWS Organizations.

## Features

- **Account-Level Health Monitoring**:
  - View current AWS service health events
  - Get detailed information about affected resources
  - Check service-specific health events
  - View completed/resolved health events
  - Monitor scheduled changes and maintenance

- **Organization-Level Health Monitoring**:
  - View health events across all accounts in your AWS Organization
  - See which accounts are affected by specific events
  - Check service-specific health events across your organization
  - Monitor account-specific health events
  - Track scheduled changes across your organization

## Prerequisites

- Python 3.8+
- AWS credentials with appropriate permissions
- For organization-level features: AWS Organizations enabled and proper permissions

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/jsanketh/AWS-health-MCP.git
   cd AWS-health-MCP
   ```

2. Install dependencies:
   ```
   pip install -e .
   ```

3. Configure AWS credentials:
   ```
   aws configure
   ```

## Usage

### With Kiro IDE

1. Add the MCP server configuration to your `.kiro/settings/mcp.json` file:
   ```json
   {
     "mcpServers": {
       "aws-health": {
         "command": "python3",
         "args": [
           "-m",
           "awslabs.aws_health_mcp_server"
         ],
         "env": {},
         "disabled": false,
         "autoApprove": [
           "get_service_health",
           "get_org_health_events",
           "get_service_events",
           "get_scheduled_changes",
           "get_affected_entities",
           "get_completed_events",
           "get_org_service_health",
           "get_org_affected_entities",
           "get_org_service_events",
           "get_org_account_events",
           "get_org_scheduled_changes"
         ]
       }
     }
   }
   ```

2. Use the MCP tools in Kiro IDE to interact with AWS Health API.

### Available Tools

#### Account-Level Tools

- `get_service_health()`: Get current AWS service health events
- `get_affected_entities()`: Get affected entities for all open AWS health events
- `get_service_events(service)`: Get health events for a specific AWS service
- `get_completed_events(service=None)`: Get completed/closed health events
- `get_scheduled_changes()`: Get all scheduled changes/maintenance events

#### Organization-Level Tools

- `get_org_health_events(service=None, account_id=None, status="active")`: Get health events across your AWS Organization
- `get_org_service_health()`: Get current AWS service health events across your organization
- `get_org_affected_entities(account_id=None, event_arn=None)`: Get affected entities for AWS health events across your organization
- `get_org_service_events(service)`: Get health events for a specific AWS service across your organization
- `get_org_account_events(account_id)`: Get health events for a specific AWS account in your organization
- `get_org_scheduled_changes()`: Get all scheduled changes/maintenance events across your AWS Organization

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.