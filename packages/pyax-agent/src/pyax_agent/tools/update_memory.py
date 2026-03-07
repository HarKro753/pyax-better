"""Update memory tool — update a section in a memory file.

Allows the agent to update sections in USER.md or WORKSPACE.md.
SOUL.md is read-only and cannot be modified.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.memory import WRITABLE_FILES, MemoryManager

logger = logging.getLogger(__name__)


def create_update_memory(memory_manager: MemoryManager):
    """Create an update_memory tool with the memory manager captured in closure."""

    @tool(
        "update_memory",
        "Update a section in a memory file to store information about the user "
        "or workspace. Only 'user' and 'workspace' files can be updated (not 'soul'). "
        "Section should be a markdown heading like '## Profile' or '## Disability'. "
        "If the section doesn't exist, it will be created.",
        {"name": str, "section": str, "content": str},
    )
    async def update_memory(args: dict) -> dict:
        name = args.get("name", "")
        section = args.get("section", "")
        content = args.get("content", "")

        if name not in WRITABLE_FILES:
            if name == "soul":
                result = json.dumps({"error": "Cannot modify soul memory — it is read-only"})
            else:
                result = json.dumps(
                    {
                        "error": f"Invalid memory file: {name!r}. Must be one of: {', '.join(WRITABLE_FILES)}"
                    }
                )
            return {"content": [{"type": "text", "text": result}]}

        if not section:
            result = json.dumps({"error": "section parameter is required"})
            return {"content": [{"type": "text", "text": result}]}

        if not content:
            result = json.dumps({"error": "content parameter is required"})
            return {"content": [{"type": "text", "text": result}]}

        success = memory_manager.update_section(name, section, content)
        if success:
            result = json.dumps({"success": True, "file": name, "section": section})
        else:
            result = json.dumps({"error": f"Failed to update section {section!r} in {name}"})

        return {"content": [{"type": "text", "text": result}]}

    return update_memory
