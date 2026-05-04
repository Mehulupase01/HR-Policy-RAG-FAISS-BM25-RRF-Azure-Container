"""Azure Blob Storage persistence for local retrieval artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from app.ingest.indexer import BM25_INDEX, EMBEDDINGS_PARQUET, FAISS_INDEX


INDEX_FILES = (EMBEDDINGS_PARQUET, FAISS_INDEX, BM25_INDEX)


class BlobIndexStore:
    """Upload and download retrieval index artifacts from Azure Blob Storage."""

    def __init__(
        self,
        storage_account_url: str,
        container_name: str,
        *,
        container_client: Any | None = None,
    ) -> None:
        if container_client is not None:
            self.container_client = container_client
            return

        # DefaultAzureCredential supports local development credentials such as Azure CLI,
        # and managed identity in Azure-hosted apps including Container Apps:
        # https://learn.microsoft.com/en-us/azure/developer/python/sdk/authentication/user-assigned-managed-identity
        # https://learn.microsoft.com/en-us/azure/container-apps/managed-identity
        credential = DefaultAzureCredential()
        service_client = BlobServiceClient(
            account_url=storage_account_url,
            credential=credential,
        )
        self.container_client = service_client.get_container_client(container_name)

    def upload_index(self, local_dir: Path | str, prefix: str) -> None:
        local_path = Path(local_dir)
        for filename in INDEX_FILES:
            blob_name = _blob_name(prefix, filename)
            with (local_path / filename).open("rb") as file:
                self.container_client.upload_blob(
                    name=blob_name,
                    data=file,
                    overwrite=True,
                )

    def download_index(self, local_dir: Path | str, prefix: str) -> None:
        local_path = Path(local_dir)
        local_path.mkdir(parents=True, exist_ok=True)
        for filename in INDEX_FILES:
            blob_name = _blob_name(prefix, filename)
            data = self.container_client.download_blob(blob_name).readall()
            (local_path / filename).write_bytes(data)

    def index_exists(self, prefix: str) -> bool:
        return all(
            self.container_client.get_blob_client(_blob_name(prefix, filename)).exists()
            for filename in INDEX_FILES
        )


def _blob_name(prefix: str, filename: str) -> str:
    cleaned_prefix = prefix.strip("/")
    return f"{cleaned_prefix}/{filename}" if cleaned_prefix else filename
