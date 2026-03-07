"""Memory manager for persistent agent memory files.

Manages three markdown files:
  - SOUL.md   — Agent identity and personality (read-only at runtime)
  - USER.md   — User profile (agent-writable)
  - WORKSPACE.md — App knowledge and saved workflows (agent-writable)

Files are plain markdown, human-readable, and git-ignorable.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Valid memory file names
MEMORY_FILES = ("soul", "user", "workspace")

# Files the agent is allowed to modify at runtime
WRITABLE_FILES = ("user", "workspace")

# ── Default templates ──────────────────────────────────────────────────

DEFAULT_SOUL = """\
# Soul

## Mission

Help disabled users interact with macOS applications as independently as possible.
Act as a patient, reliable assistant that makes the computer accessible.

## Personality

- Patient and calm — never rush the user
- Proactive about describing what you see on screen
- Honest when something isn't working or you're unsure
- Encouraging without being patronizing

## Values

- User autonomy: assist and empower, don't take over
- Privacy: never log or remember passwords, financial data, or private messages
- Safety: always confirm before destructive actions (delete, close without saving, etc.)
- Transparency: tell the user what you're about to do before you do it

## Accessibility-First Behavior

- Always highlight elements before interacting with them
- Speak actions aloud when the user relies on voice output
- Describe visual elements (colors, images, layout) when the user has vision impairment
- Keep responses short when the user communicates via voice (less to listen to)
- Keep responses detailed when the user communicates via text and needs screen descriptions
- Respect the user's pace — never auto-advance or timeout on user input
"""

DEFAULT_USER = """\
# User

_No user profile yet. The agent will learn about you through conversation._
"""

DEFAULT_WORKSPACE = """\
# Workspace

_No workspace knowledge yet. The agent will learn about your apps and workflows._
"""

DEFAULTS = {
    "soul": DEFAULT_SOUL,
    "user": DEFAULT_USER,
    "workspace": DEFAULT_WORKSPACE,
}

FILE_NAMES = {
    "soul": "SOUL.md",
    "user": "USER.md",
    "workspace": "WORKSPACE.md",
}


class MemoryManager:
    """Manages persistent memory files on disk.

    Memory files are plain markdown stored in a configurable directory.
    The agent can read all three files but can only write to USER.md
    and WORKSPACE.md — SOUL.md defines agent identity and is read-only.
    """

    def __init__(self, memory_dir: str) -> None:
        self.memory_dir = Path(memory_dir)

    def _file_path(self, name: str) -> Path:
        """Get the full path for a memory file by short name."""
        if name not in MEMORY_FILES:
            raise ValueError(f"Invalid memory file name: {name!r}. Must be one of {MEMORY_FILES}")
        return self.memory_dir / FILE_NAMES[name]

    def ensure_files(self) -> None:
        """Create memory dir and default files if they don't exist."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        for name in MEMORY_FILES:
            path = self._file_path(name)
            if not path.exists():
                path.write_text(DEFAULTS[name], encoding="utf-8")
                logger.info("Created default memory file: %s", path)

    def load_all(self) -> dict[str, str]:
        """Load all memory files.

        Returns:
            Dict with keys "soul", "user", "workspace" mapped to file contents.
            Missing files return empty strings.
        """
        result = {}
        for name in MEMORY_FILES:
            result[name] = self.read_file(name)
        return result

    def read_file(self, name: str) -> str:
        """Read a specific memory file.

        Args:
            name: One of "soul", "user", "workspace".

        Returns:
            File contents as string, or empty string if file doesn't exist.
        """
        path = self._file_path(name)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def update_section(self, name: str, section: str, content: str) -> bool:
        """Update a specific section in a memory file.

        Args:
            name: Must be "user" or "workspace" (not "soul").
            section: A markdown heading like "## Profile" or "## Saved Workflows".
            content: The new content for that section (replaces everything under the heading).

        Returns:
            True on success, False on error.
        """
        if name not in WRITABLE_FILES:
            return False

        path = self._file_path(name)
        if not path.exists():
            # Create the file with the section
            path.write_text(f"{section}\n\n{content}\n", encoding="utf-8")
            return True

        text = path.read_text(encoding="utf-8")

        # Determine heading level from the section string
        heading_match = re.match(r"^(#{1,6})\s+", section)
        if not heading_match:
            return False
        heading_level = len(heading_match.group(1))

        # Build a regex to find this section and everything until the next same-or-higher-level heading
        # Escape the section for regex
        escaped_section = re.escape(section)
        # Match the section heading and content until next heading of same or higher level, or end
        pattern = re.compile(
            rf"({escaped_section})\n(.*?)(?=\n#{{{1},{heading_level}}}\s|\Z)",
            re.DOTALL,
        )

        match = pattern.search(text)
        if match:
            # Replace the section content
            replacement = f"{section}\n\n{content}\n"
            text = text[: match.start()] + replacement + text[match.end() :]
        else:
            # Section doesn't exist — append it
            text = text.rstrip("\n") + f"\n\n{section}\n\n{content}\n"

        path.write_text(text, encoding="utf-8")
        return True

    def append_to_section(self, name: str, section: str, content: str) -> bool:
        """Append content to a section (for adding workflows, app notes, etc.).

        Args:
            name: Must be "user" or "workspace" (not "soul").
            section: A markdown heading like "## Saved Workflows".
            content: Content to append under the section.

        Returns:
            True on success, False on error.
        """
        if name not in WRITABLE_FILES:
            return False

        path = self._file_path(name)
        if not path.exists():
            # Create the file with the section and content
            path.write_text(f"{section}\n\n{content}\n", encoding="utf-8")
            return True

        text = path.read_text(encoding="utf-8")

        # Determine heading level from the section string
        heading_match = re.match(r"^(#{1,6})\s+", section)
        if not heading_match:
            return False
        heading_level = len(heading_match.group(1))

        # Find the section
        escaped_section = re.escape(section)
        pattern = re.compile(
            rf"({escaped_section})\n(.*?)(?=\n#{{{1},{heading_level}}}\s|\Z)",
            re.DOTALL,
        )

        match = pattern.search(text)
        if match:
            # Append content at the end of the section (before the next heading)
            insert_pos = match.end()
            text = text[:insert_pos].rstrip("\n") + f"\n\n{content}\n" + text[insert_pos:]
        else:
            # Section doesn't exist — create it with the content
            text = text.rstrip("\n") + f"\n\n{section}\n\n{content}\n"

        path.write_text(text, encoding="utf-8")
        return True

    def build_system_prompt(self, base_prompt: str) -> str:
        """Build a full system prompt by appending memory file contents.

        Concatenates:
        1. base_prompt (the existing SYSTEM_PROMPT behavioral guidelines)
        2. SOUL.md contents (wrapped in ## Agent Identity)
        3. USER.md contents (wrapped in ## User Profile)
        4. WORKSPACE.md contents (wrapped in ## Workspace Knowledge)

        If memory files don't exist, their sections are simply omitted.

        Args:
            base_prompt: The base system prompt string.

        Returns:
            The enriched system prompt.
        """
        parts = [base_prompt]

        memory = self.load_all()

        if memory.get("soul"):
            parts.append(f"\n## Agent Identity\n\n{memory['soul']}")

        if memory.get("user"):
            parts.append(f"\n## User Profile\n\n{memory['user']}")

        if memory.get("workspace"):
            parts.append(f"\n## Workspace Knowledge\n\n{memory['workspace']}")

        return "\n".join(parts)
