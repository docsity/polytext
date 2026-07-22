import os

import boto3
from google.auth.transport.requests import Request
from google.oauth2 import id_token as google_id_token


DEFAULT_AWS_AUTH_MODE = "default"
STS_WEB_IDENTITY_AUTH_MODE = "sts_web_identity"


def _first_value(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _client_kwargs(region_name):
    if region_name:
        return {"region_name": region_name}
    return {}


def create_s3_client(
    auth_mode=None,
    role_arn=None,
    region_name=None,
    role_session_name=None,
    web_identity_token_audience=None,
    duration_seconds=None,
    boto3_module=boto3,
):
    """
    Create an S3 client using either boto3 defaults or opt-in STS web identity.

    The STS branch intentionally does not export credentials to os.environ and
    does not reset boto3's global session, so Polytext does not affect callers.
    """
    resolved_auth_mode = _first_value(
        auth_mode,
        os.getenv("POLYTEXT_AWS_AUTH_MODE"),
        DEFAULT_AWS_AUTH_MODE,
    )
    default_region = region_name
    resolved_region = _first_value(
        region_name,
        os.getenv("AWS_REGION"),
        os.getenv("AWS_DEFAULT_REGION"),
    )

    if resolved_auth_mode in {DEFAULT_AWS_AUTH_MODE, "boto3"}:
        return boto3_module.client("s3", **_client_kwargs(default_region))

    if resolved_auth_mode != STS_WEB_IDENTITY_AUTH_MODE:
        raise ValueError(f"Unsupported AWS auth mode: {resolved_auth_mode}")

    resolved_role_arn = _first_value(role_arn, os.getenv("AWS_ROLE_ARN"))
    if not resolved_role_arn:
        raise ValueError("AWS role ARN is required for sts_web_identity auth mode")

    resolved_audience = _first_value(
        web_identity_token_audience,
        os.getenv("GCP_ID_TOKEN_AUDIENCE"),
    )
    if not resolved_audience:
        raise ValueError("GCP ID token audience is required for sts_web_identity auth mode")

    resolved_session_name = _first_value(
        role_session_name,
        os.getenv("AWS_ROLE_SESSION_NAME"),
        "polytext-sts-web-identity",
    )
    resolved_duration_seconds = int(
        _first_value(
            duration_seconds,
            os.getenv("AWS_STS_DURATION_SECONDS"),
            3600,
        )
    )

    web_identity_token = google_id_token.fetch_id_token(Request(), resolved_audience)
    sts_client = boto3_module.client("sts", **_client_kwargs(resolved_region))
    response = sts_client.assume_role_with_web_identity(
        RoleArn=resolved_role_arn,
        RoleSessionName=resolved_session_name,
        WebIdentityToken=web_identity_token,
        DurationSeconds=resolved_duration_seconds,
    )
    credentials = response["Credentials"]

    return boto3_module.client(
        "s3",
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        **_client_kwargs(resolved_region),
    )
