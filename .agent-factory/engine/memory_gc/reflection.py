"""Reflection — LLM-as-clusterer based semantic clustering + LLM synthesis.

2-step flow:
  1) Send metadata (name/description/importance/type) of all memories to LLM
     Request to group the same topic → Only clusters with cumulative_importance >= threshold are accepted.
  2) Request synthesis to LLM including the text of each cluster → Generate composite copy.

All LLM calls are Claude Code CLI headless (claude -p ... --output-format json).
Failure is silent — only returns candidates without synthesis.

Older versions of jaccard-based find_clusters had a threshold of 0.35 in the Korean short description:
Too tight, resulting in zero cluster problem. Replaced with semantic-based judgment with LLM-as-clusterer.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .core import MemoryFile, parse_memory_file, write_memory_file
from .paths import GCConfig

CLAUDE_CLI: str = 'claude'
HEADLESS_TIMEOUT: int = 90
CLUSTERING_TIMEOUT: int = 60  # metadata only — lighter than synthesis


@dataclass(frozen=True)
class ReflectionCluster:
    type: str
    members: list[MemoryFile]
    cumulative_importance: int
    reason: str = ''


def _build_clustering_prompt(items: list[dict], threshold: int) -> str:
    return (
        'The following is a list of memory metadata. Group memories that can be grouped into the same topic. \n \n'
        'Rule: \n'
        '- Group memories that semantically deal with the same topic, issue, or decision into one cluster \n'
        f'- Returns only groups where the cumulative_importance (sum of member importance) of each cluster is {threshold} or higher \n'
        '- Do not return exclusive memory (cluster size 1) \n'
        '- Regardless of Korean/English, meaning-based judgment (topic matching, not vocabulary matching) \n'
        '- Do not bundle too much — if you are not confident, exclude the cluster \n \n'
        'Response is in JSON only (no codefencing): \n'
        '{"clusters": [{"members": ["filename1.md", "filename2.md", ...], "reason": "One line of group reason"}, ...]} \n \n'
        '## Memory metadata \n \n'
        + json.dumps(items, ensure_ascii=False, indent=2)
    )


def find_clusters(memories: list[MemoryFile], threshold: int) -> list[ReflectionCluster]:
    """Semantic-based clustering with LLM-as-clusterer.

    Only metadata is passed in one LLM call and the grouping results are received.
    Clusters with cumulative_importance < threshold or members < 2 have their own filter.
    When LLM call fails, an empty list is returned (silent).
    """
    if not memories:
        return []
    items = [
        {
            'name': m.path.name,
            'type': m.type,
            'importance': m.importance,
            'description': m.description,
        }
        for m in memories
    ]
    prompt = _build_clustering_prompt(items, threshold)
    response = _invoke_claude(prompt, timeout=CLUSTERING_TIMEOUT)
    if not response or 'clusters' not in response:
        return []

    by_name: dict[str, MemoryFile] = {m.path.name: m for m in memories}
    out: list[ReflectionCluster] = []
    for c in response.get('clusters', []) or []:
        member_names = c.get('members') or []
        members = [by_name[n] for n in member_names if n in by_name]
        if len(members) < 2:
            continue
        cum = sum(m.importance for m in members)
        if cum < threshold:
            continue
        # Member type majority vote (tie is the first meeting type)
        type_counts: dict[str, int] = {}
        for m in members:
            type_counts[m.type] = type_counts.get(m.type, 0) + 1
        cluster_type = max(type_counts.items(), key=lambda kv: kv[1])[0]
        out.append(ReflectionCluster(
            type=cluster_type,
            members=members,
            cumulative_importance=cum,
            reason=str(c.get('reason') or ''),
        ))
    return out


def _build_prompt(cluster: ReflectionCluster) -> str:
    lines = [
        'Below are the memory files. Please synthesize them into one abstract memory as they are duplicated and fragmented on the same topic.',
        '',
        'Requirements:',
        '- The synthesis result consists of frontmatter (name, description, type, importance) and body.',
        '- name is a short identifier of the synthetic memory (2 to 4 snake_case words)',
        '- description is a one-line summary',
        '- importance is 1 to 10, equal to or 1 higher than the most important original importance.',
        '- Markdown text, core insights + why/how structure recommended',
        '- Response is in JSON only: {"name": "...", "description": "...", "importance": N, "body": "..."}',
        '',
        '## Original memory',
        '',
    ]
    for i, m in enumerate(cluster.members, start=1):
        lines.append(f'### [{i}] {m.name} (importance={m.importance})')
        lines.append(f'description: {m.description}')
        lines.append('')
        lines.append(m.body.strip())
        lines.append('')
    return '\n'.join(lines)


def _invoke_claude(prompt: str, *, timeout: int = HEADLESS_TIMEOUT) -> dict | None:
    """Claude Code CLI headless calls. Parse the resulting JSON.

    None on failure.
    """
    cmd = [CLAUDE_CLI, '-p', prompt, '--output-format', 'json',
           '--allowed-tools', 'Read,Write']
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    # claude -p --output-format json output structure: {"result": "...", ...}
    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    body = envelope.get('result', '') if isinstance(envelope, dict) else ''
    # The body contains the JSON we requested — parsing
    body = body.strip()
    if body.startswith('```'):
        # Codefence removal
        lines = body.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        body = '\n'.join(lines)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _apply_synthesis(cfg: GCConfig, cluster: ReflectionCluster, payload: dict) -> Path | None:
    """Save the synthesis result as a new memory file + move the original to archive/synthesized/."""
    name = str(payload.get('name', '')).strip()
    description = str(payload.get('description', '')).strip()
    body = str(payload.get('body', '')).strip()
    importance = int(payload.get('importance', max((m.importance for m in cluster.members), default=5)))
    if not name or not description or not body:
        return None
    type_dir = cfg.type_dir(cluster.type)
    type_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    dest = type_dir / f'synthesis_{ts}_{name}.md'
    synthesis_of = [str(m.path.relative_to(cfg.memory_dir)) for m in cluster.members]
    mem = MemoryFile(
        path=dest,
        name=name,
        description=description,
        type=cluster.type,
        importance=importance,
        last_accessed=dt.date.today().isoformat(),
        access_count=0,
        synthesis_of=synthesis_of,
        body=body,
        raw_frontmatter={'name': name, 'description': description, 'type': cluster.type},
    )
    write_memory_file(mem)
    # Move original archive
    archive_dir = cfg.archive_subdir('synthesized')
    archive_dir.mkdir(parents=True, exist_ok=True)
    for m in cluster.members:
        if not m.path.exists():
            continue
        target = archive_dir / m.path.name
        if target.exists():
            target = archive_dir / f'{m.path.stem}.{int(m.path.stat().st_mtime)}{m.path.suffix}'
        shutil.move(str(m.path), str(target))
    return dest


@dataclass
class ReflectionResult:
    cluster_count: int
    synthesized: list[Path]
    skipped: int

    def summary(self) -> str:
        return f'clusters={self.cluster_count} synthesized={len(self.synthesized)} skipped={self.skipped}'


def run_reflection(cfg: GCConfig, memories: list[MemoryFile], *, apply: bool) -> ReflectionResult:
    clusters = find_clusters(memories, cfg.reflection_threshold)
    if not apply:
        return ReflectionResult(cluster_count=len(clusters), synthesized=[], skipped=len(clusters))
    synthesized: list[Path] = []
    skipped = 0
    for cluster in clusters:
        prompt = _build_prompt(cluster)
        payload = _invoke_claude(prompt)
        if not payload:
            skipped += 1
            continue
        dest = _apply_synthesis(cfg, cluster, payload)
        if dest is None:
            skipped += 1
            continue
        synthesized.append(dest)
    return ReflectionResult(cluster_count=len(clusters), synthesized=synthesized, skipped=skipped)
