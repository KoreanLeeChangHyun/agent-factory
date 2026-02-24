"""SkillsMP marketplace skill search and download module.

Searches the SkillsMP marketplace for skills matching a SearchQuery,
ranks results using a weighted scoring algorithm, and downloads
selected skills via git clone or HTTP.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import tarfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SearchQuery:
    """Query parameters extracted from user prompt.

    Defined here as a local fallback; the canonical definition lives in
    prompt_analyzer.py.  When both modules are available, the pipeline
    orchestrator passes the same object regardless of origin.
    """

    keywords: list[str] = field(default_factory=list)
    domain: str = ""
    task_type: str = ""


@dataclass
class SearchResult:
    """A single search result returned from the marketplace."""

    name: str = ""
    description: str = ""
    url: str = ""
    score: float = 0.0
    source: str = "skillsmp"


@dataclass
class DownloadedSkill:
    """Metadata about a successfully downloaded skill package."""

    name: str = ""
    local_path: str = ""
    format_type: str = "agent_skills"  # agent_skills | mcp_server | npm_package
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

_COMPATIBLE_LICENSES = frozenset({
    "mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "isc",
    "0bsd", "unlicense", "cc0-1.0", "mpl-2.0",
})


def _keyword_match_score(query: SearchQuery, result: SearchResult) -> float:
    """Return 0-1 score based on keyword overlap with name + description."""
    if not query.keywords:
        return 0.0

    text = f"{result.name} {result.description}".lower()
    hits = sum(1 for kw in query.keywords if kw.lower() in text)
    return min(hits / len(query.keywords), 1.0)


def _description_similarity(query: SearchQuery, result: SearchResult) -> float:
    """Simple token-overlap similarity between query keywords and description.

    Uses Jaccard-like coefficient over lowercased word tokens.  This avoids
    heavy NLP dependencies while still capturing semantic overlap.
    """
    if not query.keywords or not result.description:
        return 0.0

    query_tokens = {kw.lower() for kw in query.keywords}
    desc_tokens = set(re.findall(r"[a-z0-9\uac00-\ud7a3]+", result.description.lower()))

    if not desc_tokens:
        return 0.0

    intersection = query_tokens & desc_tokens
    union = query_tokens | desc_tokens
    return len(intersection) / len(union) if union else 0.0


def _recency_score(result: SearchResult) -> float:
    """Return 0-1 score based on how recently the skill was updated.

    Extracts ``updated_at`` from the result metadata embedded in ``source``
    field (ISO-8601 string) or falls back to 0.5 (neutral).
    """
    # Try to extract date from metadata encoded in source or description
    iso_pattern = re.compile(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?")
    match = iso_pattern.search(getattr(result, "_raw_updated_at", ""))
    if not match:
        return 0.5  # neutral when unknown

    try:
        updated = datetime.fromisoformat(match.group().replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_old = (now - updated).days
        # 0 days -> 1.0, 365 days -> ~0.0
        return max(0.0, 1.0 - days_old / 365.0)
    except (ValueError, TypeError):
        return 0.5


def _license_score(result: SearchResult) -> float:
    """Return 1.0 for compatible licenses, 0.3 for unknown, 0.0 for incompatible."""
    lic = getattr(result, "_raw_license", "").lower().strip()
    if not lic:
        return 0.3  # unknown
    if lic in _COMPATIBLE_LICENSES:
        return 1.0
    return 0.0


def compute_final_score(query: SearchQuery, result: SearchResult) -> float:
    """Weighted ranking score.

    Weights:
        keyword matching  : 0.4
        description sim   : 0.3
        recency           : 0.2
        license compat    : 0.1
    """
    return (
        0.4 * _keyword_match_score(query, result)
        + 0.3 * _description_similarity(query, result)
        + 0.2 * _recency_score(result)
        + 0.1 * _license_score(result)
    )


# ---------------------------------------------------------------------------
# SkillSearcher
# ---------------------------------------------------------------------------

# Default SkillsMP API base URL (configurable via env)
_SKILLSMP_API_BASE = os.environ.get(
    "SKILLSMP_API_BASE", "https://skillsmp.com/api/v1"
)

# Request timeout in seconds
_REQUEST_TIMEOUT = int(os.environ.get("SKILLSMP_TIMEOUT", "15"))


class SkillSearcher:
    """Search the SkillsMP marketplace for skills matching a query."""

    def __init__(self, api_base: str | None = None, timeout: int | None = None):
        self.api_base = (api_base or _SKILLSMP_API_BASE).rstrip("/")
        self.timeout = timeout if timeout is not None else _REQUEST_TIMEOUT

    # ----- public API -----

    def search(self, query: SearchQuery, top_k: int = 3) -> list[SearchResult]:
        """Search SkillsMP and return the top *top_k* ranked results.

        Falls back to GitHub search if the primary API is unreachable.
        """
        raw_results = self._call_skillsmp_api(query)

        if not raw_results:
            logger.info("SkillsMP API returned no results; trying GitHub fallback")
            raw_results = self._github_fallback(query)

        # Compute scores and rank
        for r in raw_results:
            r.score = compute_final_score(query, r)

        raw_results.sort(key=lambda r: r.score, reverse=True)
        return raw_results[:top_k]

    # ----- private helpers -----

    def _call_skillsmp_api(self, query: SearchQuery) -> list[SearchResult]:
        """Call SkillsMP REST API ``/skills/search`` endpoint."""
        search_terms = " ".join(query.keywords)
        if query.domain:
            search_terms += f" {query.domain}"

        params = urllib.parse.urlencode({"q": search_terms, "limit": "10"})
        url = f"{self.api_base}/skills/search?{params}"

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "management-skill-integrator/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())

            return self._parse_skillsmp_response(data)

        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            logger.warning("SkillsMP API call failed: %s", exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unexpected error calling SkillsMP API: %s", exc)
            return []

    def _parse_skillsmp_response(self, data: dict | list) -> list[SearchResult]:
        """Normalize the SkillsMP JSON response into ``SearchResult`` objects."""
        results: list[SearchResult] = []

        # Handle both {"results": [...]} and bare list
        items = data if isinstance(data, list) else data.get("results", data.get("skills", []))

        for item in items:
            if not isinstance(item, dict):
                continue

            sr = SearchResult(
                name=str(item.get("name", "")),
                description=str(item.get("description", "")),
                url=str(item.get("url", item.get("repository_url", item.get("html_url", "")))),
                score=0.0,
                source="skillsmp",
            )

            # Stash raw metadata for scoring helpers
            sr._raw_updated_at = str(item.get("updated_at", ""))  # type: ignore[attr-defined]
            sr._raw_license = str(item.get("license", item.get("license_key", "")))  # type: ignore[attr-defined]

            if sr.name:
                results.append(sr)

        return results

    def _github_fallback(self, query: SearchQuery) -> list[SearchResult]:
        """Search GitHub for agent-skills repositories as a fallback."""
        search_terms = "+".join(query.keywords + ["agent-skills"])
        url = (
            f"https://api.github.com/search/repositories"
            f"?q={urllib.parse.quote(search_terms)}&sort=stars&per_page=10"
        )

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "management-skill-integrator/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())

            results: list[SearchResult] = []
            for item in data.get("items", []):
                sr = SearchResult(
                    name=str(item.get("name", "")),
                    description=str(item.get("description", "") or ""),
                    url=str(item.get("html_url", "")),
                    score=0.0,
                    source="github",
                )
                sr._raw_updated_at = str(item.get("updated_at", ""))  # type: ignore[attr-defined]
                license_info = item.get("license") or {}
                sr._raw_license = str(license_info.get("spdx_id", ""))  # type: ignore[attr-defined]

                if sr.name:
                    results.append(sr)

            return results

        except Exception as exc:  # noqa: BLE001
            logger.warning("GitHub fallback search failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# SkillDownloader
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3


class SkillDownloader:
    """Download a skill from a search result into a local directory."""

    def __init__(self, max_retries: int = _MAX_RETRIES):
        self.max_retries = max_retries

    def download(
        self,
        result: SearchResult,
        target_dir: str,
    ) -> DownloadedSkill:
        """Download the skill referenced by *result* into *target_dir*.

        Tries git clone first; falls back to HTTP tarball download.
        Retries up to ``max_retries`` times on failure.

        Raises ``RuntimeError`` if all attempts fail.
        """
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)

        errors: list[str] = []

        for attempt in range(1, self.max_retries + 1):
            try:
                local_path = self._try_git_clone(result, target)
                return self._build_downloaded_skill(result, local_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"git clone attempt {attempt}: {exc}")
                logger.info("git clone attempt %d failed: %s", attempt, exc)

            try:
                local_path = self._try_http_download(result, target)
                return self._build_downloaded_skill(result, local_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"HTTP download attempt {attempt}: {exc}")
                logger.info("HTTP download attempt %d failed: %s", attempt, exc)

            if attempt < self.max_retries:
                time.sleep(1)

        raise RuntimeError(
            f"Failed to download '{result.name}' after {self.max_retries} "
            f"attempts. Errors: {'; '.join(errors)}"
        )

    def download_first_successful(
        self,
        candidates: list[SearchResult],
        target_dir: str,
    ) -> DownloadedSkill:
        """Try downloading each candidate in order; return the first success.

        Raises ``RuntimeError`` if none succeed.
        """
        errors: list[str] = []
        for candidate in candidates:
            try:
                return self.download(candidate, target_dir)
            except RuntimeError as exc:
                errors.append(f"{candidate.name}: {exc}")
                logger.info("Candidate '%s' failed, trying next", candidate.name)

        raise RuntimeError(
            f"All {len(candidates)} candidates failed to download. "
            f"Errors: {'; '.join(errors)}"
        )

    # ----- private helpers -----

    def _try_git_clone(self, result: SearchResult, target: Path) -> str:
        """Clone a git repository into target/<name>."""
        git_url = self._resolve_git_url(result.url)
        if not git_url:
            raise ValueError(f"Cannot derive git URL from '{result.url}'")

        dest = target / self._safe_dirname(result.name)
        if dest.exists():
            shutil.rmtree(dest)

        proc = subprocess.run(
            ["git", "clone", "--depth", "1", git_url, str(dest)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed: {proc.stderr.strip()}")

        # Remove .git directory to save space
        git_dir = dest / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)

        return str(dest)

    def _try_http_download(self, result: SearchResult, target: Path) -> str:
        """Download a tarball/zip from the URL and extract it."""
        download_url = self._resolve_archive_url(result.url)
        if not download_url:
            raise ValueError(f"Cannot derive archive URL from '{result.url}'")

        dest = target / self._safe_dirname(result.name)
        if dest.exists():
            shutil.rmtree(dest)

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "management-skill-integrator/1.0"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(tmp_path, "wb") as f:
                    f.write(resp.read())

            # Extract
            dest.mkdir(parents=True, exist_ok=True)
            with tarfile.open(tmp_path, "r:gz") as tar:
                # Strip top-level directory if present
                members = tar.getmembers()
                prefix = self._common_prefix(members)
                for member in members:
                    if member.name == prefix.rstrip("/"):
                        continue
                    if prefix:
                        member.name = member.name[len(prefix):]
                    if member.name:
                        tar.extract(member, str(dest), filter="data")

            return str(dest)

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _resolve_git_url(self, url: str) -> str:
        """Convert various URL formats to a clonable git URL."""
        if not url:
            return ""
        # GitHub HTTPS
        gh_match = re.match(r"https?://github\.com/([\w\-\.]+/[\w\-\.]+)", url)
        if gh_match:
            return f"https://github.com/{gh_match.group(1)}.git"
        # Already a .git URL
        if url.endswith(".git"):
            return url
        # Generic https that might be a repo
        if url.startswith("https://") and "/" in url.split("//", 1)[1]:
            return url if url.endswith(".git") else f"{url.rstrip('/')}.git"
        return ""

    def _resolve_archive_url(self, url: str) -> str:
        """Derive a tarball download URL (GitHub-style)."""
        gh_match = re.match(r"https?://github\.com/([\w\-\.]+/[\w\-\.]+)", url)
        if gh_match:
            return f"https://github.com/{gh_match.group(1)}/archive/refs/heads/main.tar.gz"
        return ""

    def _common_prefix(self, members: list) -> str:
        """Find the common top-level directory in tarball members."""
        names = [m.name for m in members if m.name]
        if not names:
            return ""
        parts = [n.split("/")[0] for n in names]
        if len(set(parts)) == 1:
            return parts[0] + "/"
        return ""

    def _safe_dirname(self, name: str) -> str:
        """Sanitize a skill name for use as a directory name."""
        safe = re.sub(r"[^\w\-]", "-", name.lower())
        safe = re.sub(r"-+", "-", safe).strip("-")
        return safe or "skill"

    def _build_downloaded_skill(
        self, result: SearchResult, local_path: str
    ) -> DownloadedSkill:
        """Create a ``DownloadedSkill`` from the downloaded files."""
        fmt = self._detect_format(local_path)
        return DownloadedSkill(
            name=result.name,
            local_path=local_path,
            format_type=fmt,
            metadata={
                "source": result.source,
                "url": result.url,
                "score": result.score,
                "description": result.description,
            },
        )

    def _detect_format(self, local_path: str) -> str:
        """Detect whether the downloaded package is Agent Skills, MCP, or npm."""
        p = Path(local_path)

        # Agent Skills: has SKILL.md
        if (p / "SKILL.md").exists():
            return "agent_skills"

        # MCP server: has mcp.json or server.py/server.ts
        for mcp_marker in ("mcp.json", "server.py", "server.ts"):
            if (p / mcp_marker).exists():
                return "mcp_server"

        # npm package: has package.json
        if (p / "package.json").exists():
            return "npm_package"

        return "agent_skills"  # default assumption


# ---------------------------------------------------------------------------
# Convenience / module-level helpers
# ---------------------------------------------------------------------------


def search_and_download(
    query: SearchQuery,
    target_dir: str,
    top_k: int = 3,
) -> DownloadedSkill:
    """High-level helper: search, rank, and download the best candidate.

    Returns the first successfully downloaded skill from the top *top_k*
    ranked candidates.
    """
    searcher = SkillSearcher()
    candidates = searcher.search(query, top_k=top_k)

    if not candidates:
        raise RuntimeError(
            f"No search results for keywords: {query.keywords}"
        )

    downloader = SkillDownloader()
    return downloader.download_first_successful(candidates, target_dir)
