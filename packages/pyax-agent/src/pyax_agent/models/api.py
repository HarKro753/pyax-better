"""API request/response models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    """A single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatRequest:
    """Request body for POST /chat."""

    message: str
    conversation_id: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> ChatRequest:
        return cls(
            message=data.get("message", ""),
            conversation_id=data.get("conversation_id", ""),
        )

    def validate(self) -> list[str]:
        """Return validation errors. Empty list means valid."""
        errors: list[str] = []
        if not self.message or not self.message.strip():
            errors.append("message is required and cannot be empty")
        return errors


@dataclass
class ErrorResponse:
    """Standard error response."""

    error: str
    status_code: int = 400

    def to_dict(self) -> dict:
        return {"error": self.error}
