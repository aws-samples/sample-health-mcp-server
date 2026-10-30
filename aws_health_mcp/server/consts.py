"""Constants for AWS Health MCP Server.

The authoritative list of AWS service codes comes from the Health API itself
(``DescribeEventTypes``) -- see ``HealthClient.get_known_services``. Hardcoding
that list is a trap: the API knows ~320 services, and any static copy both goes
stale and silently rejects services it has never heard of.

What *is* kept here is the small set of aliases that pure string normalization
cannot resolve, i.e. cases where the name people use differs semantically from
the code AWS Health uses.
"""

# Keys are "compressed" service names: uppercased with every non-alphanumeric
# character stripped, so "Step Functions", "step-functions" and "STEP_FUNCTIONS"
# all arrive here as "STEPFUNCTIONS". Values are real AWS Health service codes.
#
# Plain spelling differences (e.g. "Kinesis Video" -> "KINESIS_VIDEO",
# "Storage Gateway" -> "STORAGEGATEWAY") need no entry: compression handles them.
SERVICE_ALIASES: dict[str, str] = {
    # Names that differ from the Health service code
    "STEPFUNCTIONS": "STATES",
    "SFN": "STATES",
    "EVENTBRIDGE": "EVENTS",
    "CLOUDWATCHEVENTS": "EVENTS",
    "EFS": "ELASTICFILESYSTEM",
    "ELASTICSEARCH": "ES",
    "OPENSEARCH": "ES",
    "ELB": "ELASTICLOADBALANCING",
    "ALB": "ELASTICLOADBALANCING",
    "NLB": "ELASTICLOADBALANCING",
    "ELASTICLOADBALANCER": "ELASTICLOADBALANCING",
    "EMR": "ELASTICMAPREDUCE",
    "MSK": "KAFKA",
    "ACMPCA": "ACMPRIVATECA",
    "KINESISFIREHOSE": "FIREHOSE",
    "KINESISDATAFIREHOSE": "FIREHOSE",
    "COGNITOIDP": "COGNITO",
    "COGNITOIDENTITY": "COGNITO",
    "COGNITOUSERPOOLS": "COGNITO",
    # Common shorthands
    "DYNAMO": "DYNAMODB",
    "BEANSTALK": "ELASTICBEANSTALK",
}
