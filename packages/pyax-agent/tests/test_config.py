"""Tests for agent configuration."""

import os
from unittest.mock import patch

from pyax_agent.config import AgentConfig, get_config


class TestAgentConfig:
    """Tests for the AgentConfig dataclass."""

    def test_default_values(self):
        config = AgentConfig()
        assert config.model == "claude-sonnet-4-20250514"
        assert config.max_tokens == 4096
        assert config.max_turns == 20
        assert config.request_timeout == 120.0
        assert config.bridge_url == "ws://localhost:8765"
        assert config.agent_port == 8766
        assert config.memory_dir == ""
        assert config.auto_context is True

    def test_custom_values(self):
        config = AgentConfig(
            model="claude-haiku-20240307",
            max_tokens=2048,
            max_turns=10,
            request_timeout=60.0,
            bridge_url="ws://localhost:9999",
            agent_port=9000,
            memory_dir="/tmp/memory",
            auto_context=False,
        )
        assert config.model == "claude-haiku-20240307"
        assert config.max_tokens == 2048
        assert config.max_turns == 10
        assert config.request_timeout == 60.0
        assert config.bridge_url == "ws://localhost:9999"
        assert config.agent_port == 9000
        assert config.memory_dir == "/tmp/memory"
        assert config.auto_context is False

    def test_frozen(self):
        config = AgentConfig()
        try:
            config.model = "new-model"  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass  # Expected for frozen dataclass


class TestConfigValidation:
    """Tests for config validation."""

    def test_valid_config(self):
        config = AgentConfig()
        assert config.validate() == []

    def test_invalid_max_turns(self):
        config = AgentConfig(max_turns=0)
        errors = config.validate()
        assert any("max_turns" in e for e in errors)

    def test_invalid_max_tokens(self):
        config = AgentConfig(max_tokens=0)
        errors = config.validate()
        assert any("max_tokens" in e for e in errors)

    def test_invalid_timeout(self):
        config = AgentConfig(request_timeout=0)
        errors = config.validate()
        assert any("request_timeout" in e for e in errors)

    def test_invalid_port_too_low(self):
        config = AgentConfig(agent_port=0)
        errors = config.validate()
        assert any("agent_port" in e for e in errors)

    def test_invalid_port_too_high(self):
        config = AgentConfig(agent_port=70000)
        errors = config.validate()
        assert any("agent_port" in e for e in errors)

    def test_multiple_errors(self):
        config = AgentConfig(max_turns=0, max_tokens=-1)
        errors = config.validate()
        assert len(errors) >= 2  # max_turns + max_tokens


class TestGetConfig:
    """Tests for loading config from environment."""

    def test_defaults_from_env(self):
        with patch.dict(os.environ, {}, clear=True):
            config = get_config()
        assert config.model == "claude-sonnet-4-20250514"
        assert config.agent_port == 8766

    def test_custom_env(self):
        env = {
            "PYAX_MODEL": "claude-opus-4-20250514",
            "PYAX_MAX_TOKENS": "8192",
            "PYAX_MAX_TURNS": "30",
            "PYAX_REQUEST_TIMEOUT": "60.0",
            "PYAX_BRIDGE_URL": "ws://localhost:1234",
            "PYAX_AGENT_PORT": "9999",
            "PYAX_MEMORY_DIR": "/tmp/mem",
            "PYAX_AUTO_CONTEXT": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            config = get_config()
        assert config.model == "claude-opus-4-20250514"
        assert config.max_tokens == 8192
        assert config.max_turns == 30
        assert config.request_timeout == 60.0
        assert config.bridge_url == "ws://localhost:1234"
        assert config.agent_port == 9999
        assert config.memory_dir == "/tmp/mem"
        assert config.auto_context is False

    def test_auto_context_variants(self):
        for val, expected in [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
            ("no", False),
        ]:
            with patch.dict(os.environ, {"PYAX_AUTO_CONTEXT": val}, clear=True):
                config = get_config()
            assert config.auto_context is expected, f"Failed for {val!r}"
