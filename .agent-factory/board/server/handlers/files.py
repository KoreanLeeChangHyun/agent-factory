"""FilesHandlerMixin — memory / rules / prompt / CLAUDE.md write endpoints."""

from __future__ import annotations

import json
import os

from .._common import (
    api_endpoint,
    _write_memory_file,
    _delete_memory_file,
    _write_rules_file,
    _delete_rules_file,
    _write_prompt_file,
    _delete_prompt_file,
    _write_claude_md,
    _write_quick_prompt,
    _delete_quick_prompt,
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

    @api_endpoint("M", "save")
    def _handle_memory_write(self) -> None:
        """메모리 파일 생성/수정 엔드포인트를 처리한다.

        method: POST
        url: /api/memory/file
        domain: M
        handler: FilesHandlerMixin._handle_memory_write
        request: body {name: str, content: str}
        response_ok: {ok: true, name: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400
        auth: none (local-only)
        side_effects: write to .claude/.. memory file
        sse_events: memory_update (via FileWatcher)
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

    @api_endpoint("M", "delete")
    def _handle_memory_delete(self) -> None:
        """메모리 파일 삭제 엔드포인트를 처리한다.

        method: DELETE
        url: /api/memory/file
        domain: M
        handler: FilesHandlerMixin._handle_memory_delete
        request: query {name: str}
        response_ok: {ok: true, name: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404
        auth: none (local-only)
        side_effects: remove memory file
        sse_events: memory_update (via FileWatcher)
        """
        name = self._parse_query_param('name')
        if not name:
            self._send_error(400, 'Missing "name" query parameter')
            return
        try:
            self._send_json(_delete_memory_file(os.getcwd(), name))
        except ValueError as e:
            self._send_error(400, str(e))
        except FileNotFoundError as e:
            self._send_error(404, str(e))

    @api_endpoint("M", "rules_save")
    def _handle_rules_write(self) -> None:
        """rules 파일 생성/수정 엔드포인트를 처리한다.

        method: POST
        url: /api/prompt/rules/file
        domain: M
        handler: FilesHandlerMixin._handle_rules_write
        request: body {path: str (category/filename.md), content: str}
        response_ok: {ok: true, path: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 500
        auth: none (local-only) — claude_edit subprocess 경유
        side_effects: write to .claude/rules/.. via claude_edit
        sse_events: none (direct file write)
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

    @api_endpoint("M", "rules_delete")
    def _handle_rules_delete(self) -> None:
        """rules 파일 삭제 엔드포인트를 처리한다.

        method: DELETE
        url: /api/prompt/rules/file
        domain: M
        handler: FilesHandlerMixin._handle_rules_delete
        request: query {path: str (relative)}
        response_ok: {ok: true, path: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404, 500
        auth: none (local-only)
        side_effects: remove rules file
        sse_events: none
        """
        rel_path = self._parse_query_param('path')
        if not rel_path:
            self._send_error(400, 'Missing "path" query parameter')
            return
        try:
            self._send_json(_delete_rules_file(os.getcwd(), rel_path))
        except ValueError as e:
            self._send_error(400, str(e))
        except FileNotFoundError as e:
            self._send_error(404, str(e))
        except RuntimeError as e:
            self._send_error(500, str(e))

    @api_endpoint("PR", "save")
    def _handle_prompt_write(self) -> None:
        """prompt 파일 생성/수정 엔드포인트를 처리한다.

        method: POST
        url: /api/prompt/prompt-files/file
        domain: PR
        handler: FilesHandlerMixin._handle_prompt_write
        request: body {name: str, content: str}
        response_ok: {ok: true, name: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400
        auth: none (local-only)
        side_effects: write to prompts directory
        sse_events: none
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

    @api_endpoint("PR", "delete")
    def _handle_prompt_delete(self) -> None:
        """prompt 파일 삭제 엔드포인트를 처리한다.

        method: DELETE
        url: /api/prompt/prompt-files/file
        domain: PR
        handler: FilesHandlerMixin._handle_prompt_delete
        request: query {name: str}
        response_ok: {ok: true, name: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404
        auth: none (local-only)
        side_effects: remove prompt file
        sse_events: none
        """
        name = self._parse_query_param('name')
        if not name:
            self._send_error(400, 'Missing "name" query parameter')
            return
        try:
            self._send_json(_delete_prompt_file(os.getcwd(), name))
        except ValueError as e:
            self._send_error(400, str(e))
        except FileNotFoundError as e:
            self._send_error(404, str(e))

    @api_endpoint("PR", "claude_md_save")
    def _handle_claude_md_write(self) -> None:
        """CLAUDE.md 수정 엔드포인트를 처리한다.

        method: POST
        url: /api/prompt/claude-md
        domain: PR
        handler: FilesHandlerMixin._handle_claude_md_write
        request: body {content: str}
        response_ok: {ok: true}
        response_error: {ok: false, error: str}
        status_codes: 200, 400
        auth: none (local-only)
        side_effects: write to CLAUDE.md root file
        sse_events: none
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

    @api_endpoint("PR", "quick_save")
    def _handle_quick_prompt_write(self) -> None:
        """quick prompt 단건 생성/갱신 엔드포인트.

        method: POST
        url: /api/quick-prompts/item
        domain: PR
        handler: FilesHandlerMixin._handle_quick_prompt_write
        request: body {id: str, prompt: str, label?: str, bindTo?: str, description?: str}
        response_ok: {ok: true, id: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400
        auth: none (local-only)
        side_effects: write to quick-prompts.json
        sse_events: none
        """
        data = self._read_json_body()
        if data is None:
            return

        prompt_id = data.get('id', '')
        if not prompt_id:
            self._send_error(400, 'Missing "id" field')
            return

        try:
            result = _write_quick_prompt(os.getcwd(), prompt_id, data)
            self._send_json(result)
        except ValueError as e:
            self._send_error(400, str(e))

    @api_endpoint("PR", "quick_delete")
    def _handle_quick_prompt_delete(self) -> None:
        """quick prompt 단건 삭제 엔드포인트.

        method: DELETE
        url: /api/quick-prompts/item
        domain: PR
        handler: FilesHandlerMixin._handle_quick_prompt_delete
        request: query {id: str}
        response_ok: {ok: true, id: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404
        auth: none (local-only)
        side_effects: remove quick-prompt entry
        sse_events: none
        """
        prompt_id = self._parse_query_param('id')
        if not prompt_id:
            self._send_error(400, 'Missing "id" query parameter')
            return

        try:
            result = _delete_quick_prompt(os.getcwd(), prompt_id)
            self._send_json(result)
        except ValueError as e:
            self._send_error(400, str(e))
        except FileNotFoundError as e:
            self._send_error(404, str(e))
