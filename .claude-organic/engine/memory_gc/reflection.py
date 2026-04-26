"""Reflection — 같은 topic 누적 importance >= threshold 시 LLM 합성.

LLM 호출은 Claude Code CLI 헤드리스 (claude -p ... --output-format json).
실패는 silent — 합성 없이 후보만 반환.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .core import MemoryFile, parse_memory_file, write_memory_file
from .dedup import _tokens, _jaccard
from .paths import GCConfig

CLUSTER_OVERLAP: float = 0.35  # dedup 보다 느슨 — 합성은 "관련 메모리" 묶기
CLAUDE_CLI: str = 'claude'
HEADLESS_TIMEOUT: int = 90


@dataclass(frozen=True)
class ReflectionCluster:
    type: str
    members: list[MemoryFile]
    cumulative_importance: int


def find_clusters(memories: list[MemoryFile], threshold: int) -> list[ReflectionCluster]:
    """type 별로 토큰 유사도 기반 클러스터링. 누적 importance 가 threshold 이상인 클러스터만 반환."""
    by_type: dict[str, list[MemoryFile]] = {}
    for m in memories:
        by_type.setdefault(m.type, []).append(m)
    clusters: list[ReflectionCluster] = []
    for t, items in by_type.items():
        used: set[Path] = set()
        for i, anchor in enumerate(items):
            if anchor.path in used:
                continue
            anchor_tokens = _tokens(anchor.description) | _tokens(anchor.name)
            cluster = [anchor]
            used.add(anchor.path)
            for j in range(i + 1, len(items)):
                cand = items[j]
                if cand.path in used:
                    continue
                cand_tokens = _tokens(cand.description) | _tokens(cand.name)
                if _jaccard(anchor_tokens, cand_tokens) >= CLUSTER_OVERLAP:
                    cluster.append(cand)
                    used.add(cand.path)
            cum = sum(m.importance for m in cluster)
            if len(cluster) >= 2 and cum >= threshold:
                clusters.append(ReflectionCluster(type=t, members=cluster, cumulative_importance=cum))
    return clusters


def _build_prompt(cluster: ReflectionCluster) -> str:
    lines = [
        '다음은 메모리 파일들입니다. 동일 주제로 중복·파편화되어 있어 하나의 추상 메모리로 합성해주세요.',
        '',
        '요구 사항:',
        '- 합성 결과는 frontmatter (name, description, type, importance) 와 본문으로 구성',
        '- name 은 합성 메모리의 짧은 식별자 (snake_case 단어 2~4개)',
        '- description 은 한 줄 요약',
        '- importance 는 1~10, 가장 중요한 원본 importance 와 같거나 1 높게',
        '- 본문은 Markdown, 핵심 인사이트 + Why/How 구조 권장',
        '- 응답은 JSON 으로만: {"name": "...", "description": "...", "importance": N, "body": "..."}',
        '',
        '## 원본 메모리',
        '',
    ]
    for i, m in enumerate(cluster.members, start=1):
        lines.append(f'### [{i}] {m.name} (importance={m.importance})')
        lines.append(f'description: {m.description}')
        lines.append('')
        lines.append(m.body.strip())
        lines.append('')
    return '\n'.join(lines)


def _invoke_claude(prompt: str) -> dict | None:
    """Claude Code CLI 헤드리스 호출. 결과 JSON 파싱.

    실패 시 None.
    """
    cmd = [CLAUDE_CLI, '-p', prompt, '--output-format', 'json',
           '--allowed-tools', 'Read,Write']
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=HEADLESS_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    # claude -p --output-format json 출력 구조: {"result": "...", ...}
    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    body = envelope.get('result', '') if isinstance(envelope, dict) else ''
    # body 안에 우리가 요청한 JSON 이 들어있다 — 파싱
    body = body.strip()
    if body.startswith('```'):
        # 코드펜스 제거
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
    """합성 결과를 신규 메모리 파일로 저장 + 원본은 archive/synthesized/ 이동."""
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
    # 원본 archive 이동
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
