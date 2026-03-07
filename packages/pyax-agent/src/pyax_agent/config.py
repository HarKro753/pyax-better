"""Agent configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for the pyax agent server.

    All values come from environment variables with sensible defaults.
    The Claude Agent SDK handles authentication via Claude Code CLI's
    own auth (~/.claude directory), so no API key is needed.
    """

    model: str = "claude-sonnet-4-20250514"
    max_turns: int = 20
    request_timeout: float = 120.0
    bridge_url: str = "ws://localhost:8765"
    agent_port: int = 8766
    memory_dir: str = ""
    auto_context: bool = True
    permission_mode: str = "bypassPermissions"

    def validate(self) -> list[str]:
        """Return a list of validation errors. Empty list means valid."""
        errors: list[str] = []
        if self.max_turns < 1:
            errors.append("max_turns must be at least 1")
        if self.request_timeout <= 0:
            errors.append("request_timeout must be positive")
        if self.agent_port < 1 or self.agent_port > 65535:
            errors.append("agent_port must be between 1 and 65535")
        valid_modes = ("default", "acceptEdits", "plan", "bypassPermissions")
        if self.permission_mode not in valid_modes:
            errors.append(f"permission_mode must be one of {valid_modes}")
        return errors


def get_config() -> AgentConfig:
    """Build an AgentConfig from environment variables."""
    return AgentConfig(
        model=os.environ.get("PYAX_MODEL", "claude-sonnet-4-20250514"),
        max_turns=int(os.environ.get("PYAX_MAX_TURNS", "20")),
        request_timeout=float(os.environ.get("PYAX_REQUEST_TIMEOUT", "120.0")),
        bridge_url=os.environ.get("PYAX_BRIDGE_URL", "ws://localhost:8765"),
        agent_port=int(os.environ.get("PYAX_AGENT_PORT", "8766")),
        memory_dir=os.environ.get("PYAX_MEMORY_DIR", ""),
        auto_context=os.environ.get("PYAX_AUTO_CONTEXT", "true").lower() in ("true", "1", "yes"),
        permission_mode=os.environ.get("PYAX_PERMISSION_MODE", "bypassPermissions"),
    )
