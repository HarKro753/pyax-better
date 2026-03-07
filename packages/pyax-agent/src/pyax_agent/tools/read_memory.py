"""Read memory tool — read contents of a memory file.

Allows the agent to read any of the three memory files:
soul, user, or workspace.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.memory import MEMORY_FILES, MemoryManager

logger = logging.getLogger(__name__)


def create_read_memory(memory_manager: MemoryManager):
    """Create a read_memory tool with the memory manager captured in closure."""

    @tool(
        "read_memory",
        "Read a memory file to recall stored information. "
        "Available files: 'soul' (agent identity), 'user' (user profile), "
        "'workspace' (app knowledge and saved workflows).",
        {"name": str},
    )
    async def read_memory(args: dict) -> dict:
        name = args.get("name", "")

        if name not in MEMORY_FILES:
            result = json.dumps(
                {
                    "error": f"Invalid memory file: {name!r}. Must be one of: {', '.join(MEMORY_FILES)}"
                }
            )
            return {"content": [{"type": "text", "text": result}]}

        content = memory_manager.read_file(name)
        if not content:
            result = json.dumps(
                {"name": name, "content": "", "note": "File is empty or does not exist"}
            )
        else:
            result = json.dumps({"name": name, "content": content})

        return {"content": [{"type": "text", "text": result}]}

    return read_memory
