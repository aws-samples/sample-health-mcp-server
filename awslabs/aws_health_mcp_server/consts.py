"""Constants for AWS Health MCP Server."""

# System prompt for AWS Health API interactions
SYSTEM_PROMPT = """You are an AWS Health API assistant. You can help users:
1. Monitor AWS service health status
2. Track and analyze AWS health events
3. Get information about affected resources
4. View scheduled maintenance and changes
5. Access organization-wide health events

Always provide clear, concise responses and highlight any critical issues that require immediate attention.
Format your responses in a structured way for better readability."""

# Example prompts for different scenarios
EXAMPLE_PROMPTS = [
    "What's the current health status of AWS services?",
    "Show me any active issues with EC2 instances",
    "Are there any scheduled maintenance events?",
    "List all affected resources in our organization",
    "Check if there are any ongoing issues in the us-east-1 region",
]

# Help text for using the AWS Health API tools
HELP_TEXT = """AWS Health API Tools Help:

1. Service Health Status:
   - Use get_service_health() to check overall AWS service status
   - Use get_service_events(service) for specific service issues

2. Maintenance & Changes:
   - Use get_scheduled_changes() to view upcoming maintenance
   - Check get_completed_events() for historical events

3. Resource Impact:
   - Use get_affected_entities() to see impacted resources
   - Filter by service or account with get_org_health_events()

4. Organization View:
   - Use get_org_health_events() for multi-account visibility
   - Specify account_id to focus on specific accounts

Tips:
- Always check service health before investigating specific issues
- Use scheduled changes to plan for maintenance
- Monitor organization events for broad impact assessment"""

# Valid AWS service names for validation
VALID_AWS_SERVICES = [
    "ACMPCA",
    "AMPLIFY",
    "API_GATEWAY",
    "APPFLOW",
    "APPLICATION_AUTOSCALING",
    "ATHENA",
    "AUTOSCALING",
    "BACKUP",
    "BATCH",
    "CLOUDFORMATION",
    "CLOUDFRONT",
    "CLOUDHSM",
    "CLOUDSEARCH",
    "CLOUDWATCH",
    "CODEARTIFACT",
    "CODEBUILD",
    "CODECOMMIT",
    "CODEDEPLOY",
    "CODEPIPELINE",
    "COGNITO_IDP",
    "COGNITO_IDENTITY",
    "CONFIG",
    "CONNECT",
    "DAX",
    "DIRECTCONNECT",
    "DMS",
    "DOCDB",
    "DYNAMODB",
    "EBS",
    "EC2",
    "ECR",
    "ECS",
    "EFS",
    "EKS",
    "ELASTIC_INFERENCE",
    "ELASTICACHE",
    "ELASTICBEANSTALK",
    "ELASTICFILESYSTEM",
    "ELASTICLOADBALANCING",
    "ELASTICMAPREDUCE",
    "ELASTICTRANSCODER",
    "ELASTICSEARCH",
    "EVENTBRIDGE",
    "FIREHOSE",
    "FSX",
    "GAMELIFT",
    "GLACIER",
    "GLUE",
    "GREENGRASS",
    "GUARDDUTY",
    "IAM",
    "IMAGEBUILDER",
    "INSPECTOR",
    "IOT",
    "KAFKA",
    "KINESIS",
    "KINESISANALYTICS",
    "KINESISFIREHOSE",
    "KINESISVIDEO",
    "KMS",
    "LAMBDA",
    "QLDB",
    "RDS",
    "REDSHIFT",
    "REKOGNITION",
    "ROUTE53",
    "S3",
    "SAGEMAKER",
    "SECRETSMANAGER",
    "SECURITYHUB",
    "SES",
    "SNS",
    "SQS",
    "SSM",
    "STEP_FUNCTIONS",
    "STORAGE_GATEWAY",
    "SWF",
    "TEXTRACT",
    "TIMESTREAM",
    "TRANSFER",
    "VPC",
    "WORKSPACES",
    "XRAY",
]
