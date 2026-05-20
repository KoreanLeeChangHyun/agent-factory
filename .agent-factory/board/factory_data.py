"""Board Data Reading/Utilization Modules.

server.py provides a separate data access function and related constant.
BoardHTTPRequestHandler. handle api()
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time

from board.factory_sources.settings import (
    _parse_env_file,
    _resolve_settings_file,
    _update_env_value,
)
from board.factory_sources.overview import (
    DASH_BASE,
    DASH_FILES,
    KANBAN_DIRS_LIST,
    _read_dashboard,
    _read_kanban_tickets,
)
from board.factory_sources.workflows import (
    WF_BASE,
    WF_DETAIL_FILES,
    WF_ENTRY_RE,
    WF_HISTORY,
    _get_git_branch,
    _list_workflow_entries,
    _workflow_detail,
)
from board.factory_sources.prompts import (
    _delete_prompt_file,
    _list_prompt_files,
    _prompt_files_dir,
    _read_prompt_file,
    _validate_prompt_filename,
    _write_prompt_file,
)
from engine.apps.board_api.prompt_store import (
    QUICK_PROMPTS_PATH,
    _delete_quick_prompt,
    _quick_prompts_filepath,
    _read_quick_prompts,
    _validate_quick_prompt_id,
    _write_quick_prompt,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------

# Allowed file name patterns: alphabet, number, hyphen, underscore, dot (.md extension required)
_MEMORY_FILENAME_RE = re.compile(r'^[A-Za-z0-9_\-]+\.md$')

# Allow step 1 sub-directory after Memory GC migration (user/feedback/project/reference/archive)
_MEMORY_TYPE_DIRS: tuple[str, ...] = ('user', 'feedback', 'project', 'reference')
_MEMORY_ARCHIVE_DIRS: tuple[str, ...] = ('archive/merged', 'archive/synthesized', 'archive/stale')
_MEMORY_ALLOWED_SUBDIRS: tuple[str, ...] = _MEMORY_TYPE_DIRS + _MEMORY_ARCHIVE_DIRS


def _resolve_memory_dir(project_root: str) -> str:
    """return the Claude auto memory directory path to the project route.

    Path rules: ~/. slash to dash}/memory/
    /home-deus-workspace-claude/memory/

    Args:
        project root: Project route absolute path

    Returns:
        memory directory absolute path
    """
    # Preceding/removing project_root/->-replacement
    normalized = project_root.lstrip('/').replace('/', '-')
    return os.path.join(
        os.path.expanduser('~'), '.claude', 'projects',
        '-' + normalized, 'memory',
    )


def _list_memory_files(project_root: str) -> list[dict]:
    """returns the .md file list of memory directories.

    type directory (user/feedback/project/reference) and
    Scan the archive sub(merged/synthesized/stale) as well. Default file is also compatible.
    name field is mem dir standard relative path (e.g. "feedback/feedback root.md").

    MEMORY.md isIndex: true, and is placed in the top of the list.
    Search file(.) Start) is excluded.

    Args:
        project root: Project route absolute path

    Returns:
        [{"name": str, "size": int, "mtime": str, "isIndex": bool, "category": str}, ...]
        Director Lee Min-Joon
    """
    mem_dir = _resolve_memory_dir(project_root)
    if not os.path.isdir(mem_dir):
        return []

    files: list[dict] = []

    def _emit(rel_name: str, abs_path: str, category: str) -> None:
        try:
            stat = os.stat(abs_path)
        except OSError:
            return
        files.append({
            'name': rel_name,
            'size': stat.st_size,
            'mtime': time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime),
            ),
            'isIndex': rel_name == 'MEMORY.md',
            'category': category,
        })

    # 1) Flattened files (including MEMORY.md)
    try:
        for entry in os.scandir(mem_dir):
            if not entry.is_file() or not entry.name.endswith('.md'):
                continue
            if entry.name.startswith('.'):
                continue
            _emit(entry.name, entry.path, 'flat')
    except OSError:
        return []

    # 2) Step 1 sub-directory (type + archive)
    for sub in _MEMORY_ALLOWED_SUBDIRS:
        sub_path = os.path.join(mem_dir, sub)
        if not os.path.isdir(sub_path):
            continue
        try:
            for entry in os.scandir(sub_path):
                if not entry.is_file() or not entry.name.endswith('.md'):
                    continue
                if entry.name.startswith('.'):
                    continue
                _emit(f'{sub}/{entry.name}', entry.path, sub)
        except OSError:
            continue

    # MEMORY.md at the top → Others are sorted by (category, name)
    files.sort(key=lambda f: (not f['isIndex'], f['category'], f['name']))
    return files


def _read_memory_file(project_root: str, filename: str) -> dict:
    """return to read 1 memory file.

    Args:
        project root: Project route absolute path
        filename: read filename (including specifier)

    Returns:
        {"name": str, "content": str, "size": int}

    Raises:
        ValueError: If filename fails to validate security
        FileNotFoundError: If the file does not exist
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
    """Create or edit memory files.

    . If there is no md extension, it will be automatically attached. Perform index sync after storage.

    Args:
        project root: Project route absolute path
        filename:
        content: Content

    Returns:
        {"ok": True, "name": str}

    Raises:
        ValueError: If filename fails to validate security
    """
    if not filename.endswith('.md'):
        filename += '.md'
    _validate_memory_filename(filename)

    mem_dir = _resolve_memory_dir(project_root)
    filepath = os.path.join(mem_dir, filename)
    os.makedirs(os.path.dirname(filepath) or mem_dir, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    _trigger_memory_index_regen(project_root)
    return {'ok': True, 'name': filename}


def _delete_memory_file(project_root: str, filename: str) -> dict:
    """Delete memory files.

    MEMORY.md cannot be deleted. Perform index synchronization after deletion.

    Args:
        project root: Project route absolute path
        filename:

    Returns:
        {"ok": True}

    Raises:
        ValueError: If filename fails to validate security or MEMORY.md
        FileNotFoundError: If the file does not exist
    """
    _validate_memory_filename(filename)
    if filename == 'MEMORY.md':
        raise ValueError('Cannot delete index file: MEMORY.md')

    mem_dir = _resolve_memory_dir(project_root)
    filepath = os.path.join(mem_dir, filename)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f'Memory file not found: {filename}')

    os.remove(filepath)
    _trigger_memory_index_regen(project_root)
    return {'ok': True}


def _sync_memory_index(project_root: str) -> None:
    """Sync the Topic Files section of MEMORY.md with the directory real file.

    - Topic Files section only and no directory items: removal
    - .md file without directory and Topic Files: Added
    - The description text of the existing item ("--Description") preserved
    - MEMORY.md self and hidden files excluded from index target

    Args:
        project root: Project route absolute path
    """
    mem_dir = _resolve_memory_dir(project_root)
    index_path = os.path.join(mem_dir, 'MEMORY.md')

    if not os.path.isfile(index_path):
        return

    # List of actual .md files in the directory (excluding MEMORY.md, hidden files)
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

    # Read MEMORY.md
    with open(index_path, encoding='utf-8') as f:
        lines = f.readlines()

    # Find the Topic Files section
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
        # Skip synchronization if Topic Files section does not exist
        return

    # Parse existing Topic Files items: {filename: "full line text"}
    # Format: - [filename.md](filename.md) — Description
    topic_line_re = re.compile(
        r'^- \[([^\]]+)\]\([^)]+\)(.*)',
    )
    existing: dict[str, str] = {}  # filename -> description part
    topic_lines_range = range(topic_start + 1, topic_end)
    for i in topic_lines_range:
        m = topic_line_re.match(lines[i].strip())
        if m:
            fname = m.group(1)
            desc = m.group(2)  # "- explanation" or empty string
            existing[fname] = desc

    # Sync: Compare to actual file
    # 1) Remove deleted files
    synced: dict[str, str] = {
        fname: desc for fname, desc in existing.items()
        if fname in actual_files
    }
    # 2) Insert newly added file (no description)
    for fname in sorted(actual_files):
        if fname not in synced:
            synced[fname] = ''

    # New Topic Files section line configuration
    new_topic_lines: list[str] = []
    for fname in sorted(synced.keys()):
        desc = synced[fname]
        new_topic_lines.append(f'- [{fname}]({fname}){desc}\n')

    # Reconstruct the original line
    # Keep topic_start line (## Topic Files), then blank line + item + blank line
    before = lines[:topic_start + 1]
    after = lines[topic_end:]

    rebuilt: list[str] = before + ['\n'] + new_topic_lines + ['\n'] + after

    with open(index_path, 'w', encoding='utf-8') as f:
        f.writelines(rebuilt)


def _validate_memory_filename(filename: str) -> None:
    """Perform security verification of memory filename.

    Prevents directory attacks, sub-directory whitelisted
    (user/feedback/project/reference, archive/{merged,synthesized,stale})

    Args:
        filename: filename or sub-path to validate

    Raises:
        ValueError: '..' in the filename, '\\\\' contains or whitelists,
                   If you do not meet the acceptable pattern
    """
    if '..' in filename or '\\' in filename:
        raise ValueError(f'Invalid filename: {filename}')
    if '/' in filename:
        # Only 1st or 2nd level (archive/x) sub-directories are allowed.
        head, _, tail = filename.rpartition('/')
        if head not in _MEMORY_ALLOWED_SUBDIRS:
            raise ValueError(f'Invalid memory sub-directory: {head}')
        if not _MEMORY_FILENAME_RE.match(tail):
            raise ValueError(f'Invalid filename format: {tail}')
        return
    if not _MEMORY_FILENAME_RE.match(filename):
        raise ValueError(f'Invalid filename format: {filename}')


# ---------------------------------------------------------------------------
# Rules helpers (.claude/rules/)
# ---------------------------------------------------------------------------

# rules Allowed file name patterns: alphabet, number, hyphen, underscore, dot (.md extension required)
_RULES_FILENAME_RE = re.compile(r'^[A-Za-z0-9_\-]+\.md$')

# Allowed categories
_RULES_CATEGORIES = {'workflow', 'project'}

# claude_edit.py script absolute path
_CLAUDE_EDIT_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'engine', 'claude_edit.py',
)


def _validate_rules_rel_path(rel_path: str) -> tuple[str, str]:
    """Verify the relative path and return (category, filename) tuple.

    Args:
        rel path: '.claude/rules/' reference path (e.g. 'workflow/general.md')

    Returns:
        (category, filename)

    Raises:
        ValueError: If the path format is wrong or not allowed
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
    """returns the list by recurring all .md files under '.claude/rules/'.

    Args:
        project root: Project route absolute path

    Returns:
        [{"name": str, "path": str, "size": int, "mtime": str, "category": str}, ...]
        'path' is '.claude/rules/' based relative path (e.g. 'workflowgene/ral.md')
        'category' is a subdirectory name (workflow or project)
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
    """Returns the contents of the rules file.

    Args:
        project root: Project route absolute path
        rel path: '.claude/rules/' reference path (e.g. 'workflow/general.md')

    Returns:
        {"name": str, "path": str, "content": str, "size": int}

    Raises:
        ValueError: If the path fails to validate security
        FileNotFoundError: If the file does not exist
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
    """Create or edit the rules file.

    . Since claude/ sub-files, it is enforced by flow-claude-edit (claude edit.py).
    open -> edit/ modify the file -> save in order.

    Args:
        project root: Project route absolute path
        rel path: '.claude/rules/' reference path (e.g. 'workflow/general.md')
        content: save file content

    Returns:
        {"ok": True, "path": str}

    Raises:
        ValueError: If the path fails to validate security
        RuntimeError: When the flow-claude-edit call failed
    """
    category, filename = _validate_rules_rel_path(rel_path)

    # Pass to claude_edit in the format .claude/rules/category/filename
    claude_rel_path = f'rules/{rel_path}'

    # Since open fails if there is no original, create a new file directly and then save it.
    original_path = os.path.join(project_root, '.claude', 'rules', category, filename)
    edit_dir = os.path.join(project_root, '.agent-factory', 'staging')
    edit_path = os.path.join(edit_dir, 'rules', rel_path)
    script = os.path.normpath(_CLAUDE_EDIT_SCRIPT)

    is_new = not os.path.isfile(original_path)

    if not is_new:
        # open: .claude/ -> edit/ Copy
        result = subprocess.run(
            ['python3', script, 'open', claude_rel_path],
            capture_output=True, text=True, timeout=10,
            cwd=project_root,
        )
        if result.returncode != 0:
            raise RuntimeError(f'flow-claude-edit open failed: {result.stderr.strip()}')

    # edit/ Write content to file
    os.makedirs(os.path.dirname(edit_path), exist_ok=True)
    with open(edit_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # save: edit/ -> overwrite .claude/
    result = subprocess.run(
        ['python3', script, 'save', claude_rel_path],
        capture_output=True, text=True, timeout=10,
        cwd=project_root,
    )
    if result.returncode != 0:
        raise RuntimeError(f'flow-claude-edit save failed: {result.stderr.strip()}')

    return {'ok': True, 'path': rel_path}


def _delete_rules_file(project_root: str, rel_path: str) -> dict:
    """Delete the rules file.

    . Since the claude/ sub-file is open, edit/ delete files, the original rm will be processed in order.

    Args:
        project root: Project route absolute path
        rel path: '.claude/rules/' reference path (e.g. 'workflow/general.md')

    Returns:
        {"ok": True}

    Raises:
        ValueError: If the path fails to validate security
        FileNotFoundError: If the file does not exist
        RuntimeError: When the flow-claude-edit call failed
    """
    category, filename = _validate_rules_rel_path(rel_path)
    original_path = os.path.join(project_root, '.claude', 'rules', category, filename)

    if not os.path.isfile(original_path):
        raise FileNotFoundError(f'Rules file not found: {rel_path}')

    claude_rel_path = f'rules/{rel_path}'
    script = os.path.normpath(_CLAUDE_EDIT_SCRIPT)
    edit_dir = os.path.join(project_root, '.agent-factory', 'staging')
    edit_path = os.path.join(edit_dir, 'rules', rel_path)

    # open: .claude/ -> edit/ Copy
    result = subprocess.run(
        ['python3', script, 'open', claude_rel_path],
        capture_output=True, text=True, timeout=10,
        cwd=project_root,
    )
    if result.returncode != 0:
        raise RuntimeError(f'flow-claude-edit open failed: {result.stderr.strip()}')

    # edit/delete copy
    if os.path.isfile(edit_path):
        os.remove(edit_path)

    # Delete original file
    os.remove(original_path)

    return {'ok': True}


# ---------------------------------------------------------------------------
# CLAUDE.md helpers (project root)
# ---------------------------------------------------------------------------


def _read_claude_md(project_root: str) -> dict:
    """Returns the CLAUDE.md contents of the project route.

    Args:
        project root: Project route absolute path

    Returns:
        {"name": "CLAUDE.md", "content": str, "size": int}

    Raises:
        FileNotFoundError: If CLAUDE.md does not exist
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
    """modify CLAUDE.md in project root.

    CLAUDE.md is located in the project route and is not .claude/ sub, so you can write it directly.

    Args:
        project root: Project route absolute path
        content: save file content

    Returns:
        {"ok": True}
    """
    filepath = os.path.join(project_root, 'CLAUDE.md')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return {'ok': True}


# ---------------------------------------------------------------------------
# Roadmap (.agent-factory/roadmap/ROADMAP.yaml)
# ---------------------------------------------------------------------------

ROADMAP_PATH: str = os.path.join('.agent-factory', 'roadmap', 'ROADMAP.yaml')


def _read_roadmap(project_root: str) -> dict:
    """return dict that read ROADMAP.yaml.

    If you don't have a file, you can respond to an empty phases and display the client "no data" naturally
    About Us The parsing error is that the handler responds to 500.

    Args:
        project root: Project route absolute path

    Returns:
        {"version": int, "phases": [...]}
    """
    import yaml  # Delayed import — Other board functions work even in environments where PyYAML is not installed

    filepath = os.path.join(project_root, ROADMAP_PATH)
    if not os.path.isfile(filepath):
        return {'version': 1, 'phases': []}

    with open(filepath, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        return {'version': 1, 'phases': []}

    data.setdefault('version', 1)
    data.setdefault('phases', [])
    return data


# ---------------------------------------------------------------------------
# Memory GC (.agent-factory/bin/flow-memory-gc wrapper delegate)
# ---------------------------------------------------------------------------

MEMORY_GC_BIN: str = os.path.join('.agent-factory', 'bin', 'flow-memory-gc')


def _run_memory_gc(project_root: str, subcmd: str, *args: str, timeout: int = 30) -> dict:
    """returns JSON results by calling flow-memory-gc subdirection.

    When failure {"ok": False, "error": "..."} Normalization in form.
    """
    bin_path = os.path.join(project_root, MEMORY_GC_BIN)
    if not os.path.isfile(bin_path):
        return {'ok': False, 'error': 'flow-memory-gc not found'}
    cmd = [bin_path, subcmd, *args]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=project_root,
        )
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'timeout'}
    stdout = (result.stdout or '').strip()
    stderr = (result.stderr or '').strip()
    payload: dict = {}
    if stdout.startswith('{'):
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {'raw_stdout': stdout}
    else:
        payload = {'raw_stdout': stdout}
    payload.setdefault('ok', result.returncode == 0)
    if result.returncode != 0:
        payload['error'] = stderr or stdout or f'exit {result.returncode}'
    return payload


def _memory_gc_status(project_root: str) -> dict:
    return _run_memory_gc(project_root, 'status', timeout=15)


def _memory_gc_run(project_root: str, *, dry_run: bool, with_reflection: bool) -> dict:
    args: list[str] = ['--json']
    if dry_run:
        args.append('--dry-run')
    if not with_reflection:
        args.append('--no-reflection')
    timeout = 180 if with_reflection else 60
    return _run_memory_gc(project_root, 'run', *args, timeout=timeout)


def _memory_gc_prune_archive(project_root: str, *, apply: bool) -> dict:
    args: list[str] = []
    if apply:
        args.append('--apply')
    return _run_memory_gc(project_root, 'prune-archive', *args, timeout=30)


def _trigger_memory_index_regen(project_root: str) -> None:
    """memory write/delete after index auto update — fire-and-forget.

    flow-memory-gc auto --trigger session call. 'session' trigger
    saturation only if included. skip to main content
    """
    bin_path = os.path.join(project_root, MEMORY_GC_BIN)
    if not os.path.isfile(bin_path):
        return
    try:
        subprocess.Popen(
            [bin_path, 'auto', '--trigger', 'session'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=project_root,
        )
    except OSError:
        pass
