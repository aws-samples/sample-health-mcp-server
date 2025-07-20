"""Main entry point for AWS Health MCP Server."""

import sys

from .debug_helper import setup_logging, validate_aws_credentials
from .server import run_server


def main():
    """Main entry point."""
    # Setup logging
    setup_logging()

    # Validate AWS credentials
    if not validate_aws_credentials():
        print("Error: AWS credentials not found or invalid.", file=sys.stderr)
        print("Please configure your AWS credentials using:", file=sys.stderr)
        print("  - AWS CLI: aws configure", file=sys.stderr)
        print(
            "  - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY", file=sys.stderr
        )
        print("  - IAM roles (for EC2 instances)", file=sys.stderr)
        sys.exit(1)

    # Run the server
    run_server()


if __name__ == "__main__":
    main()
