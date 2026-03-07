"""Save workflow tool — save a named workflow to workspace memory.

Appends a named workflow (with numbered steps) to the
"## Saved Workflows" section of WORKSPACE.md.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.memory import MemoryManager

logger = logging.getLogger(__name__)


def create_save_workflow(memory_manager: MemoryManager):
    """Create a save_workflow tool with the memory manager captured in closure."""

    @tool(
        "save_workflow",
        "Save a named workflow so it can be replayed later. "
        "Provide a name for the workflow and a list of step descriptions. "
        "The workflow is saved to workspace memory for future reference.",
        {"name": str, "steps": list},
    )
    async def save_workflow(args: dict) -> dict:
        name = args.get("name", "")
        steps = args.get("steps", [])

        if not name:
            result = json.dumps({"error": "name parameter is required"})
            return {"content": [{"type": "text", "text": result}]}

        if not steps:
            result = json.dumps(
                {"error": "steps parameter is required (list of step descriptions)"}
            )
            return {"content": [{"type": "text", "text": result}]}

        # Format the workflow as markdown
        lines = [f"### {name}", ""]
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")

        workflow_text = "\n".join(lines)

        success = memory_manager.append_to_section("workspace", "## Saved Workflows", workflow_text)
        if success:
            result = json.dumps(
                {
                    "success": True,
                    "workflow": name,
                    "step_count": len(steps),
                }
            )
        else:
            result = json.dumps({"error": f"Failed to save workflow {name!r}"})

        return {"content": [{"type": "text", "text": result}]}

    return save_workflow
