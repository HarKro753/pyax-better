"""Tests for MemoryManager — file creation, reading, updating, and system prompt building."""

import pytest

from pyax_agent.memory import (
    DEFAULT_SOUL,
    DEFAULT_USER,
    DEFAULT_WORKSPACE,
    MEMORY_FILES,
    WRITABLE_FILES,
    MemoryManager,
)


class TestMemoryManagerInit:
    """Tests for MemoryManager initialization."""

    def test_creates_with_path(self, tmp_path):
        mm = MemoryManager(str(tmp_path / "memory"))
        assert mm.memory_dir == tmp_path / "memory"

    def test_ensure_files_creates_dir(self, tmp_path):
        mem_dir = tmp_path / "new_memory"
        mm = MemoryManager(str(mem_dir))
        assert not mem_dir.exists()
        mm.ensure_files()
        assert mem_dir.exists()

    def test_ensure_files_creates_all_defaults(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        assert (tmp_path / "SOUL.md").exists()
        assert (tmp_path / "USER.md").exists()
        assert (tmp_path / "WORKSPACE.md").exists()

    def test_ensure_files_default_contents(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        assert (tmp_path / "SOUL.md").read_text() == DEFAULT_SOUL
        assert (tmp_path / "USER.md").read_text() == DEFAULT_USER
        assert (tmp_path / "WORKSPACE.md").read_text() == DEFAULT_WORKSPACE

    def test_ensure_files_does_not_overwrite(self, tmp_path):
        """Existing files should not be overwritten."""
        (tmp_path / "SOUL.md").write_text("custom soul")
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        assert (tmp_path / "SOUL.md").read_text() == "custom soul"
        # But missing files should still be created
        assert (tmp_path / "USER.md").exists()
        assert (tmp_path / "WORKSPACE.md").exists()

    def test_ensure_files_nested_dir(self, tmp_path):
        mem_dir = tmp_path / "a" / "b" / "c"
        mm = MemoryManager(str(mem_dir))
        mm.ensure_files()
        assert (mem_dir / "SOUL.md").exists()


class TestMemoryManagerRead:
    """Tests for reading memory files."""

    def test_read_file_soul(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        content = mm.read_file("soul")
        assert "# Soul" in content
        assert "Mission" in content

    def test_read_file_user(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        content = mm.read_file("user")
        assert "# User" in content

    def test_read_file_workspace(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        content = mm.read_file("workspace")
        assert "# Workspace" in content

    def test_read_nonexistent_file(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        # Don't call ensure_files — files don't exist
        content = mm.read_file("soul")
        assert content == ""

    def test_read_invalid_name(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        with pytest.raises(ValueError, match="Invalid memory file name"):
            mm.read_file("invalid")

    def test_load_all(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        result = mm.load_all()
        assert set(result.keys()) == {"soul", "user", "workspace"}
        assert "# Soul" in result["soul"]
        assert "# User" in result["user"]
        assert "# Workspace" in result["workspace"]

    def test_load_all_missing_files(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        result = mm.load_all()
        assert result == {"soul": "", "user": "", "workspace": ""}


class TestMemoryManagerUpdateSection:
    """Tests for updating sections in memory files."""

    def test_update_user_section(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        result = mm.update_section("user", "## Profile", "Name: Alice\nAge: 30")
        assert result is True
        content = mm.read_file("user")
        assert "## Profile" in content
        assert "Name: Alice" in content

    def test_update_workspace_section(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        result = mm.update_section("workspace", "## Apps", "Safari, Finder, Mail")
        assert result is True
        content = mm.read_file("workspace")
        assert "## Apps" in content
        assert "Safari, Finder, Mail" in content

    def test_update_soul_rejected(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        result = mm.update_section("soul", "## Mission", "New mission")
        assert result is False

    def test_update_invalid_name(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        result = mm.update_section("invalid", "## Section", "content")
        assert result is False

    def test_update_creates_new_section(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        mm.update_section("user", "## Disability", "Low vision")
        content = mm.read_file("user")
        assert "## Disability" in content
        assert "Low vision" in content

    def test_update_replaces_existing_section(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        mm.update_section("user", "## Profile", "Name: Alice")
        mm.update_section("user", "## Profile", "Name: Bob")
        content = mm.read_file("user")
        assert "Name: Bob" in content
        assert "Name: Alice" not in content

    def test_update_creates_file_if_missing(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        # File doesn't exist yet (no ensure_files)
        result = mm.update_section("user", "## Profile", "Name: Alice")
        assert result is True
        content = mm.read_file("user")
        assert "## Profile" in content
        assert "Name: Alice" in content

    def test_update_invalid_section_heading(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        result = mm.update_section("user", "No heading marker", "content")
        assert result is False

    def test_update_preserves_other_sections(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        mm.update_section("user", "## Profile", "Name: Alice")
        mm.update_section("user", "## Disability", "Low vision")
        mm.update_section("user", "## Profile", "Name: Bob")
        content = mm.read_file("user")
        assert "Name: Bob" in content
        assert "## Disability" in content
        assert "Low vision" in content


class TestMemoryManagerAppendToSection:
    """Tests for appending to sections."""

    def test_append_to_existing_section(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        mm.update_section("workspace", "## Saved Workflows", "Existing content")
        mm.append_to_section("workspace", "## Saved Workflows", "New content")
        content = mm.read_file("workspace")
        assert "Existing content" in content
        assert "New content" in content

    def test_append_creates_section(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        mm.append_to_section("workspace", "## Saved Workflows", "First workflow")
        content = mm.read_file("workspace")
        assert "## Saved Workflows" in content
        assert "First workflow" in content

    def test_append_to_soul_rejected(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        result = mm.append_to_section("soul", "## New Section", "content")
        assert result is False

    def test_append_creates_file_if_missing(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        result = mm.append_to_section("workspace", "## Notes", "A note")
        assert result is True
        content = mm.read_file("workspace")
        assert "## Notes" in content
        assert "A note" in content

    def test_append_invalid_section_heading(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        result = mm.append_to_section("workspace", "No heading", "content")
        assert result is False

    def test_append_multiple_items(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        mm.append_to_section("workspace", "## Saved Workflows", "### Check Email\n\n1. Open Mail")
        mm.append_to_section("workspace", "## Saved Workflows", "### Read News\n\n1. Open Safari")
        content = mm.read_file("workspace")
        assert "### Check Email" in content
        assert "### Read News" in content


class TestMemoryManagerBuildSystemPrompt:
    """Tests for building enriched system prompts."""

    def test_build_with_all_files(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        prompt = mm.build_system_prompt("Base prompt here.")
        assert prompt.startswith("Base prompt here.")
        assert "## Agent Identity" in prompt
        assert "## User Profile" in prompt
        assert "## Workspace Knowledge" in prompt
        assert "# Soul" in prompt
        assert "# User" in prompt
        assert "# Workspace" in prompt

    def test_build_without_files(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        # Don't ensure files — they don't exist
        prompt = mm.build_system_prompt("Base prompt here.")
        assert prompt == "Base prompt here."
        assert "## Agent Identity" not in prompt

    def test_build_partial_files(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        # Only create SOUL.md
        (tmp_path / "SOUL.md").write_text("Agent soul content")
        prompt = mm.build_system_prompt("Base prompt.")
        assert "## Agent Identity" in prompt
        assert "Agent soul content" in prompt
        assert "## User Profile" not in prompt
        assert "## Workspace Knowledge" not in prompt

    def test_build_preserves_base_prompt(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        base = "You are a test agent.\n\n## Guidelines\n\n- Be helpful"
        prompt = mm.build_system_prompt(base)
        assert prompt.startswith(base)

    def test_build_order(self, tmp_path):
        mm = MemoryManager(str(tmp_path))
        mm.ensure_files()
        prompt = mm.build_system_prompt("Base")
        # Verify ordering: base -> soul -> user -> workspace
        soul_pos = prompt.index("## Agent Identity")
        user_pos = prompt.index("## User Profile")
        workspace_pos = prompt.index("## Workspace Knowledge")
        assert soul_pos < user_pos < workspace_pos


class TestDefaultTemplates:
    """Tests for default template content."""

    def test_soul_has_mission(self):
        assert "## Mission" in DEFAULT_SOUL

    def test_soul_has_personality(self):
        assert "## Personality" in DEFAULT_SOUL

    def test_soul_has_values(self):
        assert "## Values" in DEFAULT_SOUL

    def test_soul_has_accessibility_behavior(self):
        assert "## Accessibility-First Behavior" in DEFAULT_SOUL

    def test_user_has_placeholder(self):
        assert "No user profile yet" in DEFAULT_USER

    def test_workspace_has_placeholder(self):
        assert "No workspace knowledge yet" in DEFAULT_WORKSPACE


class TestMemoryConstants:
    """Tests for module-level constants."""

    def test_memory_files(self):
        assert MEMORY_FILES == ("soul", "user", "workspace")

    def test_writable_files(self):
        assert WRITABLE_FILES == ("user", "workspace")
        assert "soul" not in WRITABLE_FILES
