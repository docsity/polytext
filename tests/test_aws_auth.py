import os
import unittest
from unittest.mock import Mock, patch

from polytext.loader.base import BaseLoader


AWS_AUTH_ENV_VARS = [
    "POLYTEXT_AWS_AUTH_MODE",
    "AWS_ROLE_ARN",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_ROLE_SESSION_NAME",
    "GCP_ID_TOKEN_AUDIENCE",
    "AWS_STS_DURATION_SECONDS",
]


def _without_aws_auth_env():
    return patch.dict(os.environ, {name: "" for name in AWS_AUTH_ENV_VARS})


class TestAwsAuth(unittest.TestCase):
    def test_default_s3_auth_uses_boto3_credential_chain(self):
        from polytext.loader.aws_auth import create_s3_client

        fake_boto3 = Mock()
        fake_s3_client = Mock()
        fake_boto3.client.return_value = fake_s3_client

        with _without_aws_auth_env():
            result = create_s3_client(boto3_module=fake_boto3)

        self.assertIs(result, fake_s3_client)
        fake_boto3.client.assert_called_once_with("s3")

    def test_sts_web_identity_builds_s3_client_with_temporary_credentials_without_mutating_env(self):
        from polytext.loader.aws_auth import create_s3_client

        original_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        fake_sts_client = Mock()
        fake_sts_client.assume_role_with_web_identity.return_value = {
            "Credentials": {
                "AccessKeyId": "temporary-access-key",
                "SecretAccessKey": "temporary-secret",
                "SessionToken": "temporary-session-token",
            }
        }
        fake_s3_client = Mock()

        fake_boto3 = Mock()
        fake_boto3.client.side_effect = [fake_sts_client, fake_s3_client]

        with patch("polytext.loader.aws_auth.google_id_token.fetch_id_token", return_value="jwt-token"):
            result = create_s3_client(
                auth_mode="sts_web_identity",
                role_arn="arn:aws:iam::111122223333:role/ExampleCrossAccountRole",
                web_identity_token_audience="example-gcp-audience",
                region_name="eu-central-1",
                role_session_name="polytext-test-session",
                duration_seconds=900,
                boto3_module=fake_boto3,
            )

        self.assertIs(result, fake_s3_client)
        fake_boto3.client.assert_any_call("sts", region_name="eu-central-1")
        fake_sts_client.assume_role_with_web_identity.assert_called_once_with(
            RoleArn="arn:aws:iam::111122223333:role/ExampleCrossAccountRole",
            RoleSessionName="polytext-test-session",
            WebIdentityToken="jwt-token",
            DurationSeconds=900,
        )
        fake_boto3.client.assert_any_call(
            "s3",
            aws_access_key_id="temporary-access-key",
            aws_secret_access_key="temporary-secret",
            aws_session_token="temporary-session-token",
            region_name="eu-central-1",
        )
        self.assertEqual(os.environ.get("AWS_ACCESS_KEY_ID"), original_access_key)

    def test_base_loader_default_s3_auth_is_opt_in_only(self):
        loader = BaseLoader()
        fake_s3_client = Mock()

        with _without_aws_auth_env():
            with patch("polytext.loader.base.create_s3_client", return_value=fake_s3_client) as create_s3_client:
                storage = loader.initiate_storage("s3://example-bucket/uploads/image/example.jpg")

        self.assertIs(storage["s3_client"], fake_s3_client)
        self.assertEqual(storage["document_aws_bucket"], "example-bucket")
        self.assertEqual(storage["file_path"], "uploads/image/example.jpg")
        create_s3_client.assert_called_once_with(
            auth_mode=None,
            role_arn=None,
            region_name=None,
            role_session_name=None,
            web_identity_token_audience=None,
            duration_seconds=None,
        )

    def test_env_can_opt_in_to_sts_web_identity(self):
        loader = BaseLoader()
        fake_s3_client = Mock()

        with patch.dict(
            os.environ,
            {
                "POLYTEXT_AWS_AUTH_MODE": "sts_web_identity",
                "AWS_ROLE_ARN": "arn:aws:iam::111122223333:role/ExampleCrossAccountRole",
                "AWS_REGION": "eu-central-1",
                "AWS_ROLE_SESSION_NAME": "polytext-env-session",
                "GCP_ID_TOKEN_AUDIENCE": "example-gcp-audience",
            },
        ):
            with patch("polytext.loader.base.create_s3_client", return_value=fake_s3_client) as create_s3_client:
                storage = loader.initiate_storage("s3://example-bucket/uploads/image/example.jpg")

        self.assertIs(storage["s3_client"], fake_s3_client)
        create_s3_client.assert_called_once_with(
            auth_mode=None,
            role_arn=None,
            region_name=None,
            role_session_name=None,
            web_identity_token_audience=None,
            duration_seconds=None,
        )

    def test_create_s3_client_uses_env_sts_web_identity(self):
        from polytext.loader.aws_auth import create_s3_client

        fake_sts_client = Mock()
        fake_sts_client.assume_role_with_web_identity.return_value = {
            "Credentials": {
                "AccessKeyId": "env-access-key",
                "SecretAccessKey": "env-secret",
                "SessionToken": "env-session-token",
            }
        }
        fake_s3_client = Mock()
        fake_boto3 = Mock()
        fake_boto3.client.side_effect = [fake_sts_client, fake_s3_client]

        with patch.dict(
            os.environ,
            {
                "POLYTEXT_AWS_AUTH_MODE": "sts_web_identity",
                "AWS_ROLE_ARN": "arn:aws:iam::111122223333:role/ExampleCrossAccountRole",
                "AWS_REGION": "eu-central-1",
                "AWS_ROLE_SESSION_NAME": "polytext-env-session",
                "GCP_ID_TOKEN_AUDIENCE": "example-gcp-audience",
            },
        ):
            with patch("polytext.loader.aws_auth.google_id_token.fetch_id_token", return_value="env-jwt-token"):
                result = create_s3_client(boto3_module=fake_boto3)

        self.assertIs(result, fake_s3_client)
        fake_sts_client.assume_role_with_web_identity.assert_called_once_with(
            RoleArn="arn:aws:iam::111122223333:role/ExampleCrossAccountRole",
            RoleSessionName="polytext-env-session",
            WebIdentityToken="env-jwt-token",
            DurationSeconds=3600,
        )

    def test_base_loader_uses_configured_aws_auth_for_s3_urls(self):
        loader = BaseLoader(
            aws_auth_mode="sts_web_identity",
            aws_role_arn="arn:aws:iam::111122223333:role/ExampleCrossAccountRole",
            aws_region="eu-central-1",
            aws_role_session_name="polytext-session",
            gcp_id_token_audience="example-gcp-audience",
            aws_sts_duration_seconds=900,
        )
        fake_s3_client = Mock()

        with patch("polytext.loader.base.create_s3_client", return_value=fake_s3_client) as create_s3_client:
            storage = loader.initiate_storage("s3://example-bucket/uploads/image/example.jpg")

        self.assertIs(storage["s3_client"], fake_s3_client)
        self.assertEqual(storage["document_aws_bucket"], "example-bucket")
        self.assertEqual(storage["file_path"], "uploads/image/example.jpg")
        create_s3_client.assert_called_once_with(
            auth_mode="sts_web_identity",
            role_arn="arn:aws:iam::111122223333:role/ExampleCrossAccountRole",
            region_name="eu-central-1",
            role_session_name="polytext-session",
            web_identity_token_audience="example-gcp-audience",
            duration_seconds=900,
        )


if __name__ == "__main__":
    unittest.main()
