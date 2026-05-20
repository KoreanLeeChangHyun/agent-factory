"""Reflection — LLM-as-clusterer 기반 의미 클러스터링 + LLM 합성.

2-step 흐름:
  1) 모든 메모리의 metadata (name/description/importance/type) 를 LLM 에 보내
     같은 토픽 그룹으로 묶도록 요청 → cumulative_importance >= threshold 인 클러스터만 채택.
  2) 각 클러스터의 본문을 포함하여 LLM 에 합성 요청 → 합성본 생성.

LLM 호출은 모두 Claude Code CLI 헤드리스 (claude -p ... --output-format json).
실패는 silent — 합성 없이 후보만 반환.

이전 버전의 jaccard 기반 find_clusters 는 한국어 짧은 description 에서 임계 0.35 가
너무 빡빡하여 클러스터 0개 문제를 초래. LLM-as-clusterer 로 의미 기반 판단으로 교체.
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
CLUSTERING_TIMEOUT: int = 60  # metadata 만 — 합성보다 가벼움


@dataclass(frozen=True)
class ReflectionCluster:
    type: str
    members: list[MemoryFile]
    cumulative_importance: int
    reason: str = ''


def _build_clustering_prompt(items: list[dict], threshold: int) -> str:
    return (
        '다음은 메모리 metadata 리스트입니다. 같은 토픽으로 묶을 수 있는 메모리들을 그룹화하세요.\n\n'
        '규칙:\n'
        '- 의미적으로 같은 주제·이슈·결정사항을 다루는 메모리들을 한 클러스터로 묶기\n'
        f'- 각 클러스터의 cumulative_importance (멤버 importance 합) 가 {threshold} 이상인 그룹만 반환\n'
        '- 단독 메모리(클러스터 크기 1)는 반환하지 말 것\n'
        '- 한국어/영어 무관, 의미 기반 판단 (어휘 매칭이 아닌 토픽 매칭)\n'
        '- 무리하게 묶지 말 것 — 확신이 약하면 클러스터 제외\n\n'
        '응답은 JSON 으로만 (코드펜스 금지):\n'
        '{"clusters": [{"members": ["filename1.md", "filename2.md", ...], "reason": "그룹 사유 한 줄"}, ...]}\n\n'
        '## 메모리 metadata\n\n'
        + json.dumps(items, ensure_ascii=False, indent=2)
    )


def find_clusters(memories: list[MemoryFile], threshold: int) -> list[ReflectionCluster]:
    """LLM-as-clusterer 로 의미 기반 클러스터링.

    metadata 만 한 번의 LLM 호출로 전달하고 그룹화 결과를 받는다.
    cumulative_importance < threshold 또는 멤버 < 2 인 클러스터는 자체 필터.
    LLM 호출 실패 시 빈 리스트 반환 (silent).
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
        # 멤버 type 다수결 (동률은 첫 만난 type)
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


def _invoke_claude(prompt: str, *, timeout: int = HEADLESS_TIMEOUT) -> dict | None:
    """Claude Code CLI 헤드리스 호출. 결과 JSON 파싱.

    실패 시 None.
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
