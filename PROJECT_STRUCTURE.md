# Project Structure

```
aws-health-mcp-server/
├── aws_health_mcp/
│   └── server/
│       ├── __init__.py          # Package initialization
│       ├── __main__.py          # Entry point with production features
│       ├── client.py            # AWS Health API client with retry logic
│       ├── config.py            # Configuration management
│       ├── consts.py            # Constants and service definitions
│       ├── debug_helper.py      # Logging and health checks
│       ├── errors.py            # Custom exceptions
│       ├── formatters.py        # Output formatting utilities
│       ├── models.py            # Data models
│       ├── org_tools.py         # Organization-level tools
│       └── server.py            # Main MCP server implementation
├── examples/
│   ├── .env.example             # Environment configuration template
│   └── mcp-config.json          # MCP client configuration example
├── scripts/
│   ├── build.sh                 # Production build script
│   └── install.sh               # Installation script
├── tests/                       # Test files
├── .github/
│   └── workflows/
│       ├── ci.yml               # Continuous integration
│       └── release.yml          # Release automation
├── .gitignore                   # Git ignore rules
├── CODE_OF_CONDUCT.md           # Community guidelines
├── CONTRIBUTING.md              # Contribution guidelines
├── LICENSE                      # MIT license
├── PROJECT_STRUCTURE.md         # This file
├── README.md                    # Main documentation
└── pyproject.toml               # Python project configuration
```

## Key Features

- **Production-ready**: Error handling, retry logic, logging, health checks
- **Easy installation**: `pip install aws-health-mcp-server`
- **GitHub ready**: CI/CD workflows, contribution guidelines
- **Clean structure**: Minimal, focused codebase
- **Examples included**: Configuration templates and usage examples
