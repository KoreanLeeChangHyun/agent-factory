"""Skill validation and installation module.

Validates converted skills against 7 quality checks and installs them
into the .claude/skills/ directory structure.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CheckResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    message: str


@dataclass
class ValidationReport:
    """Aggregated result of all validation checks."""

    passed: bool
    checks: list[CheckResult]
    warnings: list[str]


# ---------------------------------------------------------------------------
# Lightweight local stub so this module can be imported and tested even when
# format_converter.py has not been created yet (W04 runs in parallel).
# When format_converter is available the canonical ConvertedSkill is used.
# ---------------------------------------------------------------------------
try:
    from .format_converter import ConvertedSkill  # noqa: F401
except Exception:
    try:
        from format_converter import ConvertedSkill  # noqa: F401
    except Exception:

        @dataclass
        class ConvertedSkill:  # type: ignore[no-redef]
            """Fallback stub matching the W04 contract."""

            name: str
            path: str
            frontmatter: dict
            body: str
            resources: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_NAME_REGEX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_DESCRIPTION_MIN_LENGTH = 50
_BODY_MAX_LINES = 500
_COMPATIBLE_LICENSES = frozenset(
    {
        "apache-2.0",
        "mit",
        "bsd-2-clause",
        "bsd-3-clause",
        "isc",
        "unlicense",
        "cc0-1.0",
        "0bsd",
        "mpl-2.0",
    }
)


# =========================================================================
# SkillValidator
# =========================================================================
class SkillValidator:
    """Run 7 quality checks on a ``ConvertedSkill``."""

    def validate(self, skill: ConvertedSkill) -> ValidationReport:
        """Execute all checks and return an aggregated report."""

        checks: list[CheckResult] = [
            self._check_frontmatter_validity(skill),
            self._check_name_regex(skill),
            self._check_description_quality(skill),
            self._check_file_reference_integrity(skill),
            self._check_conflict(skill),
            self._check_progressive_disclosure(skill),
            self._check_license_compatibility(skill),
        ]

        warnings: list[str] = []
        for cr in checks:
            if not cr.passed:
                warnings.append(f"[{cr.name}] {cr.message}")

        passed = all(cr.passed for cr in checks)
        return ValidationReport(passed=passed, checks=checks, warnings=warnings)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_frontmatter_validity(skill: ConvertedSkill) -> CheckResult:
        """Check 1: frontmatter contains required fields (name, description)."""
        fm = skill.frontmatter or {}
        missing: list[str] = []
        if "name" not in fm:
            missing.append("name")
        if "description" not in fm:
            missing.append("description")

        if missing:
            return CheckResult(
                name="frontmatter_validity",
                passed=False,
                message=f"Missing required frontmatter fields: {', '.join(missing)}",
            )
        return CheckResult(
            name="frontmatter_validity",
            passed=True,
            message="All required frontmatter fields present",
        )

    @staticmethod
    def _check_name_regex(skill: ConvertedSkill) -> CheckResult:
        """Check 2: name matches ``^[a-z0-9]+(-[a-z0-9]+)*$``."""
        name = (skill.frontmatter or {}).get("name", skill.name)
        if not name:
            return CheckResult(
                name="name_regex",
                passed=False,
                message="Skill name is empty",
            )
        if _NAME_REGEX.match(name):
            return CheckResult(
                name="name_regex",
                passed=True,
                message=f"Name '{name}' matches required pattern",
            )
        return CheckResult(
            name="name_regex",
            passed=False,
            message=f"Name '{name}' does not match pattern ^[a-z0-9]+(-[a-z0-9]+)*$",
        )

    @staticmethod
    def _check_description_quality(skill: ConvertedSkill) -> CheckResult:
        """Check 3: description >= 50 chars and contains quality signals."""
        desc = (skill.frontmatter or {}).get("description", "")
        if not desc:
            return CheckResult(
                name="description_quality",
                passed=False,
                message="Description is empty",
            )

        issues: list[str] = []
        if len(desc) < _DESCRIPTION_MIN_LENGTH:
            issues.append(
                f"Length {len(desc)} < {_DESCRIPTION_MIN_LENGTH} characters"
            )

        lower = desc.lower()
        has_quality_signal = any(
            pat in lower
            for pat in ("use this when", "use for", "use when", "triggers:")
        )
        if not has_quality_signal:
            issues.append(
                "Missing quality signal ('Use this when', 'Use for', etc.)"
            )

        if issues:
            return CheckResult(
                name="description_quality",
                passed=False,
                message="; ".join(issues),
            )
        return CheckResult(
            name="description_quality",
            passed=True,
            message=f"Description quality OK (length={len(desc)})",
        )

    @staticmethod
    def _check_file_reference_integrity(skill: ConvertedSkill) -> CheckResult:
        """Check 4: all relative paths referenced in body actually exist."""
        if not skill.path or not os.path.isdir(skill.path):
            return CheckResult(
                name="file_reference_integrity",
                passed=True,
                message="No local path to verify (skipped)",
            )

        ref_pattern = re.compile(
            r"(?:scripts/|references/|assets/)[^\s\)\"'>]+", re.MULTILINE
        )
        refs = ref_pattern.findall(skill.body or "")

        missing: list[str] = []
        for ref in refs:
            full = os.path.join(skill.path, ref)
            if not os.path.exists(full):
                missing.append(ref)

        if missing:
            return CheckResult(
                name="file_reference_integrity",
                passed=False,
                message=f"Missing referenced files: {', '.join(missing[:5])}",
            )
        return CheckResult(
            name="file_reference_integrity",
            passed=True,
            message=f"All {len(refs)} file references resolved",
        )

    @staticmethod
    def _check_conflict(skill: ConvertedSkill) -> CheckResult:
        """Check 5: target directory does not already exist."""
        name = (skill.frontmatter or {}).get("name", skill.name)
        target = os.path.join(".claude", "skills", name)
        if os.path.isdir(target):
            return CheckResult(
                name="conflict_check",
                passed=False,
                message=f"Skill directory already exists: {target}",
            )
        return CheckResult(
            name="conflict_check",
            passed=True,
            message="No existing skill conflict",
        )

    @staticmethod
    def _check_progressive_disclosure(skill: ConvertedSkill) -> CheckResult:
        """Check 6: SKILL.md body is within 500 lines."""
        body = skill.body or ""
        line_count = body.count("\n") + (1 if body and not body.endswith("\n") else 0)
        if line_count > _BODY_MAX_LINES:
            return CheckResult(
                name="progressive_disclosure",
                passed=False,
                message=(
                    f"Body has {line_count} lines (max {_BODY_MAX_LINES}). "
                    "Move detailed content to references/"
                ),
            )
        return CheckResult(
            name="progressive_disclosure",
            passed=True,
            message=f"Body line count OK ({line_count} <= {_BODY_MAX_LINES})",
        )

    @staticmethod
    def _check_license_compatibility(skill: ConvertedSkill) -> CheckResult:
        """Check 7: license is compatible (permissive open-source)."""
        fm = skill.frontmatter or {}
        license_val = fm.get("license", "")

        # Also check for LICENSE file in skill path
        if not license_val and skill.path and os.path.isdir(skill.path):
            license_file = os.path.join(skill.path, "LICENSE")
            alt_license_file = os.path.join(skill.path, "LICENSE.txt")
            if os.path.isfile(license_file) or os.path.isfile(alt_license_file):
                return CheckResult(
                    name="license_compatibility",
                    passed=True,
                    message="LICENSE file found (manual review recommended)",
                )

        if not license_val:
            return CheckResult(
                name="license_compatibility",
                passed=False,
                message="No license information found",
            )

        normalized = license_val.strip().lower()
        if normalized in _COMPATIBLE_LICENSES:
            return CheckResult(
                name="license_compatibility",
                passed=True,
                message=f"License '{license_val}' is compatible",
            )

        return CheckResult(
            name="license_compatibility",
            passed=False,
            message=f"License '{license_val}' not in compatible list; manual review needed",
        )


# =========================================================================
# SkillInstaller
# =========================================================================
class SkillInstaller:
    """Install a validated ``ConvertedSkill`` into ``.claude/skills/``."""

    def install(
        self,
        skill: ConvertedSkill,
        target_base: str = ".claude/skills",
    ) -> str:
        """Copy skill into ``target_base/{name}/`` directory.

        Returns:
            One of ``"installed"``, ``"conflict"``, or ``"error:<msg>"``.
        """
        name = (skill.frontmatter or {}).get("name", skill.name)
        target_dir = os.path.join(target_base, name)

        # Conflict detection
        if os.path.isdir(target_dir):
            return "conflict"

        source = skill.path
        if not source or not os.path.isdir(source):
            return f"error:source path does not exist ({source})"

        try:
            self._copy_skill(source, target_dir, skill)
            return "installed"
        except Exception as exc:  # noqa: BLE001
            # Rollback on failure
            if os.path.isdir(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            return f"error:{exc}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _copy_skill(
        source: str,
        target_dir: str,
        skill: ConvertedSkill,
    ) -> None:
        """Create target directory and copy skill contents."""
        os.makedirs(target_dir, exist_ok=True)

        # Write SKILL.md from in-memory data (frontmatter + body)
        skill_md = SkillInstaller._build_skill_md(skill)
        skill_md_path = os.path.join(target_dir, "SKILL.md")
        with open(skill_md_path, "w", encoding="utf-8") as fh:
            fh.write(skill_md)

        # Copy resource directories (scripts/, references/, assets/)
        for subdir in ("scripts", "references", "assets"):
            src_sub = os.path.join(source, subdir)
            if os.path.isdir(src_sub):
                dst_sub = os.path.join(target_dir, subdir)
                shutil.copytree(src_sub, dst_sub, dirs_exist_ok=True)

        # Copy any additional resource files listed in skill.resources
        for res in skill.resources or []:
            src_file = os.path.join(source, res)
            if os.path.isfile(src_file):
                dst_file = os.path.join(target_dir, res)
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                shutil.copy2(src_file, dst_file)

    @staticmethod
    def _build_skill_md(skill: ConvertedSkill) -> str:
        """Reconstruct SKILL.md content from frontmatter dict and body."""
        lines: list[str] = ["---"]
        fm = skill.frontmatter or {}
        for key, value in fm.items():
            if isinstance(value, str) and "\n" in value:
                lines.append(f"{key}: |")
                for vline in value.split("\n"):
                    lines.append(f"  {vline}")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")
        if skill.body:
            lines.append(skill.body)
        return "\n".join(lines)


# =========================================================================
# Convenience function
# =========================================================================
def validate_and_install(
    skill: ConvertedSkill,
    target_base: str = ".claude/skills",
    *,
    dry_run: bool = False,
) -> tuple[ValidationReport, Optional[str]]:
    """Validate a skill and optionally install it.

    Args:
        skill: The converted skill to validate.
        target_base: Base directory for installation.
        dry_run: If True, skip installation even when validation passes.

    Returns:
        Tuple of (ValidationReport, install_status).
        install_status is None when dry_run is True or validation fails.
    """
    validator = SkillValidator()
    report = validator.validate(skill)

    install_status: Optional[str] = None
    if report.passed and not dry_run:
        installer = SkillInstaller()
        install_status = installer.install(skill, target_base=target_base)

    return report, install_status
