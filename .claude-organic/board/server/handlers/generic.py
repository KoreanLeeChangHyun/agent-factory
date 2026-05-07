"""GenericHandlerMixin — api / poll / sse endpoints."""

from __future__ import annotations

import json
import os
import re
import time

# ---- flow-kanban done 결과 파싱용 정규식 상수 ----
# 성공 시 stdout 에서 merge 정보 추출: '<branch> -> develop 병합 완료 (<sha8>)'
_DONE_MERGE_OK_RE = re.compile(
    r'(.+?)\s*->\s*develop\s+병합\s+완료\s+\(([0-9a-f]{6,})\)',
)
# 충돌 헤더 라인 검출: '[ERROR]' 로 시작하는 라인
_DONE_CONFLICT_HEADER = re.compile(r'^\[ERROR\]')
# 미커밋 변경 헤더 라인 검출
_DONE_DIRTY_HEADER = re.compile(r'미커밋\s+파일\s+목록\s*:')
# 충돌/미커밋 파일 경로 라인: '    - <path>' 패턴
_DONE_PATH_RE = re.compile(r'^\s+-\s+(.+)$')

from ..state import sse_manager, poll_tracker
from .._common import (
    SERVER_STARTED_AT,
    SERVER_PID,
    _parse_env_file,
    _read_kanban_tickets,
    _read_dashboard,
    _list_workflow_entries,
    _get_git_branch,
    _workflow_detail,
    _resolve_memory_dir,
    _list_memory_files,
    _read_memory_file,
    _list_rules_files,
    _read_rules_file,
    _list_prompt_files,
    _read_prompt_file,
    _read_claude_md,
    _read_roadmap,
    _read_quick_prompts,
    _memory_gc_status,
    _memory_gc_run,
    _memory_gc_prune_archive,
    logger,
)


class GenericHandlerMixin:
    """Kanban / dashboard / workflow / memory / rules / prompt API + SSE."""

    def _handle_api(self) -> None:
        """API 요청을 라우팅한다."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        project_root = os.getcwd()

        if path == '/api/env':
            self._send_json(_parse_env_file(project_root))
        elif path == '/api/kanban':
            files_param = qs.get('files', [None])[0]
            files = files_param.split(',') if files_param else None
            self._send_json(_read_kanban_tickets(project_root, files))
        elif path == '/api/dashboard':
            self._send_json(_read_dashboard(project_root))
        elif path == '/api/workflow/entries':
            self._send_json(_list_workflow_entries(project_root))
        elif path == '/api/workflow/detail':
            entry = qs.get('entry', [None])[0]
            if not entry:
                self._send_json([])
                return
            self._send_json(_workflow_detail(project_root, entry))
        elif path == '/api/server-info':
            self._send_json({
                'pid': SERVER_PID,
                'started_at': SERVER_STARTED_AT,
            })
        elif path == '/api/branch':
            self._send_json({'branch': _get_git_branch(project_root)})
        elif path == '/api/roadmap':
            self._send_json(_read_roadmap(project_root))
        elif path == '/api/workflow/artifact':
            self._handle_workflow_artifact(qs)
        elif path == '/api/memory':
            self._send_json(_list_memory_files(project_root))
        elif path == '/api/memory/file':
            name = qs.get('name', [None])[0]
            if not name:
                self._send_error(400, 'Missing "name" query parameter')
                return
            try:
                self._send_json(_read_memory_file(project_root, name))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/rules':
            self._send_json(_list_rules_files(project_root))
        elif path == '/api/prompt/rules/file':
            rel_path = qs.get('path', [None])[0]
            if not rel_path:
                self._send_error(400, 'Missing "path" query parameter')
                return
            try:
                self._send_json(_read_rules_file(project_root, rel_path))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/prompt-files':
            self._send_json(_list_prompt_files(project_root))
        elif path == '/api/prompt/prompt-files/file':
            name = qs.get('name', [None])[0]
            if not name:
                self._send_error(400, 'Missing "name" query parameter')
                return
            try:
                self._send_json(_read_prompt_file(project_root, name))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/claude-md':
            try:
                self._send_json(_read_claude_md(project_root))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/quick-prompts':
            self._send_json(_read_quick_prompts(project_root))
        elif path == '/api/memory/gc/status':
            self._send_json(_memory_gc_status(project_root))
        else:
            self.send_response(404)
            self.end_headers()

    # ---------------- Memory GC POST handlers ----------------

    def _handle_memory_gc_run(self) -> None:
        """POST /api/memory/gc/run — body {"dry_run": bool, "with_reflection": bool}"""
        data = self._read_json_body() or {}
        dry_run = bool(data.get('dry_run', False))
        with_reflection = bool(data.get('with_reflection', False))
        result = _memory_gc_run(
            os.getcwd(), dry_run=dry_run, with_reflection=with_reflection,
        )
        self._send_json(result)

    def _handle_memory_gc_prune(self) -> None:
        """POST /api/memory/gc/prune-archive — body {"apply": bool}"""
        data = self._read_json_body() or {}
        apply = bool(data.get('apply', False))
        result = _memory_gc_prune_archive(os.getcwd(), apply=apply)
        self._send_json(result)

    # ---------------- Kanban DnD POST handler ----------------

    def _handle_kanban_move(self) -> None:
        """POST /api/kanban/move — body {"ticket": "T-NNN", "to": "todo"|"open"}.

        칸반 보드 DnD 로 To Do ↔ Open 전이만 허용한다 (안전 DnD 정책).
        다른 전이 (In Progress / Review / Done) 는 부수 효과를 동반하므로
        명시적 명령 (/wf -s, /wf -d) 으로만 가능.

        내부적으로 `flow-kanban move T-NNN <to>` 를 호출하여 FSM 검증 + 파일 이동
        + 로그 기록까지 위임한다.
        """
        import subprocess

        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        to = (data.get('to') or '').strip().lower()

        # 입력 검증
        if not ticket or not ticket.startswith('T-'):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return
        if to not in ('todo', 'open'):
            self._send_error(400, 'DnD allows only To Do ↔ Open transitions ("to" must be "todo" or "open")')
            return

        # flow-kanban move 호출 (FSM 검증 + 파일 이동 + 로그)
        project_root = os.getcwd()
        flow_kanban = os.path.join(project_root, '.claude-organic', 'bin', 'flow-kanban')
        try:
            result = subprocess.run(
                [flow_kanban, 'move', ticket, to],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-kanban move timed out')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-kanban not found: {flow_kanban}')
            return

        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or '').strip()
            self._send_error(400, f'flow-kanban move failed: {stderr}')
            return

        self._send_json({
            'ok': True,
            'ticket': ticket,
            'to': to,
            'stdout': result.stdout.strip(),
        })

    def _handle_kanban_submit(self) -> None:
        """POST /api/kanban/submit — body {"ticket": "T-NNN", "command": "implement|research|review"}.

        프론트 DnD Open → In Progress drop confirm 모달의 [실행] 버튼이
        호출하는 단일 진입점. launcher 가 ① progress 이동 ② command 정규화
        ③ LLM spawn 을 모두 흡수하므로 핸들러는 위임만 담당한다 (T-399).

        응답: {ok: bool, mode: "launched"|"inline"|"error",
               session_id?: str, message: str}
        """
        import re
        import subprocess

        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        command = (data.get('command') or '').strip()

        # 입력 검증
        if not ticket or not re.match(r'^T-\d+$', ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return
        if command not in ('implement', 'research', 'review'):
            self._send_error(400, 'Invalid "command" (must be implement/research/review)')
            return

        # flow-launcher launch 호출 — launcher 가 ① progress 이동 ② command 정규화
        # ③ LLM spawn 을 모두 처리한다.
        project_root = os.getcwd()
        flow_launcher = os.path.join(project_root, '.claude-organic', 'bin', 'flow-launcher')
        try:
            result = subprocess.run(
                [flow_launcher, 'launch', ticket, command],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-launcher launch timed out')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-launcher not found: {flow_launcher}')
            return

        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or '').strip()
            self._send_error(400, f'flow-launcher launch failed: {stderr}')
            return

        # stdout prefix 파싱: LAUNCH:/INLINE:
        stdout = result.stdout.strip()
        first_line = stdout.split('\n', 1)[0].strip() if stdout else ''
        if first_line.startswith('LAUNCH:'):
            # "LAUNCH: <session_id> 실행 중" 형태에서 session_id 추출
            mode = 'launched'
            tail = first_line[len('LAUNCH:'):].strip()
            session_id = tail.split()[0] if tail else ''
            payload = {
                'ok': True,
                'mode': mode,
                'ticket': ticket,
                'session_id': session_id,
                'message': first_line,
            }
        elif first_line.startswith('INLINE:'):
            mode = 'inline'
            payload = {
                'ok': True,
                'mode': mode,
                'ticket': ticket,
                'message': first_line,
            }
        else:
            payload = {
                'ok': True,
                'mode': 'unknown',
                'ticket': ticket,
                'message': first_line or 'no stdout',
            }
        self._send_json(payload)

    def _handle_kanban_done(self) -> None:
        """POST /api/kanban/done — body {"ticket": "T-NNN"}.

        칸반 보드 DnD Review → Done 전이의 단일 진입점.
        내부적으로 `flow-kanban done <ticket>` 을 호출하여
        merge_to_develop + worktree 정리 + 칸반 Done 전이를 위임한다 (T-906).

        성공 응답 (200):
            {ok: true, ticket, merge_commit, merged_branch, stdout}

        실패 응답 (409):
            {ok: false, error_kind: 'merge_conflict'|'dirty_worktree'|'other',
             conflicts: [...], dirty_files: [...], message}

        타임아웃(504) / 실행파일 없음(500) 은 기존 핸들러 패턴과 동일.
        """
        import subprocess

        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()

        # 입력 검증 — ^T-\d+$ 형식만 허용
        if not ticket or not re.match(r'^T-\d+$', ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        # Review 상태 사전 확인 — review/ 디렉터리에 티켓 XML 존재 여부로 판별
        # (T-906 워커가 _read_kanban_tickets 반환 타입 dict[파일명,XML]을 list[dict]로 잘못 가정해
        # 항상 fail 하던 회귀 수정)
        project_root = os.getcwd()
        review_xml = os.path.join(
            project_root, '.claude-organic', 'tickets', 'review', f'{ticket}.xml',
        )
        if not os.path.isfile(review_xml):
            self._send_error(
                400,
                f'{ticket} is not in Review column (current state check failed)',
            )
            return

        # flow-kanban done 호출 — merge 시간 고려해 timeout 120초
        flow_kanban = os.path.join(
            project_root, '.claude-organic', 'bin', 'flow-kanban',
        )
        try:
            result = subprocess.run(
                [flow_kanban, 'done', ticket],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-kanban done timed out (120s)')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-kanban not found: {flow_kanban}')
            return

        stdout = result.stdout or ''

        if result.returncode == 0:
            # 성공 — stdout 에서 merge 정보 추출
            merge_commit = ''
            merged_branch = ''
            for line in stdout.splitlines():
                m = _DONE_MERGE_OK_RE.search(line)
                if m:
                    merged_branch = m.group(1).strip()
                    merge_commit = m.group(2).strip()
                    break
            self._send_json({
                'ok': True,
                'ticket': ticket,
                'merge_commit': merge_commit,
                'merged_branch': merged_branch,
                'stdout': stdout.strip(),
            })
            return

        # 실패 — stdout 줄 단위 분석으로 error_kind 분류
        lines = stdout.splitlines()
        error_kind = 'other'
        conflicts: list[str] = []
        dirty_files: list[str] = []
        error_message = ''
        in_dirty_block = False

        for line in lines:
            if _DONE_CONFLICT_HEADER.match(line):
                error_kind = 'merge_conflict'
                error_message = line.strip()
                in_dirty_block = False
            elif _DONE_DIRTY_HEADER.search(line):
                error_kind = 'dirty_worktree'
                in_dirty_block = True
            elif _DONE_PATH_RE.match(line):
                path_val = _DONE_PATH_RE.match(line).group(1).strip()
                if error_kind == 'merge_conflict':
                    conflicts.append(path_val)
                elif in_dirty_block:
                    dirty_files.append(path_val)
            else:
                in_dirty_block = False
                if not error_message and line.strip():
                    error_message = line.strip()

        stderr_text = (result.stderr or '').strip()
        if not error_message and stderr_text:
            error_message = stderr_text

        self._send_json_with_status(409, {
            'ok': False,
            'error_kind': error_kind,
            'conflicts': conflicts,
            'dirty_files': dirty_files,
            'message': error_message,
            'ticket': ticket,
        })

    def _send_json_with_status(self, status: int, data: object) -> None:
        """지정한 HTTP 상태 코드로 JSON 응답을 전송한다."""
        import json as _json
        body = _json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _handle_poll(self) -> None:
        """폴링 엔드포인트를 처리한다.

        마지막 폴링 이후 변경된 이벤트 타입 목록을 JSON으로 응답한다.
        """
        changes = poll_tracker.flush()
        body = json.dumps(changes).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _handle_sse(self) -> None:
        """SSE 엔드포인트를 처리한다.

        연결을 유지하며 FileWatcher의 이벤트를 클라이언트에 스트리밍한다.
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 연결 확인용 초기 주석 전송
        try:
            self.wfile.write(b': connected\n\n')
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

        sse_manager.add(self.wfile)
        try:
            # 연결이 유지되는 동안 대기
            while True:
                time.sleep(1)
                # keep-alive 주석 전송으로 연결 상태 확인
                client_lock = sse_manager.get_lock(self.wfile)
                if client_lock is None:
                    break
                try:
                    with client_lock:
                        self.wfile.write(b': heartbeat\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            sse_manager.remove(self.wfile)
