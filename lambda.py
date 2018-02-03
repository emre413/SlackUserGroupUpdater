# Script Author: Celal Emre CICEK
# Script License: GNU General Public License v3

import requests
import boto3
import sys
import os

# Global variables starting with prefix S3 below should be set, if GET_CREDENTIALS_FROM_S3 is True.
GET_CREDENTIALS_FROM_S3 = False
S3_SLACK_TOKEN_BUCKET = ""
S3_SLACK_TOKEN_FILE = ""
S3_OPSGENIE_API_KEY_BUCKET = ""
S3_OPSGENIE_API_KEY_FILE = ""

OPSGENIE_SCHEDULE_NAME = ""
SLACK_GROUP_NAME = ""

OPSGENIE_BASE_API_URL = "https://api.opsgenie.com"
OPSGENIE_SCHEDULES_ENDPOINT = OPSGENIE_BASE_API_URL + "/v2/schedules"
OPSGENIE_WHO_IS_ONCALL_POSTFIX = "/on-calls"
SLACK_BASE_API_URL = "https://slack.com"
SLACK_USERGROUPS_ENDPOINT = SLACK_BASE_API_URL + "/api/usergroups"
SLACK_USERS_ENDPOINT = SLACK_BASE_API_URL + "/api/users"


s3_client = boto3.client('s3')


def check_s3_file_exists(client, bucket_name, file_name):
    exists = False

    try:
        client.get_object(Bucket=bucket_name, Key=file_name)
    except Exception:
        exists = False
    else:
        exists = True

    return exists


def read_file_from_s3(client, bucket_name, file_name, version_id=None):
    req = None

    if not check_s3_file_exists(client, bucket_name, file_name):
        print "Given file does not exists in the bucket."  # Bucket and file are not printed on security purpose.
        sys.exit(-4)

    if version_id is None:
        req = client.get_object(Bucket=bucket_name, Key=file_name)
    else:
        req = client.get_object(Bucket=bucket_name, Key=file_name, VersionId=version_id)

    if req is not None and type(req) is dict:
        if req["ResponseMetadata"]["HTTPStatusCode"] == 200:
            binary_body = req["Body"]
            body = b''

            for chunk in iter(lambda: binary_body.read(1024), b''):
                body += chunk

            body = str(body)
            return body
        else:
            print "HTTP Status was not 200. HTTP Status was: " + str(req["ResponseMetadata"]["HTTPStatusCode"])
            sys.exit(-4)
    else:
        # You can uncomment the commented-out code piece below, if your security policies allow.
        print "Unexpected response received."  # + " Response was: " + str(req)
        sys.exit(-4)


def get_opsgenie_api_key():
    if GET_CREDENTIALS_FROM_S3:
        return read_file_from_s3(s3_client, S3_OPSGENIE_API_KEY_BUCKET, S3_OPSGENIE_API_KEY_FILE)
    else:
        return os.environ["OPSGENIE_API_KEY"]


def get_slack_token():
    if GET_CREDENTIALS_FROM_S3:
        return read_file_from_s3(s3_client, S3_SLACK_TOKEN_BUCKET, S3_SLACK_TOKEN_FILE)
    else:
        return os.environ["SLACK_API_TOKEN"]


def get_base_opsgenie_headers():
    return {
        "Authorization": "GenieKey " + get_opsgenie_api_key()
    }


def get_base_slack_headers():
    return {
        "Authorization": "Bearer " + get_slack_token()
    }


def print_request_error_and_exit(req, message, exit_status):
    print message
    print "Status Code: " + str(req.status_code)
    print "Raw Response: " + str(req.content)
    sys.exit(exit_status)


def handle_slack_get_response(req, to_be_returned):
    if 200 <= req.status_code < 400:
        resp = req.json()

        if "ok" in resp and resp["ok"] is True and to_be_returned in resp:
            return resp[to_be_returned]
        else:
            print_request_error_and_exit(req, "Could not retrieve " + to_be_returned + " from Slack.", -2)
    else:
        print_request_error_and_exit(req, "Could not retrieve " + to_be_returned + " from Slack.", -2)


def retrieve_oncall_users(schedule_name):
    url_params = {
        "scheduleIdentifierType": "name",
        "flat": "true"
    }

    req = requests.get(OPSGENIE_SCHEDULES_ENDPOINT + "/" + schedule_name + "/" + OPSGENIE_WHO_IS_ONCALL_POSTFIX,
                       params=url_params, headers=get_base_opsgenie_headers())

    if 200 <= req.status_code < 400:
        resp = req.json()
        return resp["data"]["onCallRecipients"]
    else:
        print_request_error_and_exit(req, "Could not retrieve on-call people from OpsGenie for schedule ["
                                     + schedule_name + "].", -1)


def retrieve_slack_groups():
    req = requests.get(SLACK_USERGROUPS_ENDPOINT + ".list", headers=get_base_slack_headers())
    return handle_slack_get_response(req, "usergroups")


def get_slack_group_id(groups_list, group_name):
    wanted_group = filter(lambda x: x["name"] == group_name, groups_list)

    if len(wanted_group) > 0:
        return wanted_group[0]["id"]
    else:
        return ""


def update_slack_group(group_id, user_ids):
    payload = {
        "usergroup": group_id,
        "users": ",".join(user_ids),
        "include_count": True
    }

    req = requests.post(SLACK_USERGROUPS_ENDPOINT + ".users.update", json=payload, headers=get_base_slack_headers())

    if 200 <= req.status_code < 400:
        resp = req.json()

        if "ok" in resp and resp["ok"] is True and "usergroup" in resp and "user_count" in resp["usergroup"] \
                and resp["usergroup"]["user_count"] == 1:
            print "Successfully updated the Slack group [" + group_id + "] with the users [" + ", ".join(user_ids) \
                  + "]. "
        else:
            print_request_error_and_exit(req,
                    "Could not update the Slack group [" + group_id + "] with the users ["
                    + ", ".join(user_ids) + "]. ", -3)

    else:
        print_request_error_and_exit(req,
                                     "Could not update the Slack group [" + group_id + "] with the users ["
                                     + ", ".join(user_ids) + "]. ", -3)


def retrieve_slack_user_by_email(user_email):
    url_params = {
        "email": user_email
    }

    req = requests.get(SLACK_USERS_ENDPOINT + ".lookupByEmail", params=url_params, headers=get_base_slack_headers())
    return handle_slack_get_response(req, "user")


def lambda_handler(event, context):
    on_call_users = retrieve_oncall_users(OPSGENIE_SCHEDULE_NAME)

    if len(on_call_users) > 0:
        slack_user_id = retrieve_slack_user_by_email(on_call_users[0])["id"]
        slack_group_id = get_slack_group_id(retrieve_slack_groups(), SLACK_GROUP_NAME)
        update_slack_group(slack_group_id, [slack_user_id])
    else:
        print "No person is on-call right now for the schedule [" + OPSGENIE_SCHEDULE_NAME + "]. " \
              + "Quitting without updating the Slack group [" + SLACK_GROUP_NAME + "]."
        sys.exit(0)
