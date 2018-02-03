* Script Author: Celal Emre CICEK
* Script License: GNU General Public License v3

* This script updates a group in Slack with the on-call user retrieved from an OpsGenie schedule. You can deploy it as a
    Lambda function to AWS and connect it with CloudWatch Events to periodically update a Slack group with the OpsGenie
    schedule's on-call person to not bother updating your Slack group manually.

* This script is configured by global variables and optionally AWS Lambda environment variables depending on your
    security policies. Please inspect the script and fill the needed fields, and do the necessary configurations before
    and while deploying to AWS.

* This script reads OpsGenie API Key and Slack API Token either from S3 or from environment variables (default is the
    environment variables method) with names:
        - OPSGENIE_API_KEY for the OpsGenie API Key
        - SLACK_API_TOKEN for the Slack API Token

    Please make sure that you supplied the correct environment variables or edited the script with your S3 bucket and
    file names before deploying it to AWS.

* This script needs a Slack app with scopes:
    - usergroups:read
    - usergroups:write
    - users:read
    - users:read.email
