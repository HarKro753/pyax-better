"""Entry point for pyax-agent server."""

import uvicorn

from pyax_agent.config import get_config


def main() -> None:
    """Start the pyax-agent HTTP server."""
    config = get_config()
    uvicorn.run(
        "pyax_agent.server:app",
        host="127.0.0.1",
        port=config.agent_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
