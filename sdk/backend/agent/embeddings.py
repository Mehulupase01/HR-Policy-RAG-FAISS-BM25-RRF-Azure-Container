"""Azure OpenAI embeddings helper.

Environment variables (checked in order):
  - EMBEDDINGS_MODEL_ENDPOINT / AZURE_OPENAI_ENDPOINT
  - EMBEDDINGS_MODEL_NAME     / AZURE_OPENAI_EMBED_MODEL
  - EMBEDDINGS_MODEL_API_KEY  / AZURE_OPENAI_API_KEY
  - EMBEDDINGS_API_VERSION    (optional, default 2023-05-15)
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import List


class EmbeddingError(RuntimeError):
    pass


def azure_embed_text(text: str) -> List[float]:
    """Call Azure OpenAI embeddings endpoint and return the vector."""
    raw_endpoint = os.getenv("EMBEDDINGS_MODEL_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
    endpoint = raw_endpoint
    if raw_endpoint and "/openai/deployments/" in raw_endpoint:
        endpoint = raw_endpoint.split("/openai/deployments/")[0]

    deployment = os.getenv("EMBEDDINGS_MODEL_NAME") or os.getenv("AZURE_OPENAI_EMBED_MODEL")
    api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("EMBEDDINGS_MODEL_API_KEY")
    api_version = os.getenv("EMBEDDINGS_API_VERSION") or "2023-05-15"

    if not endpoint or not deployment or not api_key:
        raise EmbeddingError("Azure OpenAI embedding environment not configured")

    url = f"{endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}"
    payload = json.dumps({"input": text}).encode()

    req = urllib.request.Request(
        url=url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "api-key": api_key},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            return data["data"][0]["embedding"]
    except Exception as exc:
        raise EmbeddingError(f"Failed to get embeddings: {exc}") from exc
