"""MemoryFile model + frontmatter parsing/update + index regeneration.

frontmatter scheme extension:
  name, description, type (default)
  importance: 1~10 (3 axis scores, Claude self-assessment default 5)
  last_accessed: YYYY-MM-DD (3-axis score recency)
  access_count: int (3-axis score)
  synthesis_of: [path, ...] (original path array when reflection synthesis)
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .paths import (
    GCConfig, INDEX_BEGIN, INDEX_END, TYPE_DIRS, ARCHIVE_SUBDIRS,
)

FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)
TODAY = lambda: dt.date.today().isoformat()  # noqa: E731


@dataclass
class MemoryFile:
    path: Path                      # absolute path
    name: str                       # frontmatter.name
    description: str
    type: str                       # user|feedback|project|reference
    importance: int = 5
    last_accessed: str = ''
    access_count: int = 0
    synthesis_of: list[str] = field(default_factory=list)
    body: str = ''
    raw_frontmatter: dict = field(default_factory=dict)

    @property
    def relative(self) -> str:
        """Relative path relative to memory_dir (for index links)."""
        return self.path.name if self.path.parent.name in ('memory', '') else (
            f'{self.path.parent.name}/{self.path.name}'
        )

    @property
    def is_archived(self) -> bool:
        parts = self.path.parts
        return 'archive' in parts


def _parse_frontmatter_block(block: str) -> dict:
    """A lightweight YAML parser — limited to our frontmatter types.

    Supported: scalar(int/str), list ([a, b]), multi-line string (>- not supported).
    Minimal implementation with PyYAML dependency avoidance.
    """
    out: dict = {}
    for line in block.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip()
        if val.startswith('[') and val.endswith(']'):
            inner = val[1:-1].strip()
            out[key] = [s.strip().strip('"').strip("'") for s in inner.split(',') if s.strip()] if inner else []
        elif val.lower() in ('true', 'false'):
            out[key] = (val.lower() == 'true')
        else:
            try:
                out[key] = int(val)
            except ValueError:
                out[key] = val.strip('"').strip("'")
    return out


def _serialize_frontmatter(fm: dict) -> str:
    keys_order = (
        'name', 'description', 'type',
        'importance', 'last_accessed', 'access_count', 'synthesis_of',
        'originSessionId',
    )
    lines: list[str] = ['---']
    for k in keys_order:
        if k not in fm:
            continue
        v = fm[k]
        if isinstance(v, list):
            inner = ', '.join(str(x) for x in v)
            lines.append(f'{k}: [{inner}]')
        elif isinstance(v, bool):
            lines.append(f'{k}: {"true" if v else "false"}')
        elif isinstance(v, int):
            lines.append(f'{k}: {v}')
        else:
            lines.append(f'{k}: {v}')
    for k, v in fm.items():
        if k in keys_order:
            continue
        if isinstance(v, list):
            lines.append(f'{k}: [{", ".join(str(x) for x in v)}]')
        else:
            lines.append(f'{k}: {v}')
    lines.append('---')
    return '\n'.join(lines) + '\n'


def parse_memory_file(path: Path) -> MemoryFile | None:
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return None
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm = _parse_frontmatter_block(m.group(1))
    body = text[m.end():]
    return MemoryFile(
        path=path,
        name=str(fm.get('name', path.stem)),
        description=str(fm.get('description', '')),
        type=str(fm.get('type', 'project')),
        importance=int(fm.get('importance', 5)),
        last_accessed=str(fm.get('last_accessed', '')),
        access_count=int(fm.get('access_count', 0)),
        synthesis_of=list(fm.get('synthesis_of', [])),
        body=body,
        raw_frontmatter=fm,
    )


def write_memory_file(mem: MemoryFile) -> None:
    """Rewrite frontmatter + body to disk.

    If raw_frontmatter exists, overwrite only the extended fields there.
    If it does not exist, create a new one with default fields.
    """
    fm = dict(mem.raw_frontmatter) if mem.raw_frontmatter else {}
    fm.update({
        'name': mem.name,
        'description': mem.description,
        'type': mem.type,
        'importance': mem.importance,
        'last_accessed': mem.last_accessed or TODAY(),
        'access_count': mem.access_count,
    })
    if mem.synthesis_of:
        fm['synthesis_of'] = mem.synthesis_of
    elif 'synthesis_of' in fm:
        del fm['synthesis_of']
    text = _serialize_frontmatter(fm) + mem.body.lstrip('\n')
    if not text.endswith('\n'):
        text += '\n'
    mem.path.write_text(text, encoding='utf-8')


def scan_memories(cfg: GCConfig, *, include_archive: bool = False) -> list[MemoryFile]:
    """Scans all memory directories.

    Collect all type directories + flat files (compatible before migration).
    archive is included as an option.
    """
    out: list[MemoryFile] = []
    if not cfg.memory_dir.is_dir():
        return out
    seen: set[Path] = set()
    # scan type directory first
    for t in TYPE_DIRS:
        d = cfg.type_dir(t)
        if not d.is_dir():
            continue
        for p in sorted(d.glob('*.md')):
            mem = parse_memory_file(p)
            if mem is not None:
                out.append(mem)
                seen.add(p.resolve())
    # Also collect flat files before migration (except MEMORY.md)
    for p in sorted(cfg.memory_dir.glob('*.md')):
        if p.name == 'MEMORY.md' or p.resolve() in seen:
            continue
        mem = parse_memory_file(p)
        if mem is not None:
            out.append(mem)
    if include_archive:
        for k in ARCHIVE_SUBDIRS:
            d = cfg.archive_subdir(k)
            if not d.is_dir():
                continue
            for p in sorted(d.glob('*.md')):
                mem = parse_memory_file(p)
                if mem is not None:
                    out.append(mem)
    return out


# ---------------------------------------------------------------------------
# Regenerate index
# ---------------------------------------------------------------------------

CATEGORY_ORDER: tuple[tuple[str, str], ...] = (
    ('user', 'User'),
    ('feedback', 'Feedback'),
    ('project', 'Project'),
    ('reference', 'Reference'),
)


def _format_index_block(memories_by_type: dict[str, list[MemoryFile]]) -> str:
    lines: list[str] = []
    for type_key, label in CATEGORY_ORDER:
        items = memories_by_type.get(type_key, [])
        if not items:
            continue
        lines.append(f'## {label}')
        lines.append('')
        for m in items:
            desc = m.description or '(no description)'
            lines.append(f'- [{m.name}]({m.relative}) — {desc}')
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def regenerate_index(cfg: GCConfig, memories: list[MemoryFile]) -> None:
    """Replace AUTO_INDEX area in MEMORY.md. External user areas are preserved.

    If the file does not exist or there is no marker, create a new one with only header + automatic area.
    """
    by_type: dict[str, list[MemoryFile]] = {t: [] for t, _ in CATEGORY_ORDER}
    # Sort descending by importance·last_accessed
    for m in sorted(memories, key=lambda x: (-x.importance, x.last_accessed or ''), reverse=False):
        if m.type in by_type:
            by_type[m.type].append(m)
    block = _format_index_block(by_type)
    existing = ''
    if cfg.index_path.exists():
        existing = cfg.index_path.read_text(encoding='utf-8')
    if INDEX_BEGIN in existing and INDEX_END in existing:
        before = existing.split(INDEX_BEGIN, 1)[0]
        after = existing.split(INDEX_END, 1)[1]
        new_text = (
            before.rstrip() + '\n\n'
            + INDEX_BEGIN + '\n'
            + block.rstrip() + '\n'
            + INDEX_END + '\n'
            + after.lstrip()
        )
    else:
        header = '# Memory \n \n > The automatic area of ​​the index is updated by `flow-memory-gc run`. \n > Notes added outside the marker will be preserved. \n \n'
        manual_keep = ''
        if existing:
            # If there is an existing MEMORY.md but no marker → preserve the existing text as Manual Notes
            stripped = existing.lstrip()
            if stripped.startswith('# '):
                # Keep only the body text after the first header
                stripped = stripped.split('\n', 1)[1] if '\n' in stripped else ''
            manual_keep = '\n\n## Manual Notes\n\n' + stripped.strip() + '\n'
        new_text = (
            header
            + INDEX_BEGIN + '\n'
            + block.rstrip() + '\n'
            + INDEX_END + '\n'
            + manual_keep
        )
    cfg.index_path.write_text(new_text, encoding='utf-8')
