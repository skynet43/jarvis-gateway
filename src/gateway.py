"""Jarvis Gateway local API for CodexOS.

This service is intentionally bound to 127.0.0.1 by default. Do not expose it
publicly unless that is an intentional, reviewed change.
"""

from __future__ import annotations

from typing import Any

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

HOST = "127.0.0.1"
PORT = 8765
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"
REQUEST_TIMEOUT_SECONDS = 120

app = FastAPI(
    title="Jarvis Gateway",
    description="Local AI control layer for CodexOS.",
    version="0.1.0",
)


class ChatMessage(BaseModel):
    """A single Ollama chat message."""

    role: str = Field(..., examples=["user"])
    content: str = Field(..., examples=["Hello from Jarvis Gateway."])


class ChatRequest(BaseModel):
    """Request body for /ollama/chat."""

    message: str | None = Field(default=None, description="Convenience user message.")
    messages: list[ChatMessage] | None = Field(
        default=None,
        description="Explicit Ollama chat messages. Used when provided.",
    )
    model: str = Field(default=DEFAULT_MODEL)
    stream: bool = Field(default=False)


@app.get("/")
def root() -> dict[str, Any]:
    """Return basic service information."""

    return {
        "service": "Jarvis Gateway",
        "purpose": "Local AI control layer for CodexOS",
        "host": HOST,
        "port": PORT,
        "ollama": OLLAMA_BASE_URL,
        "default_model": DEFAULT_MODEL,
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Return gateway health."""

    return {"status": "ok"}


@app.get("/ollama/models")
def ollama_models() -> dict[str, Any]:
    """List locally available Ollama models."""

    try:
        response = requests.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach Ollama at {OLLAMA_BASE_URL}: {exc}",
        ) from exc

    return response.json()


@app.post("/ollama/chat")
def ollama_chat(request: ChatRequest) -> dict[str, Any]:
    """Send a chat request to local Ollama."""

    messages = request.messages
    if messages is None:
        if not request.message:
            raise HTTPException(
                status_code=400,
                detail="Provide either 'message' or 'messages'.",
            )
        messages = [ChatMessage(role="user", content=request.message)]

    payload = {
        "model": request.model,
        "messages": [message.model_dump() for message in messages],
        "stream": request.stream,
    }

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama chat request failed: {exc}",
        ) from exc

    return response.json()


if __name__ == "__main__":
    uvicorn.run("gateway:app", host=HOST, port=PORT, reload=False)
