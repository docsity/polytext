import logging

logger = logging.getLogger(__name__)

class Downloader:

    def __init__(self, s3_client=None, document_aws_bucket=None, gcs_client=None, document_gcs_bucket=None):
        """
        Initialize Downloader with optional storage configuration.

        Args:
            s3_client: Boto3 S3 client instance for AWS operations (optional)
            document_aws_bucket (str): Default S3 bucket name for document storage (optional)
            PARAMETRI DI GCS
        """
        self.s3_client = s3_client
        self.document_aws_bucket = document_aws_bucket
        self.gcs_client = gcs_client
        self.document_gcs_bucket = document_gcs_bucket

    def download_file_from_s3(self, file_path, temp_file_path):
        """
        Download a file from S3 to a local temporary path.

        Attempts to download the file with both lowercase and uppercase extensions.
        Falls back to document conversion if direct download fails.

        Args:
            file_path (str): Path to file in S3 bucket
            temp_file_path (str): Local path to save the downloaded file
            source_type (str, optional): The type of the source file. Defaults to "document".
            If set to "document", the method attempts to convert the file to PDF if direct download fails.

        Returns:
            str: Path to the downloaded file (may be converted to PDF)

        Raises:
            ClientError: If S3 download operation fails
        """
        self.s3_client.download_file(Bucket=self.document_aws_bucket, Key=file_path, Filename=temp_file_path)
        logger.info(f'Downloaded {file_path} to {temp_file_path}')

        return temp_file_path

    def download_file_from_gcs(self, file_path, temp_file_path):
        """
        Download a file from Google Cloud Storage to a local temporary path.

        Args:
            file_path (str): Path to file in GCS bucket
            temp_file_path (str): Local path to save the downloaded file

        Returns:
            str: Path to the downloaded file

        Raises:
            Exception: If GCS download operation fails
        """

        try:
            # # Initialize GCS client
            # storage_client = storage.Client()
            #
            # Get bucket and blob
            bucket = self.gcs_client.bucket(self.document_gcs_bucket)
            blob = bucket.blob(file_path)

            # Download file
            blob.download_to_filename(temp_file_path)
            logger.info(f'Downloaded {file_path} to {temp_file_path}')

            return temp_file_path

        except Exception as e:
            logger.error(f"Failed to download file from GCS: {str(e)}")
            raise