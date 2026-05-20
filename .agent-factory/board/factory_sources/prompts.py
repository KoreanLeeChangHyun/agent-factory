"""Prompt file data access for the Board factory panel."""

from __future__ import annotations

import os
import re
import time

# prompt 파일명 허용 패턴: 알파벳, 숫자, 하이픈, 언더스코어, 점
_PROMPT_FILENAME_RE = re.compile(r'^[A-Za-z0-9_\-\.]+$')


def _prompt_files_dir(project_root: str) -> str:
    return os.path.join(project_root, '.agent-factory', 'board', 'config', 'prompt-files')


def _validate_prompt_filename(filename: str) -> None:
    """prompt 파일명의 보안 검증을 수행한다."""
    if '..' in filename or '/' in filename or '\\' in filename:
        raise ValueError(f'Invalid filename: {filename}')
    if not _PROMPT_FILENAME_RE.match(filename):
        raise ValueError(f'Invalid filename format: {filename}')


def _list_prompt_files(project_root: str) -> list[dict]:
    """'.agent-factory/board/config/prompt-files/' 하위 모든 파일 목록을 반환한다."""
    prompt_dir = _prompt_files_dir(project_root)
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
    """prompt 파일 1개의 내용을 읽어 반환한다."""
    _validate_prompt_filename(filename)
    prompt_dir = _prompt_files_dir(project_root)
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
    """.agent-factory/board/config/prompt-files/ 파일을 생성하거나 수정한다."""
    _validate_prompt_filename(filename)
    prompt_dir = _prompt_files_dir(project_root)
    os.makedirs(prompt_dir, exist_ok=True)
    filepath = os.path.join(prompt_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return {'ok': True, 'name': filename}


def _delete_prompt_file(project_root: str, filename: str) -> dict:
    """.agent-factory/board/config/prompt-files/ 파일을 삭제한다."""
    _validate_prompt_filename(filename)
    prompt_dir = _prompt_files_dir(project_root)
    filepath = os.path.join(prompt_dir, filename)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f'Prompt file not found: {filename}')

    os.remove(filepath)
    return {'ok': True}
