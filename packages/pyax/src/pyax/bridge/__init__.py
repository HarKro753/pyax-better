"""
pyax.bridge — WebSocket server that streams accessibility events.

Usage:
    python3 -m pyax.bridge

This module provides a WebSocket bridge that auto-detects the focused
macOS application and streams its accessibility events as JSON.
"""

from pyax.bridge.server import run as main

__all__ = ["main"]
