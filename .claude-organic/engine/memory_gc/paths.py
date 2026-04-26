"""메모리 GC 경로·환경변수 단일 진실 공급원.

memory_dir 자동 계산: ~/.claude/projects/<sanitized-cwd>/memory/
환경변수 override: MEMORY_GC_DIR
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


TYPE_DIRS: tuple[str, ...] = ('user', 'feedback', 'project', 'reference')
ARCHIVE_SUBDIRS: tuple[str, ...] = ('merged', 'synthesized', 'stale')

INDEX_FILENAME: str = 'MEMORY.md'
GC_META_DIR: str = '.gc'
LAST_RUN_FILENAME: str = 'last_run.json'

INDEX_BEGIN: str = '<!-- AUTO_INDEX_BEGIN -->'
INDEX_END: str = '<!-- AUTO_INDEX_END -->'


def _sanitize_cwd(cwd: str) -> str:
    return cwd.replace('/', '-')


def default_memory_dir(cwd: str | None = None) -> Path:
    cwd = cwd or os.getcwd()
    return Path.home() / '.claude' / 'projects' / _sanitize_cwd(cwd) / 'memory'


@dataclass(frozen=True)
class GCConfig:
    memory_dir: Path
    hot_limit: int = 30
    auto_triggers: tuple[str, ...] = ('cron', 'session', 'size')
    cron_time: str = '03:00'
    size_threshold: int = 50
    archive_ttl_days: int = 90
    reflection_threshold: int = 30

    @property
    def index_path(self) -> Path:
        return self.memory_dir / INDEX_FILENAME

    @property
    def archive_dir(self) -> Path:
        return self.memory_dir / 'archive'

    @property
    def gc_meta_dir(self) -> Path:
        return self.memory_dir / GC_META_DIR

    @property
    def last_run_path(self) -> Path:
        return self.gc_meta_dir / LAST_RUN_FILENAME

    def type_dir(self, type_name: str) -> Path:
        return self.memory_dir / type_name

    def archive_subdir(self, kind: str) -> Path:
        return self.archive_dir / kind


def _parse_int(env_value: str | None, default: int) -> int:
    if env_value is None or env_value.strip() == '':
        return default
    try:
        return int(env_value.strip())
    except ValueError:
        return default


def _parse_csv(env_value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if env_value is None:
        return default
    parts = tuple(p.strip() for p in env_value.split(',') if p.strip())
    return parts if parts else ()


def load_config(env: dict[str, str] | None = None, cwd: str | None = None) -> GCConfig:
    """환경변수에서 GCConfig 를 로드한다.

    .claude-organic/.settings 가 미리 환경에 로드되어 있다고 가정.
    미설정 시 기본값 사용.
    """
    e = env if env is not None else os.environ
    raw_dir = e.get('MEMORY_GC_DIR', '').strip()
    memory_dir = Path(raw_dir).expanduser() if raw_dir else default_memory_dir(cwd)
    return GCConfig(
        memory_dir=memory_dir,
        hot_limit=_parse_int(e.get('MEMORY_GC_HOT_LIMIT'), 30),
        auto_triggers=_parse_csv(e.get('MEMORY_GC_AUTO_TRIGGERS'), ('cron', 'session', 'size')),
        cron_time=e.get('MEMORY_GC_CRON', '03:00').strip() or '03:00',
        size_threshold=_parse_int(e.get('MEMORY_GC_SIZE_THRESHOLD'), 50),
        archive_ttl_days=_parse_int(e.get('MEMORY_GC_ARCHIVE_TTL_DAYS'), 90),
        reflection_threshold=_parse_int(e.get('MEMORY_GC_REFLECTION_THRESHOLD'), 30),
    )


def ensure_skeleton(cfg: GCConfig) -> None:
    """디렉터리 스켈레톤(type/archive/.gc) 을 멱등 생성."""
    cfg.memory_dir.mkdir(parents=True, exist_ok=True)
    for t in TYPE_DIRS:
        cfg.type_dir(t).mkdir(exist_ok=True)
    cfg.archive_dir.mkdir(exist_ok=True)
    for k in ARCHIVE_SUBDIRS:
        cfg.archive_subdir(k).mkdir(exist_ok=True)
    cfg.gc_meta_dir.mkdir(exist_ok=True)
