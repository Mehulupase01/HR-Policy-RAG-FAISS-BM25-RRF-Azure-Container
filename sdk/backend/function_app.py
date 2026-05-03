"""Azure Functions entry point.

Replace or extend the HTTP triggers below with your project-specific endpoints.
"""

from __future__ import annotations

import json
import logging
import os

import azure.functions as func
from dotenv import load_dotenv

load_dotenv()

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

logger = logging.getLogger("app")


# ── Health check ─────────────────────────────────────────────────────────────

@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(json.dumps({"status": "ok"}), mimetype="application/json")


# ── Chat endpoint (placeholder) ─────────────────────────────────────────────

@app.route(route="chat", methods=["POST"])
def chat(req: func.HttpRequest) -> func.HttpResponse:
    """Placeholder RAG chat endpoint.

    Expected JSON body::

        { "chat_id": "...", "owner_id": "...", "question": "..." }

    Returns::

        { "reply": "...", "sources": [] }
    """
    auth = req.headers.get("Authorization", "")
    if not auth:
        return _error_response("Unauthorized", "Missing Authorization header.", 401)

    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Bad Request", "Invalid JSON body.", 400)

    question = body.get("question", "").strip()
    if not question:
        return _error_response("Bad Request", "Field 'question' is required.", 400)

    # TODO: Wire up the real RAG agent here.
    # from agent.rag_agent import generate_reply
    reply = f"[placeholder] You asked: {question}"

    return func.HttpResponse(
        json.dumps({"reply": reply, "sources": []}),
        mimetype="application/json",
        status_code=200,
    )


# ── File management endpoints (placeholder) ─────────────────────────────────

@app.route(route="files", methods=["GET"])
def list_files(req: func.HttpRequest) -> func.HttpResponse:
    """List files in blob storage."""
    # TODO: Wire up blob_client.list_files()
    return func.HttpResponse(json.dumps({"files": []}), mimetype="application/json")


@app.route(route="files", methods=["POST"])
def upload_file(req: func.HttpRequest) -> func.HttpResponse:
    """Upload a file to blob storage with validation."""
    # TODO: Wire up blob_client upload + validation
    return _error_response("Not Implemented", "File upload not yet wired.", 501)


@app.route(route="files/{blob_name}", methods=["DELETE"])
def delete_file(req: func.HttpRequest) -> func.HttpResponse:
    """Delete a file from blob storage."""
    # TODO: Wire up blob_client delete
    return _error_response("Not Implemented", "File delete not yet wired.", 501)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _error_response(title: str, detail: str, status: int) -> func.HttpResponse:
    """Return a problem-details JSON error response."""
    return func.HttpResponse(
        json.dumps({"title": title, "detail": detail, "status": status}),
        mimetype="application/json",
        status_code=status,
    )
