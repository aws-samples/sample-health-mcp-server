# AWS Health MCP Server

> **Disclaimer:** This AWS content is provided subject to the terms of the AWS Customer Agreement available at https://aws.amazon.com/agreement or other written agreement between the Customer and Amazon Web Services. This is sample code for demonstration purposes only. It is not intended for production use. You should work with your security and legal teams to meet your organizational security, regulatory, and compliance requirements before any deployment.

MCP server that exposes AWS Health API as tools. Works with Claude Desktop, Kiro, Amazon Q CLI, or any MCP-compatible client.

## Prerequisites

- Python 3.10+
- AWS credentials configured (`aws configure` or environment variables)
- AWS **Business or Enterprise Support** plan (required for Health API)
- For org-level tools: AWS Organizations with Health service access enabled

## Setup

Add this to your MCP config file:

- **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Kiro**: `~/.kiro/settings/mcp.json`
- **Amazon Q CLI**: `~/.aws/amazonq/mcp.json`

### Using uvx from PyPI (recommended)

```json
{
  "mcpServers": {
    "aws-health": {
      "command": "uvx",
      "args": ["aws-health-mcp-server"],
      "env": {
        "AWS_PROFILE": "default"
      }
    }
  }
}
```

### Using pip

```bash
pip install aws-health-mcp-server
```

### From a local clone

```json
{
  "mcpServers": {
    "aws-health": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/aws-health-mcp-server", "aws-health-mcp-server"],
      "env": {
        "AWS_PROFILE": "default"
      }
    }
  }
}
```

That's it. `uv` handles the venv and dependencies automatically.

## Tools

### Account-Level

| Tool | Description |
|------|-------------|
| `get_service_health` | All active health events |
| `get_affected_entities` | Resources impacted by open events |
| `get_service_events(service)` | Events for a specific service (e.g., EC2, RDS) |
| `get_completed_events(service?)` | Recently resolved events |
| `get_scheduled_changes` | Upcoming maintenance |

### Organization-Level

| Tool | Description |
|------|-------------|
| `get_org_health_events(service?, account_id?, status?)` | Events across all accounts |
| `get_org_service_health` | Active events org-wide |
| `get_org_affected_entities(account_id?, event_arn?)` | Impacted resources across accounts |
| `get_org_service_events(service)` | Service-specific events org-wide |
| `get_org_account_events(account_id)` | Events for a specific account |
| `get_org_scheduled_changes` | Org-wide scheduled maintenance |

## Example Prompts

- "Are there any active AWS health events?"
- "What's happening with EC2 right now?"
- "Show me scheduled maintenance across my organization"
- "What resources are affected by current issues in account 123456789012?"

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_PROFILE` | none | AWS credentials profile |
| `AWS_REGION` | `us-east-1` | Region (Health API is us-east-1 only) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`) |
| `HEALTH_API_TIMEOUT` | `30` | API timeout in seconds |

## Troubleshooting

**"SubscriptionRequiredException"** — You need AWS Business or Enterprise Support.

**"AccessDeniedException"** — Your IAM user/role needs `health:Describe*` permissions.

**Org tools return access error** — Enable Health service access from your management account:
```bash
aws health enable-health-service-access-for-organization
```

**Server not starting** — Check the MCP client logs. Common issues:
- Wrong Python path in config (use the full `.venv/bin/python` path)
- Missing dependencies (run `pip install -e .` in the venv)

## Development

```bash
git clone https://gitlab.aws.dev/jsanketh/aws-health-mcp-server.git
cd aws-health-mcp-server
uv sync --extra dev
uv run pytest tests/ -v
```

## License

MIT
