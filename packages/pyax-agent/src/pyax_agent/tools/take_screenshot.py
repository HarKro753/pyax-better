"""Take screenshot tool — capture screen for visual analysis.

Uses macOS screencapture CLI to capture the screen and returns the
image as base64 for Claude to analyze (multimodal).
"""

import base64
import json
import logging
import subprocess
import tempfile
from pathlib import Path

from claude_agent_sdk import tool

logger = logging.getLogger(__name__)


def create_take_screenshot():
    """Create a take_screenshot tool (no bridge or emitter needed)."""

    @tool(
        "take_screenshot",
        "Capture a screenshot of the screen for visual analysis. "
        "Optionally specify a region with x, y, width, height to capture "
        "only a portion of the screen. Returns the image for Claude to analyze.",
        {"region": dict},
    )
    async def take_screenshot(args: dict) -> dict:
        region = args.get("region")

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            # Build screencapture command
            cmd = ["screencapture", "-x"]  # -x = no sound

            if region:
                x = region.get("x", 0)
                y = region.get("y", 0)
                w = region.get("width", 800)
                h = region.get("height", 600)
                cmd.extend(["-R", f"{x},{y},{w},{h}"])

            cmd.append(tmp_path)

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
            )

            if result.returncode != 0:
                error_msg = result.stderr.decode("utf-8", errors="replace")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"error": f"screencapture failed: {error_msg}"}),
                        }
                    ]
                }

            # Read and encode the image
            image_data = Path(tmp_path).read_bytes()
            b64_data = base64.b64encode(image_data).decode("utf-8")

            return {
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64_data,
                        },
                    }
                ]
            }

        except subprocess.TimeoutExpired:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": "Screenshot capture timed out"}),
                    }
                ]
            }
        except Exception as e:
            logger.error("Screenshot error: %s", e)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": f"Screenshot failed: {e}"}),
                    }
                ]
            }
        finally:
            # Clean up temp file
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    return take_screenshot
