"""Thin wrapper around Azure Blob Storage SDK."""

from __future__ import annotations

import logging
from typing import List, Optional

from azure.storage.blob import BlobServiceClient, ContainerClient

logger = logging.getLogger(__name__)


class BlobStorageClient:
    """Manage files in a single Azure Blob Storage container."""

    def __init__(self, connection_string: str, container_name: str):
        self._service_client = BlobServiceClient.from_connection_string(connection_string)
        self._container_client: ContainerClient = self._service_client.get_container_client(container_name)
        # Create the container if it doesn't exist
        try:
            self._container_client.get_container_properties()
        except Exception:
            self._container_client.create_container()
            logger.info("Created container: %s", container_name)

    def list_files(self) -> List:
        """Return a list of blob properties in the container."""
        return list(self._container_client.list_blobs())

    def upload(self, blob_name: str, data: bytes, content_type: Optional[str] = None) -> None:
        """Upload bytes to a blob, overwriting if it exists."""
        blob_client = self._container_client.get_blob_client(blob_name)
        blob_client.upload_blob(data, overwrite=True, content_settings={"content_type": content_type})
        logger.info("Uploaded: %s", blob_name)

    def download(self, blob_name: str) -> bytes:
        """Download a blob and return its content as bytes."""
        blob_client = self._container_client.get_blob_client(blob_name)
        return blob_client.download_blob().readall()

    def delete(self, blob_name: str) -> None:
        """Delete a blob."""
        blob_client = self._container_client.get_blob_client(blob_name)
        blob_client.delete_blob()
        logger.info("Deleted: %s", blob_name)
