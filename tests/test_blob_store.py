from __future__ import annotations

from pathlib import Path

from app.ingest.blob_store import BlobIndexStore
from app.ingest.indexer import BM25_INDEX, EMBEDDINGS_PARQUET, FAISS_INDEX


class FakeDownloader:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def readall(self) -> bytes:
        return self.data


class FakeBlobClient:
    def __init__(self, exists: bool) -> None:
        self._exists = exists

    def exists(self) -> bool:
        return self._exists


class FakeContainerClient:
    def __init__(self) -> None:
        self.uploads: dict[str, bytes] = {}
        self.existing: set[str] = set()

    def upload_blob(self, *, name: str, data, overwrite: bool) -> None:  # object from Azure SDK
        assert overwrite is True
        self.uploads[name] = data.read()
        self.existing.add(name)

    def download_blob(self, name: str) -> FakeDownloader:
        return FakeDownloader(self.uploads[name])

    def get_blob_client(self, name: str) -> FakeBlobClient:
        return FakeBlobClient(name in self.existing)


def write_artifacts(path: Path) -> None:
    path.mkdir(parents=True)
    (path / EMBEDDINGS_PARQUET).write_bytes(b"parquet")
    (path / FAISS_INDEX).write_bytes(b"faiss")
    (path / BM25_INDEX).write_bytes(b"bm25")


def test_blob_index_store_upload_download_and_exists(tmp_path: Path) -> None:
    local_dir = tmp_path / "local"
    download_dir = tmp_path / "download"
    write_artifacts(local_dir)
    fake_container = FakeContainerClient()
    store = BlobIndexStore(
        "https://example.blob.core.windows.net",
        "rag-index",
        container_client=fake_container,
    )

    assert store.index_exists("phase6") is False

    store.upload_index(local_dir, "phase6")

    assert sorted(fake_container.uploads) == [
        f"phase6/{BM25_INDEX}",
        f"phase6/{EMBEDDINGS_PARQUET}",
        f"phase6/{FAISS_INDEX}",
    ]
    assert store.index_exists("phase6") is True

    store.download_index(download_dir, "phase6")

    assert (download_dir / EMBEDDINGS_PARQUET).read_bytes() == b"parquet"
    assert (download_dir / FAISS_INDEX).read_bytes() == b"faiss"
    assert (download_dir / BM25_INDEX).read_bytes() == b"bm25"
