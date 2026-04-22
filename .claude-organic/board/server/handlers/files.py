"""FilesHandlerMixin — memory / rules / prompt / CLAUDE.md write endpoints."""

from __future__ import annotations

import json

from .._common import (
    _write_memory_file,
    _delete_memory_file,
    _write_rules_file,
    _delete_rules_file,
    _write_prompt_file,
    _delete_prompt_file,
    _write_claude_md,
    logger,
)


class FilesHandlerMixin:
    """File write / delete handlers.

    Expects the base class to provide:
      self._send_json(data: dict) -> None
      self._send_error(code: int, msg: str) -> None
      self._read_json_body() -> dict
      self.path: str (HTTP request path)
      self.command: str (HTTP method)
    """

    def _handle_memory_write(self) -> None:
        """메모리 파일 생성/수정 엔드포인트를 처리한다.

        POST /api/memory/file: 요청 본문 {"name": "filename.md", "content": "..."}
        """
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_error(400, 'Empty request body')
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
            return

        name = data.get('name', '')
        content = data.get('content', '')
        if not name:
            self._send_error(400, 'Missing "name" field')
            return

        try:
            result = _write_memory_file(os.getcwd(), name, content)
            self._send_json(result)
        except ValueError as e:
            self._send_error(400, str(e))

    def _handle_rules_write(self) -> None:
        """rules 파일 생성/수정 엔드포인트를 처리한다.

        POST /api/prompt/rules/file: 요청 본문 {"path": "category/filename.md", "content": "..."}
        """
        data = self._read_json_body()
        if data is None:
            return

        rel_path = data.get('path', '')
        content = data.get('content', '')
        if not rel_path:
            self._send_error(400, 'Missing "path" field')
            return

        try:
            result = _write_rules_file(os.getcwd(), rel_path, content)
            self._send_json(result)
        except ValueError as e:
            self._send_error(400, str(e))
        except RuntimeError as e:
            self._send_error(500, str(e))

    def _handle_prompt_write(self) -> None:
        """prompt 파일 생성/수정 엔드포인트를 처리한다.

        POST /api/prompt/prompt-files/file: 요청 본문 {"name": "filename", "content": "..."}
        """
        data = self._read_json_body()
        if data is None:
            return

        name = data.get('name', '')
        content = data.get('content', '')
        if not name:
            self._send_error(400, 'Missing "name" field')
            return

        try:
            result = _write_prompt_file(os.getcwd(), name, content)
            self._send_json(result)
        except ValueError as e:
            self._send_error(400, str(e))

    def _handle_claude_md_write(self) -> None:
        """CLAUDE.md 수정 엔드포인트를 처리한다.

        POST /api/prompt/claude-md: 요청 본문 {"content": "..."}
        """
        data = self._read_json_body()
        if data is None:
            return

        content = data.get('content')
        if content is None:
            self._send_error(400, 'Missing "content" field')
            return

        result = _write_claude_md(os.getcwd(), content)
        self._send_json(result)
