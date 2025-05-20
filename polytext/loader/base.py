# Standard library imports
import os
import tempfile
import logging

import boto3
import requests

# Local imports
from ..converter import md_to_text, html_to_md

# External imports
from retry import retry

logger = logging.getLogger(__name__)


class BaseLoader:

    def get_text(self, input: str, markdown_output: bool = True, fallback_ocr: bool = True,
                  provider: str = "google", llm_api_key: str = None, **kwargs):
        storage_client = self.initiate_storage(input=input)
        loader_class = self.init_loader_class(input=input, storage_client=storage_client)
        return self.run_loader_class(loader_class=loader_class, input=input, markdown_output=markdown_output,
                            fallback_ocr=fallback_ocr, provider=provider, llm_api_key=llm_api_key, **kwargs)


    def initiate_storage(self, input) -> object:
        if input.startswith("s3://"):
            return # s3_client
        elif input.startswith("gcs://"):
            return # gcs_client
        elif input.startswith("http://") or input.startswith("https://") or input.startswith("www.") or input.startswith("www.youtube"):
            return object()
        else:
            raise NotImplementedError
    def init_loader_class(self, input: str, storage_client: object) -> object:
        return # output from loader class launched

    def run_loader_class(self, loader_class: object, input: str, markdown_output: bool = True, fallback_ocr: bool = True,
                         provider: str = "google", llm_api_key: str = None, **kwargs ) -> dict:
        return # output from loader class launched