"""flow-memory-gc 진입점 — argparse 기반.

서브커맨드:
  migrate         디렉터리 재편 + frontmatter 확장 (1회성, 멱등)
  run             GC 사이클 적용 (dedup 머지, reflection 합성, 인덱스 갱신)
  dry-run         후보만 보고, 실제 변경 없음
  prune-archive   archive TTL 만료 영구 삭제 (수동 전용)
  status          last_run.json + 현재 디렉터리 상태 출력
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import scan_memories
from .migrate import run_migration
from .paths import ARCHIVE_SUBDIRS, TYPE_DIRS, load_config
from .pruner import find_prune_candidates, prune_archive
from .runner import load_last_run, run_cycle


def _load_settings_env() -> None:
    """.claude-organic/.settings 를 환경에 로드 (있으면)."""
    import os
    from pathlib import Path
    cwd = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    settings = cwd / '.claude-organic' / '.settings'
    if not settings.is_file():
        return
    for line in settings.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _cmd_migrate(args: argparse.Namespace) -> int:
    _load_settings_env()
    cfg = load_config()
    report = run_migration(cfg)
    print(f'migrate: {report.summary()}')
    if report.moved_files:
        for src, dest in report.moved_files:
            print(f'  moved: {src.name} -> {dest.parent.name}/')
    if report.cleaned_locks:
        for p in report.cleaned_locks:
            print(f'  cleaned lock: {p.name}')
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    _load_settings_env()
    cfg = load_config()
    report = run_cycle(
        cfg,
        apply=not args.dry_run,
        with_reflection=not args.no_reflection,
    )
    if args.json:
        from dataclasses import asdict
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print(report.summary())
    if report.errors:
        for e in report.errors:
            print(f'  ! {e}', file=sys.stderr)
    return 0 if not report.errors else 1


def _cmd_prune(args: argparse.Namespace) -> int:
    _load_settings_env()
    cfg = load_config()
    result = prune_archive(cfg, apply=args.apply)
    print(f'prune-archive: {result.summary()}')
    if not args.apply and result.candidates:
        print('  (dry-run — re-run with --apply to delete)')
        for p in result.candidates:
            print(f'  - {p.relative_to(cfg.memory_dir)}')
    elif args.apply and result.deleted:
        for p in result.deleted:
            print(f'  deleted: {p.name}')
    return 0


def _cmd_auto(args: argparse.Namespace) -> int:
    """MEMORY_GC_AUTO_TRIGGERS 에 trigger 가 포함된 경우에만 run 호출. silent skip 정책."""
    _load_settings_env()
    cfg = load_config()
    if args.trigger not in cfg.auto_triggers:
        return 0
    report = run_cycle(cfg, apply=True, with_reflection=False)
    if report.errors:
        for e in report.errors:
            print(f'  ! {e}', file=sys.stderr)
        return 1
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    _load_settings_env()
    cfg = load_config()
    info = {
        'memory_dir': str(cfg.memory_dir),
        'hot_limit': cfg.hot_limit,
        'auto_triggers': list(cfg.auto_triggers),
        'reflection_threshold': cfg.reflection_threshold,
        'archive_ttl_days': cfg.archive_ttl_days,
        'counts': {},
        'archive_counts': {},
        'archive_pending_prune': len(find_prune_candidates(cfg)),
        'last_run': load_last_run(cfg),
    }
    for t in TYPE_DIRS:
        d = cfg.type_dir(t)
        info['counts'][t] = len(list(d.glob('*.md'))) if d.is_dir() else 0
    info['counts']['flat'] = sum(
        1 for p in cfg.memory_dir.glob('*.md') if p.name != 'MEMORY.md'
    )
    info['counts']['total'] = len(scan_memories(cfg))
    for k in ARCHIVE_SUBDIRS:
        d = cfg.archive_subdir(k)
        info['archive_counts'][k] = len(list(d.glob('*.md'))) if d.is_dir() else 0
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='flow-memory-gc', description='Memory GC')
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('migrate', help='Migrate flat memory dir to type-tiered layout')

    p_run = sub.add_parser('run', help='Apply one GC cycle')
    p_run.add_argument('--dry-run', action='store_true')
    p_run.add_argument('--no-reflection', action='store_true', help='skip LLM reflection')
    p_run.add_argument('--json', action='store_true')

    p_dry = sub.add_parser('dry-run', help='Alias for "run --dry-run --no-reflection"')

    p_prune = sub.add_parser('prune-archive', help='Permanently delete archive entries past TTL')
    p_prune.add_argument('--apply', action='store_true', help='actually delete (default: dry-run)')

    sub.add_parser('status', help='Show GC status JSON')

    p_auto = sub.add_parser('auto', help='Conditional run gated by MEMORY_GC_AUTO_TRIGGERS')
    p_auto.add_argument('--trigger', required=True, choices=('cron', 'session', 'size'))

    args = parser.parse_args(argv)
    if args.cmd == 'migrate':
        return _cmd_migrate(args)
    if args.cmd == 'run':
        return _cmd_run(args)
    if args.cmd == 'dry-run':
        ns = argparse.Namespace(dry_run=True, no_reflection=True, json=False)
        return _cmd_run(ns)
    if args.cmd == 'prune-archive':
        return _cmd_prune(args)
    if args.cmd == 'status':
        return _cmd_status(args)
    if args.cmd == 'auto':
        return _cmd_auto(args)
    parser.print_help()
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
