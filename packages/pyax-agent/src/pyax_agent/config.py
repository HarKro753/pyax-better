"""Agent configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for the pyax agent server.

    All values come from environment variables with sensible defaults.
    The Anthropic SDK reads ANTHROPIC_API_KEY from the environment automatically,
    so we don't need to manage it here.
    """

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    max_turns: int = 20
    request_timeout: float = 120.0
    bridge_url: str = "ws://localhost:8765"
    agent_port: int = 8766
    memory_dir: str = ""
    auto_context: bool = True

    def validate(self) -> list[str]:
        """Return a list of validation errors. Empty list means valid."""
        errors: list[str] = []
        if self.max_turns < 1:
            errors.append("max_turns must be at least 1")
        if self.max_tokens < 1:
            errors.append("max_tokens must be at least 1")
        if self.request_timeout <= 0:
            errors.append("request_timeout must be positive")
        if self.agent_port < 1 or self.agent_port > 65535:
            errors.append("agent_port must be between 1 and 65535")
        return errors


def get_config() -> AgentConfig:
    """Build an AgentConfig from environment variables."""
    return AgentConfig(
        model=os.environ.get("PYAX_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=int(os.environ.get("PYAX_MAX_TOKENS", "4096")),
        max_turns=int(os.environ.get("PYAX_MAX_TURNS", "20")),
        request_timeout=float(os.environ.get("PYAX_REQUEST_TIMEOUT", "120.0")),
        bridge_url=os.environ.get("PYAX_BRIDGE_URL", "ws://localhost:8765"),
        agent_port=int(os.environ.get("PYAX_AGENT_PORT", "8766")),
        memory_dir=os.environ.get("PYAX_MEMORY_DIR", ""),
        auto_context=os.environ.get("PYAX_AUTO_CONTEXT", "true").lower() in ("true", "1", "yes"),
    )
