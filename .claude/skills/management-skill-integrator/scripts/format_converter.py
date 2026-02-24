"""Format converter module for management-skill-integrator pipeline.

Converts downloaded skill packages into .claude/skills/ standard directory
structure. Handles frontmatter generation/correction, directory mapping, and
removal of unnecessary files.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# DownloadedSkill is defined in skill_search.py (W03).
# Import at runtime; define a compatible protocol for standalone usage.
try:
    from .skill_search import DownloadedSkill
except ImportError:
    try:
        from skill_search import DownloadedSkill
    except ImportError:
        # Fallback dataclass for standalone / testing usage
        @dataclass
        class DownloadedSkill:  # type: ignore[no-redef]
            """Minimal stand-in when skill_search is unavailable."""
            name: str
            source_dir: str
            url: str = ""
            metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class ConvertedSkill:
    """Result of format conversion -- ready for validation & installation."""
    name: str
    path: str
    frontmatter: dict[str, Any]
    body: str
    resources: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Name must be lowercase kebab-case
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Directory mapping: source patterns -> target directory
_DIR_MAPPING: dict[str, str] = {
    "src": "scripts",
    "lib": "scripts",
    "bin": "scripts",
    "docs": "references",
    "guides": "references",
    "examples": "references",
    "assets": "assets",
    "images": "assets",
    "templates": "assets",
}

# Files to remove during conversion
_REMOVABLE_FILES: set[str] = {
    "README.md",
    "CHANGELOG.md",
    ".gitignore",
    ".git",
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "package.json",
    "package-lock.json",
    "node_modules",
    ".npmrc",
    ".npmignore",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "setup.py",
    "setup.cfg",
    "pyproject.toml",
}

# Minimum description length threshold
_MIN_DESCRIPTION_LENGTH = 50


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

class _FormatType:
    """Detected format type constants."""
    AGENT_SKILLS = "agent-skills"
    MCP_SERVER = "mcp-server"
    NPM_PACKAGE = "npm-package"
    UNKNOWN = "unknown"


def _detect_format(source_dir: str) -> str:
    """Detect the format type of a downloaded skill package.

    Returns one of _FormatType constants.
    """
    p = Path(source_dir)

    # Agent Skills: has SKILL.md at root
    if (p / "SKILL.md").exists():
        return _FormatType.AGENT_SKILLS

    # MCP Server: has mcp.json or server.json
    if (p / "mcp.json").exists() or (p / "server.json").exists():
        return _FormatType.MCP_SERVER

    # npm package: has package.json
    if (p / "package.json").exists():
        return _FormatType.NPM_PACKAGE

    return _FormatType.UNKNOWN


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.

    Returns (frontmatter_dict, body_text).
    If no frontmatter is found, returns (empty dict, full content).
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    # Simple YAML key:value parser (avoids PyYAML dependency)
    fm_raw = parts[1].strip()
    fm: dict[str, Any] = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip("'\"")
            fm[key] = value

    body = parts[2].lstrip("\n")
    return fm, body


def _normalize_name(raw_name: str) -> str:
    """Normalize a skill name to kebab-case ``^[a-z0-9]+(-[a-z0-9]+)*$``.

    Transformations:
    - Lowercase
    - Replace underscores, spaces, dots with hyphens
    - Collapse consecutive hyphens
    - Strip leading/trailing hyphens
    - Remove characters outside [a-z0-9-]
    """
    name = raw_name.lower()
    # Replace common separators with hyphens
    name = re.sub(r"[_\s.]+", "-", name)
    # Remove anything that isn't a-z, 0-9, or hyphen
    name = re.sub(r"[^a-z0-9-]", "", name)
    # Collapse consecutive hyphens
    name = re.sub(r"-{2,}", "-", name)
    # Strip leading/trailing hyphens
    name = name.strip("-")
    return name or "unnamed-skill"


def _build_frontmatter(fm: dict[str, Any], name: str) -> dict[str, Any]:
    """Ensure frontmatter has required fields with correct values."""
    result = dict(fm)

    # Normalize name
    result["name"] = _normalize_name(name)

    # Ensure description exists and meets minimum length
    desc = result.get("description", "")
    if not isinstance(desc, str):
        desc = str(desc)

    if len(desc) < _MIN_DESCRIPTION_LENGTH:
        # Generate expansion prompt
        desc = _expand_description(result["name"], desc)
    result["description"] = desc

    return result


def _expand_description(name: str, short_desc: str) -> str:
    """Expand a short description to meet minimum length requirements.

    Constructs a descriptive string from the skill name and any existing
    short description text.
    """
    parts = name.replace("-", " ").title()
    base = short_desc.strip() if short_desc.strip() else f"{parts} skill"
    expansion = (
        f"{base}. Provides automated functionality for {parts.lower()} "
        f"operations. Integrates with the .claude/skills/ standard pipeline."
    )
    return expansion


def _serialize_frontmatter(fm: dict[str, Any]) -> str:
    """Serialize a dict into YAML frontmatter string (simple key: value)."""
    lines = ["---"]
    for key, value in fm.items():
        # Quote values containing special chars
        val_str = str(value)
        if any(c in val_str for c in (":", "#", "{", "}", "[", "]", ",", "'", '"')):
            val_str = f'"{val_str}"'
        lines.append(f"{key}: {val_str}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Directory structure conversion
# ---------------------------------------------------------------------------

def _map_directory(source_dir: str, target_dir: str) -> list[str]:
    """Map source directory structure to .claude/skills/ standard layout.

    Returns list of resource file paths (relative to target_dir).
    """
    resources: list[str] = []
    source = Path(source_dir)
    target = Path(target_dir)

    if not source.is_dir():
        return resources

    for item in source.iterdir():
        # Skip removable files/dirs
        if item.name in _REMOVABLE_FILES:
            continue

        # Skip hidden files/dirs (except .claude)
        if item.name.startswith(".") and item.name != ".claude":
            continue

        if item.is_dir():
            # Map known directory names
            mapped_name = _DIR_MAPPING.get(item.name, item.name)
            dest = target / mapped_name

            # Recursively copy contents
            if dest.exists():
                # Merge into existing directory
                _copy_tree_merge(str(item), str(dest))
            else:
                shutil.copytree(str(item), str(dest))

            # Collect resource paths
            for root, _dirs, files in os.walk(str(dest)):
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), str(target))
                    resources.append(rel)
        else:
            # Copy individual files (skip SKILL.md -- handled separately)
            if item.name == "SKILL.md":
                continue
            dest_file = target / item.name
            shutil.copy2(str(item), str(dest_file))
            resources.append(item.name)

    return resources


def _copy_tree_merge(src: str, dst: str) -> None:
    """Recursively copy src into dst, merging directories."""
    src_path = Path(src)
    dst_path = Path(dst)
    dst_path.mkdir(parents=True, exist_ok=True)

    for item in src_path.iterdir():
        dest = dst_path / item.name
        if item.is_dir():
            _copy_tree_merge(str(item), str(dest))
        else:
            shutil.copy2(str(item), str(dest))


def _clean_removable_files(target_dir: str) -> None:
    """Remove known unnecessary files from the target directory tree."""
    target = Path(target_dir)
    for root, dirs, files in os.walk(str(target), topdown=False):
        for name in files:
            if name in _REMOVABLE_FILES:
                os.remove(os.path.join(root, name))
        for name in dirs:
            if name in _REMOVABLE_FILES:
                shutil.rmtree(os.path.join(root, name), ignore_errors=True)


# ---------------------------------------------------------------------------
# Main converter class
# ---------------------------------------------------------------------------

class FormatConverter:
    """Converts downloaded skill packages to .claude/skills/ standard format.

    Usage::

        converter = FormatConverter()
        result = converter.convert(downloaded_skill)
    """

    def convert(self, downloaded: DownloadedSkill) -> ConvertedSkill:
        """Convert a downloaded skill package to standard format.

        Args:
            downloaded: A DownloadedSkill instance from the search/download
                        pipeline. Must have ``name`` and ``source_dir`` attrs.

        Returns:
            ConvertedSkill with normalized name, frontmatter, body, and
            resource list.
        """
        source_dir = downloaded.source_dir
        name = downloaded.name

        # 1. Detect format type
        fmt = _detect_format(source_dir)

        # 2. Read existing SKILL.md or generate skeleton
        skill_md_path = Path(source_dir) / "SKILL.md"
        if skill_md_path.exists():
            raw_content = skill_md_path.read_text(encoding="utf-8")
        else:
            raw_content = self._generate_skeleton(name, fmt, downloaded)

        # 3. Parse frontmatter
        fm, body = _parse_frontmatter(raw_content)

        # 4. Build/normalize frontmatter
        fm = _build_frontmatter(fm, name)

        # 5. Prepare conversion target directory (temp staging area)
        staging_dir = Path(source_dir).parent / f"_staged_{fm['name']}"
        staging_dir.mkdir(parents=True, exist_ok=True)

        # 6. Map directory structure
        resources = _map_directory(source_dir, str(staging_dir))

        # 7. Clean removable files from staged output
        _clean_removable_files(str(staging_dir))

        # 8. Refresh resource list after cleaning
        resources = []
        for root, _dirs, files in os.walk(str(staging_dir)):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), str(staging_dir))
                resources.append(rel)

        return ConvertedSkill(
            name=fm["name"],
            path=str(staging_dir),
            frontmatter=fm,
            body=body,
            resources=sorted(resources),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_skeleton(
        name: str,
        fmt: str,
        downloaded: DownloadedSkill,
    ) -> str:
        """Generate a SKILL.md skeleton when the source doesn't have one."""
        norm_name = _normalize_name(name)
        title = norm_name.replace("-", " ").title()

        metadata = getattr(downloaded, "metadata", {}) or {}
        desc = metadata.get("description", "")
        if not desc:
            desc = f"{title} skill"

        fm_block = _serialize_frontmatter({
            "name": norm_name,
            "description": desc,
        })

        body_lines = [
            f"# {title}",
            "",
            f"Converted from format: **{fmt}**.",
            "",
            "## Usage",
            "",
            f"This skill was auto-integrated from an external source.",
            "",
            "## Resources",
            "",
            "See the `scripts/`, `references/`, and `assets/` directories "
            "for converted resources.",
        ]

        return fm_block + "\n\n" + "\n".join(body_lines) + "\n"

    def convert_content_only(
        self,
        name: str,
        raw_content: str,
    ) -> tuple[dict[str, Any], str]:
        """Convert only the SKILL.md content (frontmatter + body).

        Useful when no filesystem operations are needed.

        Returns:
            (normalized_frontmatter, body)
        """
        fm, body = _parse_frontmatter(raw_content)
        fm = _build_frontmatter(fm, name)
        return fm, body
