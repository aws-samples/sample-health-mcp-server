# Project Structure

```
aws-health-mcp-server/
├── aws_health_mcp/
│   └── server/
│       ├── __init__.py           # Package initialization
│       ├── __main__.py           # Entry point and logging setup
│       ├── client.py             # AWS Health API client: async, batching, caching
│       ├── config.py             # Configuration from environment variables
│       ├── consts.py             # Service name aliases
│       ├── formatters.py         # Service name resolution and markdown output
│       └── server.py             # MCP server and tool definitions
├── examples/
│   └── mcp-config.json           # MCP client configuration example
├── tests/
│   └── test_server.py            # Test suite
├── .github/
│   └── workflows/
│       ├── ci.yml                # Lint, type check, test, build
│       └── release.yml           # Release automation
├── .gitignore
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE                       # MIT-0
├── PROJECT_STRUCTURE.md          # This file
├── README.md
└── pyproject.toml
```

## Tools

All tools are read-only and annotated as such. The Health API's two mutating
operations (`EnableHealthServiceAccessForOrganization` and
`DisableHealthServiceAccessForOrganization`) are deliberately not exposed.

| Scope | Tools |
|---|---|
| Account | `get_service_health`, `get_affected_entities`, `get_service_events`, `get_completed_events`, `get_scheduled_changes` |
| Organization | `get_org_health_events`, `get_org_service_health`, `get_org_affected_entities`, `get_org_service_events`, `get_org_account_events`, `get_org_scheduled_changes`, `list_affected_accounts` |
| Detail & aggregates | `get_event_details`, `summarize_health_events`, `count_affected_entities` |
| Discovery & diagnostics | `list_event_types`, `check_health_access` |

## Design notes

- **Service names come from the API.** `DescribeEventTypes` is the authoritative
  source (~320 services), cached for 24h. Names are matched on a normalized key
  so "Kinesis Video", "kinesis-video" and `KINESIS_VIDEO` all resolve; only
  genuinely semantic aliases (Step Functions → `STATES`) live in `consts.py`.
- **Summarize before listing.** The listing tools return full event
  descriptions and can run to tens of thousands of tokens.
  `summarize_health_events` counts without fetching descriptions, and
  `get_event_details` drills into specific ARNs.
- **Batching.** `DescribeEventDetails` and the organization entity filters cap
  at 10 items per call; `client.py` batches and runs them concurrently under a
  semaphore (`HEALTH_API_MAX_CONCURRENCY`, default 5).
