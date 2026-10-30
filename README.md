# AWS Health MCP Server

> **Disclaimer:** This AWS content is provided subject to the terms of the AWS Customer Agreement available at https://aws.amazon.com/agreement or other written agreement between the Customer and Amazon Web Services. This is sample code for demonstration purposes only. It is not intended for production use. You should work with your security and legal teams to meet your organizational security, regulatory, and compliance requirements before any deployment.

MCP server that exposes AWS Health API as tools. Works with Claude Desktop, Kiro or any MCP-compatible client.

📖 **Blog:** [Building an AWS Health MCP Server for Agentic Operations](https://medium.com/@jsanketh1799/building-an-aws-health-mcp-server-for-agentic-operations-cda234012e38)


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

All tools are read-only and annotated as such. The Health API's two mutating
operations (`EnableHealthServiceAccessForOrganization` and
`DisableHealthServiceAccessForOrganization`) are deliberately not exposed.

### Start here

| Tool | Description |
|------|-------------|
| `summarize_health_events(group_by?, include_closed?)` | Event **counts** by service, status, category or region. Cheap overview — the listing tools include full descriptions and can be very large. |
| `get_event_details(event_arns)` | Full detail for specific events, by ARN |
| `find_events_for_resources(entity_values, include_closed?)` | Which events affect *your* resources, e.g. `i-1234567890abcdef0` |
| `check_health_access()` | Diagnose credentials, support plan and org access |

### Account-Level

| Tool | Description |
|------|-------------|
| `get_service_health(regions?)` | All active health events |
| `get_affected_entities` | Resources impacted by open events |
| `get_service_events(service, regions?)` | Events for a specific service (e.g., EC2, RDS) |
| `get_completed_events(service?, regions?)` | Recently resolved events |
| `get_scheduled_changes(regions?)` | Upcoming maintenance |
| `count_affected_entities(event_arns)` | How many resources an event hits, without listing them |

### Organization-Level

| Tool | Description |
|------|-------------|
| `get_org_health_events(service?, account_id?, status?, regions?)` | Events across all accounts |
| `get_org_service_health` | Active events org-wide |
| `get_org_affected_entities(account_id?, event_arn?)` | Impacted resources across accounts |
| `get_org_service_events(service, regions?)` | Service-specific events org-wide |
| `get_org_account_events(account_id, regions?)` | Events for a specific account |
| `get_org_scheduled_changes` | Org-wide scheduled maintenance |
| `list_affected_accounts(event_arn)` | Accounts affected by one event |

### Discovery

| Tool | Description |
|------|-------------|
| `list_event_types(service?, category?)` | Event types AWS Health reports, and the service codes it uses |

## Example Prompts

- "Are there any active AWS health events?"
- "Give me a summary of current AWS issues by service"
- "What's happening with EC2 right now?"
- "What's broken in us-west-2?"
- "Is instance i-1234567890abcdef0 affected by anything?"
- "Show me scheduled maintenance across my organization"
- "What resources are affected by current issues in account 123456789012?"

### Service names

Pass service names however you like — `EC2`, `ec2`, `Step Functions`,
`api gateway` all resolve. The valid set comes from the Health API itself, so
every service AWS covers is reachable, and names are mapped to the codes AWS
actually uses (Step Functions is `STATES`, EventBridge is `EVENTS`). Use
`list_event_types` to browse them. Common names resolve in about a second; an
unrecognised name (a typo, say) triggers a one-time ~8 second load of the full
service list, which is then cached.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_PROFILE` | none | AWS credentials profile |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`) |
| `HEALTH_API_TIMEOUT` | `30` | API read timeout in seconds |
| `HEALTH_API_MAX_CONCURRENCY` | `5` | Max concurrent Health API calls |
| `ENABLE_CACHE` | `true` | Cache event descriptions and affected accounts |
| `CACHE_TTL` | `300` | Cache lifetime in seconds |
| `SERVICE_LIST_TTL` | `86400` | Cache lifetime for the service catalog |

The region is not configurable; see [Regions and availability](#regions-and-availability).

## Regions and availability

The AWS Health API runs as an active-passive pair: `us-east-1` (active) and
`us-east-2` (passive), behind a single global endpoint,
`global.health.amazonaws.com`, whose DNS (10 second TTL) points at whichever
region is currently active.

- **Which endpoint this server uses.** The client is created for `us-east-1`,
  which boto3/botocore resolve to `https://global.health.amazonaws.com`. This
  holds for every botocore release this package supports (checked on 1.34.162
  and 1.43.89). The server therefore follows AWS's DNS failover; there is no
  region setting because the global endpoint chooses for you.
- **No client-side failover.** The server does not detect a failover itself or
  retry against `us-east-2`. Recovery relies on DNS re-resolution and
  botocore's retries (3 attempts, adaptive), so requests made during the switch
  can fail and a long-running server may need a call or two to pick up the new
  region. Restart the server if calls keep failing after AWS reports the
  Health API has failed over.
- **Passive data can lag.** AWS notes that only the active endpoint has the
  latest data; the passive endpoint is eventually consistent. During an
  incident, treat results as potentially slightly behind.
- **Not verified.** Requests to the global endpoint are signed for `us-east-1`
  (botocore's rule). AWS documents the signing region as that of the *active*
  endpoint, so it is not confirmed that requests signed for `us-east-1` are
  accepted after a failover to `us-east-2`. A real failover could not be tested.
  Calling `health.us-east-2.amazonaws.com` directly requires signing for
  `us-east-2`; a `us-east-1` signature is rejected with
  `InvalidSignatureException`.

Pinning the server to `us-east-2` is not supported. Overriding the endpoint
alone (for example with `AWS_ENDPOINT_URL_HEALTH`) still signs requests for
`us-east-1` and is rejected with `InvalidSignatureException`.

## Errors and partial results

Failures are reported, never turned into an empty answer:

- **Tool errors** (no Health access, API rejection, throttling that stops a
  request) are returned with the MCP `isError` flag set, so clients and agents
  can tell a failure from a result.
- **Partial results:** when one lookup inside a larger answer fails (for example
  the affected accounts of a single event), the rest is still returned with a
  "Warning: partial results" footer naming what is missing.
- **Searches:** `find_events_for_resources` returns an error rather than "no
  event affects it" if some events could not be checked.

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
git clone https://github.com/aws-samples/sample-health-mcp-server.git
cd aws-health-mcp-server
uv sync --extra dev
uv run pytest tests/ -v
```

## License

MIT-0
