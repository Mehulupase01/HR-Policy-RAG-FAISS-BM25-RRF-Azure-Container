"""Azure OpenAI chat completion helper.

Environment variables:
  - AZURE_OPENAI_ENDPOINT
  - AZURE_OPENAI_CHAT_DEPLOYMENT
  - AZURE_OPENAI_API_KEY
  - AZURE_OPENAI_API_VERSION (optional, default 2024-05-01-preview)
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import List, Sequence

from agent.rag_agent import ChatMessage


class LLMError(RuntimeError):
    pass


SYSTEM_PROMPT = (
    "You are a helpful knowledge assistant. Answer questions based on the provided context. "
    "The context contains fragments from documents. Each fragment starts with '[Source: filename]' "
    "so you know which file the information comes from.\n\n"
    "RULES:\n"
    "1. If the context contains relevant information, use it to answer.\n"
    "2. Only say 'I don't have enough information' if the context truly contains nothing relevant.\n"
    "3. When parts of the question are not covered, say so explicitly but still share what you do have.\n"
    "4. Do NOT add a sources list at the end — sources are shown separately by the application."
)


def azure_chat_completion(
    question: str,
    context: str,
    history: Sequence[ChatMessage],
) -> str:
    """Call Azure OpenAI chat completion with context and history."""
    raw_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    endpoint = raw_endpoint
    if raw_endpoint and "/openai/" in raw_endpoint:
        endpoint = raw_endpoint.split("/openai/")[0]

    deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")

    if not endpoint or not deployment or not api_key:
        raise LLMError("Azure OpenAI chat environment not configured")

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    messages: List[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Context:\n{context}"},
    ]
    for msg in history:
        if msg.role in {"user", "assistant"}:
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})

    payload = json.dumps({"messages": messages, "temperature": 0.0}).encode()

    req = urllib.request.Request(
        url=url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "api-key": api_key},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LLMError(f"Chat completion failed: {exc}") from exc
