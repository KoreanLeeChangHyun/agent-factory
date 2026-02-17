"""Main pipeline orchestrator for skill-auto-integrator.

Orchestrates the 7-stage pipeline:
  1. Prompt analysis  (prompt_analyzer)
  2. Skill search     (skill_search)
  3. Ranking          (skill_search - compute_final_score)
  4. Download         (skill_search - SkillDownloader)
  5. Format conversion(format_converter)
  6. Validation & Install (validator)
  7. Post-install keyword suggestion (command-skill-map registration)

Usage::

    python skill_auto_integrate.py "PDF 처리 스킬"
    python skill_auto_integrate.py --dry-run "코드 리뷰 스킬"
    python skill_auto_integrate.py --target /path/to/skills "데이터 분석 스킬"
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Sibling module imports (support both package and direct execution)
# ---------------------------------------------------------------------------
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from prompt_analyzer import PromptAnalyzer, SearchQuery  # noqa: E402
from skill_search import (  # noqa: E402
    SkillSearcher,
    SkillDownloader,
    SearchResult,
    DownloadedSkill,
)
from format_converter import FormatConverter, ConvertedSkill  # noqa: E402
from validator import (  # noqa: E402
    SkillValidator,
    SkillInstaller,
    ValidationReport,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class IntegrationResult:
    """Final result of the full integration pipeline."""

    success: bool
    skill_name: str = ""
    install_path: str = ""
    validation_report: Optional[ValidationReport] = None
    suggested_keywords: list[str] = field(default_factory=list)
    error: str = ""
    stage: str = ""  # stage where failure occurred


# ---------------------------------------------------------------------------
# TF-IDF keyword extraction for command-skill-map suggestion
# ---------------------------------------------------------------------------

# Common English stop-words for TF-IDF filtering
_TFIDF_STOPWORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
    "they", "them", "their", "what", "which", "who", "whom",
    "this", "that", "these", "those", "and", "but", "or", "if",
    "because", "as", "until", "while", "of", "at", "by", "for",
    "with", "about", "against", "between", "through", "during",
    "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "now", "use", "using", "used",
    "skill", "skills", "tool", "tools", "plugin", "plugins",
    "provides", "provides", "automated", "standard", "directory",
    "into", "also", "etc", "via",
}


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase alphanumeric tokens."""
    return [t.lower() for t in re.findall(r"[a-zA-Z\uac00-\ud7a3]{2,}", text)]


def _compute_tf(tokens: list[str]) -> dict[str, float]:
    """Compute term-frequency for a token list."""
    counts = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {t: c / total for t, c in counts.items()}


def _compute_idf_simple(term: str, corpus_size: int = 100) -> float:
    """Approximate IDF.  Rare/technical terms get higher scores.

    Since we don't have a real corpus, we use heuristics:
    - Stop-words and very common terms get low IDF
    - Technical terms (containing digits, hyphens, or being long) get high IDF
    """
    if term in _TFIDF_STOPWORDS:
        return 0.1

    score = 1.0

    # Longer words tend to be more specific
    if len(term) >= 8:
        score += 0.5
    elif len(term) >= 5:
        score += 0.3

    # Korean tokens are usually specific
    if re.search(r"[\uac00-\ud7a3]", term):
        score += 0.5

    # All-uppercase (acronyms like API, REST) are specific
    if term.isupper() and len(term) >= 2:
        score += 0.8

    return score


def extract_tfidf_keywords(
    description: str,
    top_k: int = 5,
    min_keywords: int = 3,
) -> list[str]:
    """Extract top keywords from description using TF-IDF heuristics.

    Returns between *min_keywords* and *top_k* keywords sorted by score.
    """
    tokens = _tokenize(description)
    if not tokens:
        return []

    tf = _compute_tf(tokens)
    scored: list[tuple[str, float]] = []
    seen: set[str] = set()

    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        if token in _TFIDF_STOPWORDS:
            continue
        idf = _compute_idf_simple(token)
        tfidf = tf[token] * idf
        scored.append((token, tfidf))

    scored.sort(key=lambda x: x[1], reverse=True)

    # Return between min_keywords and top_k
    count = max(min_keywords, min(top_k, len(scored)))
    return [t for t, _ in scored[:count]]


def format_keyword_suggestion(
    skill_name: str,
    keywords: list[str],
) -> str:
    """Format a command-skill-map table row suggestion."""
    kw_str = ", ".join(keywords)
    lines = [
        "",
        "=== command-skill-map registration suggestion ===",
        "",
        "Add the following row to the keyword table in",
        ".claude/skills/workflow-work/command-skill-map.md:",
        "",
        f"| {kw_str} | {skill_name} |",
        "",
        "================================================",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class SkillAutoIntegrator:
    """Orchestrates the 7-stage skill integration pipeline.

    Usage::

        integrator = SkillAutoIntegrator()
        result = integrator.run("PDF 처리 스킬 찾아줘")
    """

    def __init__(
        self,
        target_base: str = ".claude/skills",
        dry_run: bool = False,
    ):
        self.target_base = target_base
        self.dry_run = dry_run

        # Component instances
        self._analyzer = PromptAnalyzer()
        self._searcher = SkillSearcher()
        self._downloader = SkillDownloader()
        self._converter = FormatConverter()
        self._validator = SkillValidator()
        self._installer = SkillInstaller()

    def run(self, prompt: str) -> IntegrationResult:
        """Execute the full 7-stage pipeline.

        Stages:
            1. Prompt analysis
            2. Skill search
            3. Ranking (embedded in search)
            4. Download
            5. Format conversion
            6. Validation & installation
            7. Post-install keyword suggestion

        Each stage failure aborts the pipeline with an error message.
        """

        # --- Stage 1: Prompt Analysis ---
        try:
            query = self._analyzer.analyze(prompt)
        except Exception as exc:
            return IntegrationResult(
                success=False,
                error=f"Prompt analysis failed: {exc}",
                stage="prompt_analysis",
            )

        if not query.keywords:
            return IntegrationResult(
                success=False,
                error="No keywords could be extracted from the prompt.",
                stage="prompt_analysis",
            )

        logger.info(
            "Stage 1 complete: keywords=%s, domain=%s, task_type=%s",
            query.keywords, query.domain, query.task_type,
        )

        # --- Stage 2+3: Search & Ranking ---
        try:
            candidates = self._searcher.search(query, top_k=3)
        except Exception as exc:
            return IntegrationResult(
                success=False,
                error=f"Skill search failed: {exc}",
                stage="search",
            )

        if not candidates:
            return IntegrationResult(
                success=False,
                error=f"No skills found for keywords: {query.keywords}",
                stage="search",
            )

        logger.info(
            "Stage 2-3 complete: %d candidates found (top: %s, score=%.3f)",
            len(candidates), candidates[0].name, candidates[0].score,
        )

        # --- Stage 4: Download ---
        tmp_dir = tempfile.mkdtemp(prefix="skill-download-")
        try:
            downloaded = self._downloader.download_first_successful(
                candidates, tmp_dir,
            )
        except RuntimeError as exc:
            return IntegrationResult(
                success=False,
                error=f"Download failed: {exc}",
                stage="download",
            )
        except Exception as exc:
            return IntegrationResult(
                success=False,
                error=f"Unexpected download error: {exc}",
                stage="download",
            )

        logger.info(
            "Stage 4 complete: downloaded '%s' to %s (format=%s)",
            downloaded.name, downloaded.local_path, downloaded.format_type,
        )

        # --- Stage 5: Format Conversion ---
        # Bridge attribute name: format_converter expects `source_dir`,
        # skill_search produces `local_path`.
        if not hasattr(downloaded, "source_dir"):
            downloaded.source_dir = downloaded.local_path  # type: ignore[attr-defined]

        try:
            converted = self._converter.convert(downloaded)
        except Exception as exc:
            return IntegrationResult(
                success=False,
                error=f"Format conversion failed: {exc}",
                stage="format_conversion",
            )

        logger.info(
            "Stage 5 complete: converted '%s' (%d resources)",
            converted.name, len(converted.resources),
        )

        # --- Stage 6: Validation & Installation ---
        try:
            report = self._validator.validate(converted)
        except Exception as exc:
            return IntegrationResult(
                success=False,
                error=f"Validation failed: {exc}",
                stage="validation",
            )

        install_path = ""
        if report.passed and not self.dry_run:
            try:
                status = self._installer.install(
                    converted, target_base=self.target_base,
                )
                if status == "installed":
                    install_path = os.path.join(
                        self.target_base, converted.name,
                    )
                elif status == "conflict":
                    return IntegrationResult(
                        success=False,
                        skill_name=converted.name,
                        validation_report=report,
                        error=(
                            f"Skill '{converted.name}' already exists at "
                            f"{self.target_base}/{converted.name}"
                        ),
                        stage="installation",
                    )
                else:
                    return IntegrationResult(
                        success=False,
                        skill_name=converted.name,
                        validation_report=report,
                        error=f"Installation failed: {status}",
                        stage="installation",
                    )
            except Exception as exc:
                return IntegrationResult(
                    success=False,
                    skill_name=converted.name,
                    validation_report=report,
                    error=f"Installation error: {exc}",
                    stage="installation",
                )
        elif not report.passed:
            logger.warning(
                "Validation failed with %d warnings",
                len(report.warnings),
            )
            return IntegrationResult(
                success=False,
                skill_name=converted.name,
                validation_report=report,
                error=(
                    "Validation failed: "
                    + "; ".join(report.warnings[:3])
                ),
                stage="validation",
            )

        logger.info(
            "Stage 6 complete: %s (dry_run=%s, path=%s)",
            "validated" if self.dry_run else "installed",
            self.dry_run,
            install_path or "(dry-run)",
        )

        # --- Stage 7: Keyword Suggestion ---
        description = (converted.frontmatter or {}).get("description", "")
        suggested_keywords = extract_tfidf_keywords(description, top_k=5)

        logger.info(
            "Stage 7 complete: suggested keywords=%s",
            suggested_keywords,
        )

        return IntegrationResult(
            success=True,
            skill_name=converted.name,
            install_path=install_path,
            validation_report=report,
            suggested_keywords=suggested_keywords,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for CLI invocation."""
    parser = argparse.ArgumentParser(
        prog="skill_auto_integrate",
        description=(
            "Automated skill integration pipeline: search, download, "
            "convert, and install external AI skills from SkillsMP "
            "marketplace into .claude/skills/"
        ),
    )
    parser.add_argument(
        "prompt",
        help="Natural language search prompt (e.g. 'PDF 처리 스킬')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Search and convert only; skip installation",
    )
    parser.add_argument(
        "--target",
        default=".claude/skills",
        help="Installation target directory (default: .claude/skills)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns 0 on success, 1 on pipeline failure.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s",
    )

    integrator = SkillAutoIntegrator(
        target_base=args.target,
        dry_run=args.dry_run,
    )
    result = integrator.run(args.prompt)

    # Output results
    if result.success:
        print(f"\nSkill '{result.skill_name}' integration successful.")
        if result.install_path:
            print(f"Installed to: {result.install_path}")
        else:
            print("(dry-run mode: installation skipped)")

        if result.validation_report:
            passed = sum(
                1 for c in result.validation_report.checks if c.passed
            )
            total = len(result.validation_report.checks)
            print(f"Validation: {passed}/{total} checks passed")

        if result.suggested_keywords:
            print(
                format_keyword_suggestion(
                    result.skill_name, result.suggested_keywords,
                )
            )
        return 0
    else:
        print(f"\nPipeline failed at stage '{result.stage}'.")
        print(f"Error: {result.error}")
        if result.validation_report and result.validation_report.warnings:
            print("\nValidation warnings:")
            for w in result.validation_report.warnings:
                print(f"  - {w}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
