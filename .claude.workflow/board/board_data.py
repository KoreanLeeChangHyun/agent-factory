"""Board 데이터 읽기/유틸 모듈.

server.py에서 분리된 데이터 접근 함수와 관련 상수를 제공한다.
BoardHTTPRequestHandler._handle_api() 및 관련 핸들러에서 직접 import하여 사용한다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KANBAN_DIRS_LIST: list[str] = ['open', 'progress', 'review', 'done']
WF_BASE: str = os.path.join('.claude.workflow', 'workflow')
WF_HISTORY: str = os.path.join('.claude.workflow', 'workflow', '.history')
DASH_BASE: str = os.path.join('.claude.workflow', 'dashboard')
DASH_FILES: list[str] = ['usage', 'logs', 'skills']
WF_ENTRY_RE = re.compile(r'^\d{8}-\d{6}$')
WF_DETAIL_FILES: list[dict] = [
    {'key': 'query',   'file': 'user_prompt.txt'},
    {'key': 'plan',    'file': 'plan.md'},
    {'key': 'report',  'file': 'report.md'},
    {'key': 'summary', 'file': 'summary.txt'},
    {'key': 'usage',   'file': 'usage.json'},
    {'key': 'log',     'file': 'workflow.log'},
]

# ---------------------------------------------------------------------------
# Settings / Env helpers
# ---------------------------------------------------------------------------


def _resolve_settings_file(project_root: str) -> str:
    """Return .settings path."""
    return os.path.join(project_root, '.claude.workflow', '.settings')


def _parse_env_file(project_root: str) -> list[dict]:
    """Parse .settings into structured sections for the settings UI."""
    env_file = _resolve_settings_file(project_root)
    if not os.path.exists(env_file):
        return []

    sections: dict[str, list[dict]] = {}
    section_order: list[str] = []
    current_section = '기타'
    pending_comment = ''

    with open(env_file, encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()

            # Section header: "# (N) Section Name"
            if stripped.startswith('# (') and ')' in stripped:
                current_section = stripped.split(')', 1)[1].strip()
                if current_section not in sections:
                    sections[current_section] = []
                    section_order.append(current_section)
                pending_comment = ''
                continue

            if stripped.startswith('# ---'):
                continue

            if stripped.startswith('#'):
                text = stripped[1:].strip()
                if text.startswith('용도:'):
                    pending_comment = text[3:].strip()
                continue

            if not stripped or '=' not in stripped:
                continue

            key, _, rest = stripped.partition('=')
            key = key.strip()

            # Extract inline comment (2+ spaces before #)
            value = rest
            inline_comment = ''
            m = re.match(r'^(.*?)\s{2,}#\s*(.*)', rest)
            if m:
                value = m.group(1).strip()
                inline_comment = m.group(2).strip()
            else:
                value = rest.strip()

            # Detect type
            var_type = 'string'
            if value.lower() in ('true', 'false'):
                var_type = 'bool'
            elif value.isdigit():
                var_type = 'int'
            else:
                try:
                    float(value)
                    if '.' in value:
                        var_type = 'float'
                except ValueError:
                    pass

            label = inline_comment or pending_comment or ''
            if current_section not in sections:
                sections[current_section] = []
                section_order.append(current_section)

            sections[current_section].append({
                'key': key,
                'value': value,
                'type': var_type,
                'label': label,
            })
            pending_comment = ''

    return [{'section': s, 'vars': sections[s]} for s in section_order]


def _update_env_value(project_root: str, key: str, new_value: str) -> bool:
    """Update a single key's value in .settings, preserving structure and comments."""
    env_file = _resolve_settings_file(project_root)
    if not os.path.exists(env_file):
        return False

    with open(env_file, encoding='utf-8') as f:
        lines = f.readlines()

    pattern = re.compile(r'^' + re.escape(key) + r'=')

    for i, line in enumerate(lines):
        if not pattern.match(line.strip()):
            continue

        old_rest = line.strip().split('=', 1)[1]
        inline_part = ''
        m = re.match(r'^(.*?)\s{2,}(#\s*.*)', old_rest)
        if m:
            inline_part = m.group(2)

        if inline_part:
            base = f"{key}={new_value}"
            pad = max(2, 40 - len(base))
            lines[i] = base + ' ' * pad + inline_part + '\n'
        else:
            lines[i] = f"{key}={new_value}\n"
        break
    else:
        return False

    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    return True


# ---------------------------------------------------------------------------
# Kanban / Dashboard readers
# ---------------------------------------------------------------------------


def _read_kanban_tickets(
    project_root: str, files: list[str] | None = None,
) -> dict[str, str | None]:
    """kanban 디렉터리에서 XML 티켓을 읽어 {파일명: 내용} dict를 반환한다."""
    kanban = os.path.join(project_root, '.claude.workflow', 'kanban')
    result: dict[str, str | None] = {}
    for d in KANBAN_DIRS_LIST:
        dp = os.path.join(kanban, d)
        if not os.path.isdir(dp):
            continue
        try:
            for e in os.scandir(dp):
                if not e.is_file() or not e.name.endswith('.xml'):
                    continue
                if files and e.name not in files:
                    continue
                if e.name in result:
                    continue
                try:
                    with open(e.path, encoding='utf-8') as f:
                        result[e.name] = f.read()
                except OSError:
                    result[e.name] = None
        except OSError:
            pass
    if files:
        for fn in files:
            if fn not in result:
                result[fn] = None
    return result


def _read_dashboard(project_root: str) -> dict[str, str]:
    """dashboard .md 파일 3개를 읽어 반환한다."""
    base = os.path.join(project_root, DASH_BASE)
    result: dict[str, str] = {}
    for name in DASH_FILES:
        path = os.path.join(base, f'.{name}.md')
        try:
            with open(path, encoding='utf-8') as f:
                result[name] = f.read()
        except OSError:
            result[name] = ''
    return result


# ---------------------------------------------------------------------------
# Workflow helpers
# ---------------------------------------------------------------------------


def _list_workflow_entries(project_root: str) -> list[str]:
    """workflow + .history 엔트리를 최신순 정렬하여 반환한다."""
    entries: list[str] = []
    for rel in (WF_BASE, WF_HISTORY):
        abs_dir = os.path.join(project_root, rel)
        if not os.path.isdir(abs_dir):
            continue
        prefix = rel + '/'
        try:
            for e in os.scandir(abs_dir):
                if e.is_dir() and WF_ENTRY_RE.match(e.name):
                    entries.append(prefix + e.name + '/')
        except OSError:
            pass
    entries.sort(key=lambda p: p.rstrip('/').rsplit('/', 1)[-1], reverse=True)
    return entries


def _get_git_branch(project_root: str) -> str:
    """현재 git 브랜치명을 반환한다.

    git 명령 실행 실패 또는 타임아웃 시 빈 문자열을 반환한다.
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, timeout=3,
            cwd=project_root,
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ''


def _workflow_detail(project_root: str, entry_rel: str) -> list[dict]:
    """워크플로우 엔트리 1개의 상세 정보를 반환한다."""
    entry_name = entry_rel.rstrip('/').rsplit('/', 1)[-1]
    entry_abs = os.path.join(project_root, entry_rel.strip('/'))
    if not os.path.isdir(entry_abs):
        return []
    items: list[dict] = []
    try:
        task_dirs = sorted(
            (e.name for e in os.scandir(entry_abs) if e.is_dir()),
        )
    except OSError:
        return []
    for task in task_dirs:
        task_abs = os.path.join(entry_abs, task)
        try:
            cmd_dirs = sorted(
                (e.name for e in os.scandir(task_abs) if e.is_dir()),
            )
        except OSError:
            continue
        for cmd in cmd_dirs:
            cmd_abs = os.path.join(task_abs, cmd)
            status_path = os.path.join(cmd_abs, 'status.json')
            if not os.path.isfile(status_path):
                continue
            try:
                with open(status_path, encoding='utf-8') as f:
                    status = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            # basePath: relative URL matching client convention
            base_path = entry_rel + task + '/' + cmd + '/'
            # file map
            file_map: dict = {}
            for wf in WF_DETAIL_FILES:
                fp = os.path.join(cmd_abs, wf['file'])
                exists = os.path.isfile(fp)
                file_map[wf['key']] = {
                    'exists': exists,
                    'url': base_path + wf['file'] if exists else '',
                }
            work_dir = os.path.join(cmd_abs, 'work')
            has_work = os.path.isdir(work_dir)
            file_map['work'] = {
                'exists': has_work,
                'url': base_path + 'work/' if has_work else '',
                'isDir': True,
            }
            items.append({
                'entry': entry_name,
                'task': task,
                'command': cmd,
                'basePath': base_path,
                'step': status.get('step', 'NONE'),
                'created_at': status.get('created_at', ''),
                'updated_at': status.get('updated_at', ''),
                'transitions': status.get('transitions', []),
                'fileMap': file_map,
            })
    return items


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------

# 파일명 허용 패턴: 알파벳, 숫자, 하이픈, 언더스코어, 점 (.md 확장자 필수)
_MEMORY_FILENAME_RE = re.compile(r'^[A-Za-z0-9_\-]+\.md$')


def _resolve_memory_dir(project_root: str) -> str:
    """프로젝트 루트에 대응하는 Claude auto memory 디렉터리 경로를 반환한다.

    경로 규칙: ~/.claude/projects/-{project_root_with_slash_to_dash}/memory/
    예: /home/deus/workspace/claude -> ~/.claude/projects/-home-deus-workspace-claude/memory/

    Args:
        project_root: 프로젝트 루트 절대 경로

    Returns:
        memory 디렉터리 절대 경로
    """
    # project_root의 선행 / 제거 후 / -> - 치환
    normalized = project_root.lstrip('/').replace('/', '-')
    return os.path.join(
        os.path.expanduser('~'), '.claude', 'projects',
        '-' + normalized, 'memory',
    )


def _list_memory_files(project_root: str) -> list[dict]:
    """memory 디렉터리의 .md 파일 목록을 반환한다.

    MEMORY.md는 isIndex: true로 표시하며, 목록 최상단에 배치한다.
    숨김 파일(. 시작)은 제외한다.

    Args:
        project_root: 프로젝트 루트 절대 경로

    Returns:
        [{"name": str, "size": int, "mtime": str, "isIndex": bool}, ...]
        디렉터리 미존재 시 빈 리스트.
    """
    mem_dir = _resolve_memory_dir(project_root)
    if not os.path.isdir(mem_dir):
        return []

    files: list[dict] = []
    try:
        for entry in os.scandir(mem_dir):
            if not entry.is_file() or not entry.name.endswith('.md'):
                continue
            if entry.name.startswith('.'):
                continue
            try:
                stat = entry.stat()
                files.append({
                    'name': entry.name,
                    'size': stat.st_size,
                    'mtime': time.strftime(
                        '%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime),
                    ),
                    'isIndex': entry.name == 'MEMORY.md',
                })
            except OSError:
                pass
    except OSError:
        return []

    # MEMORY.md를 최상단, 나머지는 이름순 정렬
    files.sort(key=lambda f: (not f['isIndex'], f['name']))
    return files


def _read_memory_file(project_root: str, filename: str) -> dict:
    """memory 파일 1개의 내용을 읽어 반환한다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        filename: 읽을 파일명 (확장자 포함)

    Returns:
        {"name": str, "content": str, "size": int}

    Raises:
        ValueError: 파일명이 보안 검증에 실패한 경우
        FileNotFoundError: 파일이 존재하지 않는 경우
    """
    _validate_memory_filename(filename)
    mem_dir = _resolve_memory_dir(project_root)
    filepath = os.path.join(mem_dir, filename)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f'Memory file not found: {filename}')

    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    return {
        'name': filename,
        'content': content,
        'size': len(content.encode('utf-8')),
    }


def _write_memory_file(
    project_root: str, filename: str, content: str,
) -> dict:
    """memory 파일을 생성하거나 수정한다.

    .md 확장자가 없으면 자동으로 붙인다. 저장 후 인덱스 동기화를 수행한다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        filename: 저장할 파일명
        content: 파일 내용

    Returns:
        {"ok": True, "name": str}

    Raises:
        ValueError: 파일명이 보안 검증에 실패한 경우
    """
    if not filename.endswith('.md'):
        filename += '.md'
    _validate_memory_filename(filename)

    mem_dir = _resolve_memory_dir(project_root)
    os.makedirs(mem_dir, exist_ok=True)
    filepath = os.path.join(mem_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    _sync_memory_index(project_root)
    return {'ok': True, 'name': filename}


def _delete_memory_file(project_root: str, filename: str) -> dict:
    """memory 파일을 삭제한다.

    MEMORY.md(인덱스 파일)는 삭제할 수 없다. 삭제 후 인덱스 동기화를 수행한다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        filename: 삭제할 파일명

    Returns:
        {"ok": True}

    Raises:
        ValueError: 파일명이 보안 검증에 실패하거나 MEMORY.md인 경우
        FileNotFoundError: 파일이 존재하지 않는 경우
    """
    _validate_memory_filename(filename)
    if filename == 'MEMORY.md':
        raise ValueError('Cannot delete index file: MEMORY.md')

    mem_dir = _resolve_memory_dir(project_root)
    filepath = os.path.join(mem_dir, filename)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f'Memory file not found: {filename}')

    os.remove(filepath)
    _sync_memory_index(project_root)
    return {'ok': True}


def _sync_memory_index(project_root: str) -> None:
    """MEMORY.md의 Topic Files 섹션을 디렉터리 실제 파일과 동기화한다.

    - Topic Files 섹션에만 있고 디렉터리에 없는 항목: 제거
    - 디렉터리에만 있고 Topic Files에 없는 .md 파일: 추가
    - 기존 항목의 설명 텍스트(" -- 설명")는 보존
    - MEMORY.md 자체와 숨김 파일은 인덱스 대상에서 제외

    Args:
        project_root: 프로젝트 루트 절대 경로
    """
    mem_dir = _resolve_memory_dir(project_root)
    index_path = os.path.join(mem_dir, 'MEMORY.md')

    if not os.path.isfile(index_path):
        return

    # 디렉터리의 실제 .md 파일 목록 (MEMORY.md, 숨김 파일 제외)
    actual_files: set[str] = set()
    try:
        for entry in os.scandir(mem_dir):
            if (entry.is_file()
                    and entry.name.endswith('.md')
                    and not entry.name.startswith('.')
                    and entry.name != 'MEMORY.md'):
                actual_files.add(entry.name)
    except OSError:
        return

    # MEMORY.md 읽기
    with open(index_path, encoding='utf-8') as f:
        lines = f.readlines()

    # Topic Files 섹션 찾기
    topic_start = -1
    topic_end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == '## Topic Files':
            topic_start = i
            continue
        if topic_start >= 0 and line.startswith('## ') and i > topic_start:
            topic_end = i
            break

    if topic_start < 0:
        # Topic Files 섹션이 없으면 동기화 생략
        return

    # 기존 Topic Files 항목 파싱: {filename: "전체 라인 텍스트"}
    # 형식: - [filename.md](filename.md) — 설명
    topic_line_re = re.compile(
        r'^- \[([^\]]+)\]\([^)]+\)(.*)',
    )
    existing: dict[str, str] = {}  # filename -> description part
    topic_lines_range = range(topic_start + 1, topic_end)
    for i in topic_lines_range:
        m = topic_line_re.match(lines[i].strip())
        if m:
            fname = m.group(1)
            desc = m.group(2)  # " — 설명" 또는 빈 문자열
            existing[fname] = desc

    # 동기화: 실제 파일과 비교
    # 1) 삭제된 파일 제거
    synced: dict[str, str] = {
        fname: desc for fname, desc in existing.items()
        if fname in actual_files
    }
    # 2) 새로 추가된 파일 삽입 (설명 없음)
    for fname in sorted(actual_files):
        if fname not in synced:
            synced[fname] = ''

    # 새 Topic Files 섹션 라인 구성
    new_topic_lines: list[str] = []
    for fname in sorted(synced.keys()):
        desc = synced[fname]
        new_topic_lines.append(f'- [{fname}]({fname}){desc}\n')

    # 원본 라인 재구성
    # topic_start 라인(## Topic Files)은 유지, 그 다음 빈 줄 + 항목 + 빈 줄
    before = lines[:topic_start + 1]
    after = lines[topic_end:]

    rebuilt: list[str] = before + ['\n'] + new_topic_lines + ['\n'] + after

    with open(index_path, 'w', encoding='utf-8') as f:
        f.writelines(rebuilt)


def _validate_memory_filename(filename: str) -> None:
    """메모리 파일명의 보안 검증을 수행한다.

    디렉터리 트래버설 공격 및 비정상 파일명을 방지한다.

    Args:
        filename: 검증할 파일명

    Raises:
        ValueError: 파일명에 '..' 또는 '/'가 포함되거나, 허용 패턴에 맞지 않는 경우
    """
    if '..' in filename or '/' in filename or '\\' in filename:
        raise ValueError(f'Invalid filename: {filename}')
    if not _MEMORY_FILENAME_RE.match(filename):
        raise ValueError(f'Invalid filename format: {filename}')


# ---------------------------------------------------------------------------
# Rules helpers (.claude/rules/)
# ---------------------------------------------------------------------------

# rules 파일명 허용 패턴: 알파벳, 숫자, 하이픈, 언더스코어, 점 (.md 확장자 필수)
_RULES_FILENAME_RE = re.compile(r'^[A-Za-z0-9_\-]+\.md$')

# 허용 카테고리
_RULES_CATEGORIES = {'workflow', 'project'}

# claude_edit.py 스크립트 절대 경로
_CLAUDE_EDIT_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'scripts', 'claude_edit.py',
)


def _validate_rules_rel_path(rel_path: str) -> tuple[str, str]:
    """rules 상대 경로를 검증하고 (category, filename) 튜플을 반환한다.

    Args:
        rel_path: '.claude/rules/' 기준 상대 경로 (예: 'workflow/general.md')

    Returns:
        (category, filename) 튜플

    Raises:
        ValueError: 경로 형식이 잘못되었거나 허용되지 않는 경우
    """
    if '..' in rel_path or '\\' in rel_path:
        raise ValueError(f'Invalid path: {rel_path}')
    parts = rel_path.strip('/').split('/')
    if len(parts) != 2:
        raise ValueError(f'Path must be category/filename.md format: {rel_path}')
    category, filename = parts
    if category not in _RULES_CATEGORIES:
        raise ValueError(f'Unknown category: {category}. Must be one of {_RULES_CATEGORIES}')
    if not _RULES_FILENAME_RE.match(filename):
        raise ValueError(f'Invalid filename format: {filename}')
    return category, filename


def _list_rules_files(project_root: str) -> list[dict]:
    """'.claude/rules/' 하위 모든 .md 파일을 재귀 탐색하여 목록을 반환한다.

    Args:
        project_root: 프로젝트 루트 절대 경로

    Returns:
        [{"name": str, "path": str, "size": int, "mtime": str, "category": str}, ...]
        'path'는 '.claude/rules/' 기준 상대 경로 (예: 'workflow/general.md')
        'category'는 하위 디렉터리명 (workflow 또는 project)
    """
    rules_dir = os.path.join(project_root, '.claude', 'rules')
    if not os.path.isdir(rules_dir):
        return []

    files: list[dict] = []
    try:
        for category in sorted(os.listdir(rules_dir)):
            cat_path = os.path.join(rules_dir, category)
            if not os.path.isdir(cat_path) or category.startswith('.') or category == '__pycache__':
                continue
            try:
                for entry in os.scandir(cat_path):
                    if not entry.is_file() or not entry.name.endswith('.md'):
                        continue
                    if entry.name.startswith('.'):
                        continue
                    try:
                        stat = entry.stat()
                        files.append({
                            'name': entry.name,
                            'path': f'{category}/{entry.name}',
                            'size': stat.st_size,
                            'mtime': time.strftime(
                                '%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime),
                            ),
                            'category': category,
                        })
                    except OSError:
                        pass
            except OSError:
                continue
    except OSError:
        return []

    return files


def _read_rules_file(project_root: str, rel_path: str) -> dict:
    """rules 파일 1개의 내용을 읽어 반환한다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        rel_path: '.claude/rules/' 기준 상대 경로 (예: 'workflow/general.md')

    Returns:
        {"name": str, "path": str, "content": str, "size": int}

    Raises:
        ValueError: 경로가 보안 검증에 실패한 경우
        FileNotFoundError: 파일이 존재하지 않는 경우
    """
    category, filename = _validate_rules_rel_path(rel_path)
    filepath = os.path.join(project_root, '.claude', 'rules', category, filename)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f'Rules file not found: {rel_path}')

    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    return {
        'name': filename,
        'path': rel_path,
        'content': content,
        'size': len(content.encode('utf-8')),
    }


def _write_rules_file(
    project_root: str, rel_path: str, content: str,
) -> dict:
    """rules 파일을 생성하거나 수정한다.

    .claude/ 하위 파일이므로 flow-claude-edit (claude_edit.py)를 경유한다.
    open -> edit/ 파일 수정 -> save 순서로 처리한다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        rel_path: '.claude/rules/' 기준 상대 경로 (예: 'workflow/general.md')
        content: 저장할 파일 내용

    Returns:
        {"ok": True, "path": str}

    Raises:
        ValueError: 경로가 보안 검증에 실패한 경우
        RuntimeError: flow-claude-edit 호출 실패 시
    """
    category, filename = _validate_rules_rel_path(rel_path)

    # .claude/rules/category/filename 형식으로 claude_edit에 전달
    claude_rel_path = f'rules/{rel_path}'

    # 원본이 없을 경우 open이 실패하므로, 신규 파일은 직접 생성 후 save
    original_path = os.path.join(project_root, '.claude', 'rules', category, filename)
    edit_dir = os.path.join(project_root, '.claude.workflow', 'edit')
    edit_path = os.path.join(edit_dir, 'rules', rel_path)
    script = os.path.normpath(_CLAUDE_EDIT_SCRIPT)

    is_new = not os.path.isfile(original_path)

    if not is_new:
        # open: .claude/ -> edit/ 복사
        result = subprocess.run(
            ['python3', script, 'open', claude_rel_path],
            capture_output=True, text=True, timeout=10,
            cwd=project_root,
        )
        if result.returncode != 0:
            raise RuntimeError(f'flow-claude-edit open failed: {result.stderr.strip()}')

    # edit/ 파일에 내용 기록
    os.makedirs(os.path.dirname(edit_path), exist_ok=True)
    with open(edit_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # save: edit/ -> .claude/ 덮어쓰기
    result = subprocess.run(
        ['python3', script, 'save', claude_rel_path],
        capture_output=True, text=True, timeout=10,
        cwd=project_root,
    )
    if result.returncode != 0:
        raise RuntimeError(f'flow-claude-edit save failed: {result.stderr.strip()}')

    return {'ok': True, 'path': rel_path}


def _delete_rules_file(project_root: str, rel_path: str) -> dict:
    """rules 파일을 삭제한다.

    .claude/ 하위 파일이므로 open 후 edit/ 파일 삭제, 원본 rm 순서로 처리한다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        rel_path: '.claude/rules/' 기준 상대 경로 (예: 'workflow/general.md')

    Returns:
        {"ok": True}

    Raises:
        ValueError: 경로가 보안 검증에 실패한 경우
        FileNotFoundError: 파일이 존재하지 않는 경우
        RuntimeError: flow-claude-edit 호출 실패 시
    """
    category, filename = _validate_rules_rel_path(rel_path)
    original_path = os.path.join(project_root, '.claude', 'rules', category, filename)

    if not os.path.isfile(original_path):
        raise FileNotFoundError(f'Rules file not found: {rel_path}')

    claude_rel_path = f'rules/{rel_path}'
    script = os.path.normpath(_CLAUDE_EDIT_SCRIPT)
    edit_dir = os.path.join(project_root, '.claude.workflow', 'edit')
    edit_path = os.path.join(edit_dir, 'rules', rel_path)

    # open: .claude/ -> edit/ 복사
    result = subprocess.run(
        ['python3', script, 'open', claude_rel_path],
        capture_output=True, text=True, timeout=10,
        cwd=project_root,
    )
    if result.returncode != 0:
        raise RuntimeError(f'flow-claude-edit open failed: {result.stderr.strip()}')

    # edit/ 복사본 삭제
    if os.path.isfile(edit_path):
        os.remove(edit_path)

    # 원본 파일 삭제
    os.remove(original_path)

    return {'ok': True}


# ---------------------------------------------------------------------------
# Prompt helpers (.claude.workflow/prompt/)
# ---------------------------------------------------------------------------

# prompt 파일명 허용 패턴: 알파벳, 숫자, 하이픈, 언더스코어, 점
_PROMPT_FILENAME_RE = re.compile(r'^[A-Za-z0-9_\-\.]+$')


def _validate_prompt_filename(filename: str) -> None:
    """prompt 파일명의 보안 검증을 수행한다.

    Args:
        filename: 검증할 파일명

    Raises:
        ValueError: 파일명에 '..' 또는 '/'가 포함되거나 허용 패턴에 맞지 않는 경우
    """
    if '..' in filename or '/' in filename or '\\' in filename:
        raise ValueError(f'Invalid filename: {filename}')
    if not _PROMPT_FILENAME_RE.match(filename):
        raise ValueError(f'Invalid filename format: {filename}')


def _list_prompt_files(project_root: str) -> list[dict]:
    """'.claude.workflow/prompt/' 하위 모든 파일 목록을 반환한다.

    숨김 파일과 __pycache__ 디렉터리는 제외한다.

    Args:
        project_root: 프로젝트 루트 절대 경로

    Returns:
        [{"name": str, "size": int, "mtime": str}, ...]
    """
    prompt_dir = os.path.join(project_root, '.claude.workflow', 'prompt')
    if not os.path.isdir(prompt_dir):
        return []

    files: list[dict] = []
    try:
        for entry in os.scandir(prompt_dir):
            if not entry.is_file():
                continue
            if entry.name.startswith('.') or entry.name == '__pycache__':
                continue
            try:
                stat = entry.stat()
                files.append({
                    'name': entry.name,
                    'size': stat.st_size,
                    'mtime': time.strftime(
                        '%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime),
                    ),
                })
            except OSError:
                pass
    except OSError:
        return []

    files.sort(key=lambda f: f['name'])
    return files


def _read_prompt_file(project_root: str, filename: str) -> dict:
    """prompt 파일 1개의 내용을 읽어 반환한다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        filename: 읽을 파일명

    Returns:
        {"name": str, "content": str, "size": int}

    Raises:
        ValueError: 파일명이 보안 검증에 실패한 경우
        FileNotFoundError: 파일이 존재하지 않는 경우
    """
    _validate_prompt_filename(filename)
    prompt_dir = os.path.join(project_root, '.claude.workflow', 'prompt')
    filepath = os.path.join(prompt_dir, filename)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f'Prompt file not found: {filename}')

    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    return {
        'name': filename,
        'content': content,
        'size': len(content.encode('utf-8')),
    }


def _write_prompt_file(
    project_root: str, filename: str, content: str,
) -> dict:
    """.claude.workflow/prompt/ 파일을 생성하거나 수정한다.

    .claude.workflow/ 하위이므로 직접 쓰기 가능하다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        filename: 저장할 파일명
        content: 파일 내용

    Returns:
        {"ok": True, "name": str}

    Raises:
        ValueError: 파일명이 보안 검증에 실패한 경우
    """
    _validate_prompt_filename(filename)
    prompt_dir = os.path.join(project_root, '.claude.workflow', 'prompt')
    os.makedirs(prompt_dir, exist_ok=True)
    filepath = os.path.join(prompt_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return {'ok': True, 'name': filename}


def _delete_prompt_file(project_root: str, filename: str) -> dict:
    """.claude.workflow/prompt/ 파일을 삭제한다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        filename: 삭제할 파일명

    Returns:
        {"ok": True}

    Raises:
        ValueError: 파일명이 보안 검증에 실패한 경우
        FileNotFoundError: 파일이 존재하지 않는 경우
    """
    _validate_prompt_filename(filename)
    prompt_dir = os.path.join(project_root, '.claude.workflow', 'prompt')
    filepath = os.path.join(prompt_dir, filename)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f'Prompt file not found: {filename}')

    os.remove(filepath)
    return {'ok': True}


# ---------------------------------------------------------------------------
# CLAUDE.md helpers (project root)
# ---------------------------------------------------------------------------


def _read_claude_md(project_root: str) -> dict:
    """프로젝트 루트의 CLAUDE.md 내용을 읽어 반환한다.

    Args:
        project_root: 프로젝트 루트 절대 경로

    Returns:
        {"name": "CLAUDE.md", "content": str, "size": int}

    Raises:
        FileNotFoundError: CLAUDE.md가 존재하지 않는 경우
    """
    filepath = os.path.join(project_root, 'CLAUDE.md')
    if not os.path.isfile(filepath):
        raise FileNotFoundError('CLAUDE.md not found in project root')

    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    return {
        'name': 'CLAUDE.md',
        'content': content,
        'size': len(content.encode('utf-8')),
    }


def _write_claude_md(project_root: str, content: str) -> dict:
    """프로젝트 루트의 CLAUDE.md를 수정한다.

    CLAUDE.md는 프로젝트 루트에 위치하며 .claude/ 하위가 아니므로 직접 쓰기 가능하다.

    Args:
        project_root: 프로젝트 루트 절대 경로
        content: 저장할 파일 내용

    Returns:
        {"ok": True}
    """
    filepath = os.path.join(project_root, 'CLAUDE.md')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return {'ok': True}
