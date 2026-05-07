"""GenericHandlerMixin — api / poll / sse endpoints."""

from __future__ import annotations

import json
import os
import re
import sys
import time

# ---- flow-kanban done 결과 파싱용 정규식 상수 ----
# 성공 시 stdout 에서 merge 정보 추출: '<branch> -> develop 병합 완료 (<sha8>)'
_DONE_MERGE_OK_RE = re.compile(
    r'(.+?)\s*->\s*develop\s+병합\s+완료\s+\(([0-9a-f]{6,})\)',
)

# ---- force done / delete 관련 상수 (T-418) ----
# 티켓 번호 형식 정규식
_TICKET_RE = re.compile(r'^T-\d+$')
# 칸반 전체 디렉터리 목록 (derived-from 가드에서 사용)
_KANBAN_ALL_DIRS = ('todo', 'open', 'progress', 'review', 'done')
# 충돌 헤더 라인 검출: '[ERROR]' 로 시작하는 라인
_DONE_CONFLICT_HEADER = re.compile(r'^\[ERROR\]')
# 미커밋 변경 헤더 라인 검출
_DONE_DIRTY_HEADER = re.compile(r'미커밋\s+파일\s+목록\s*:')
# 충돌/미커밋 파일 경로 라인: '    - <path>' 패턴
_DONE_PATH_RE = re.compile(r'^\s+-\s+(.+)$')
# rc=0 이지만 merge_commit 이 빈 문자열일 때 재판별용:
# cmd_done 의 '[WARN] worktree 병합 실패: 병합 충돌 발생: ...' 형식 매칭
_DONE_CONFLICT_WARN_RE = re.compile(
    r'\[WARN\].*(병합\s*충돌|merge\s+conflict)',
    re.IGNORECASE,
)

# ---- flow-undo-done 결과 파싱용 정규식 상수 (T-905 Phase 3) ----
# 전략 식별: '[undo-done] 전략 1: reset --hard 진행' / '전략 2: revert -m 1 진행'
_UNDO_STRATEGY_RESET = re.compile(r'\[undo-done\]\s+전략\s+1\s*:\s*reset')
_UNDO_STRATEGY_REVERT = re.compile(r'\[undo-done\]\s+전략\s+2\s*:\s*revert')
# 워크트리 재생성 정보: '[undo-done] 워크트리 재생성 완료: path=<path> branch=<branch>'
_UNDO_WORKTREE_RE = re.compile(
    r'\[undo-done\]\s+워크트리\s+재생성\s+완료\s*:\s*path=(\S+)\s+branch=(\S+)',
)
# 에러 라인: '[undo-done] ERROR: <message>'
_UNDO_ERROR_RE = re.compile(r'\[undo-done\]\s+ERROR\s*:\s*(.+)')

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



def _classify_done_failure(stdout: str, stderr: str) -> dict:
    """flow-kanban done 실패(또는 rc=0 + 빈 hash) 시 stdout/stderr 를 분석해 error_kind 를 분류한다.

    반환 dict 구조:
        {
            'error_kind': 'merge_conflict' | 'dirty_worktree' | 'other',
            'conflicts':  list[str],   # 충돌 파일 경로 목록
            'dirty_files': list[str],  # 미커밋 파일 목록
            'message':    str,         # 사용자 표시용 에러 메시지
        }

    우선순위:
        1. '[ERROR]' 헤더 라인 → merge_conflict (기존 fail 분기 패턴)
        2. _DONE_CONFLICT_WARN_RE 패턴 → merge_conflict (rc=0 + 빈 hash 보조 판별)
        3. '미커밋 파일 목록:' 헤더 라인 → dirty_worktree
        4. 그 외 → other
    """
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
        elif _DONE_CONFLICT_WARN_RE.search(line):
            # rc=0 + 빈 hash 케이스: '[WARN] worktree 병합 실패: 병합 충돌 발생: ...' 매칭
            if error_kind == 'other':
                error_kind = 'merge_conflict'
            if not error_message:
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

    stderr_text = stderr.strip()
    if not error_message and stderr_text:
        error_message = stderr_text

    return {
        'error_kind': error_kind,
        'conflicts': conflicts,
        'dirty_files': dirty_files,
        'message': error_message,
    }


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
        elif path.startswith('/api/metrics/run/'):
            # /api/metrics/run/<registryKey> — 단일 워크플로우 집계
            registry_key = path[len('/api/metrics/run/'):].strip('/')
            self._handle_metrics_run(registry_key)
        elif path == '/api/metrics/aggregate':
            # /api/metrics/aggregate?last=N — 최근 N개 run summary 리스트
            last = self._parse_metrics_last(qs, default=20)
            self._handle_metrics_aggregate(last)
        elif path == '/api/metrics/regression':
            # /api/metrics/regression?last=N — 회귀 패턴 빈도 + 예시
            last = self._parse_metrics_last(qs, default=20)
            self._handle_metrics_regression(last)
        elif path == '/api/worktree/status/all':
            # GET /api/worktree/status/all — 전체 워크트리 상태 list
            self._handle_worktree_status_all()
        elif path == '/api/worktree/status':
            # GET /api/worktree/status?ticket=T-NNN — 단일 티켓 워크트리 상태
            ticket = qs.get('ticket', [None])[0]
            if not ticket:
                self._send_error(400, 'Missing "ticket" query parameter (e.g. ?ticket=T-NNN)')
                return
            self._handle_worktree_status(ticket)
        else:
            self.send_response(404)
            self.end_headers()

    # ---------------- Metrics handlers (W06) ----------------

    @staticmethod
    def _parse_metrics_last(qs: dict, default: int) -> int:
        """쿼리스트링 last 파라미터를 안전하게 정수로 파싱한다.

        음수/0/비정수는 default 로 보정한다 (잘못된 입력에 graceful 처리).
        """
        raw = (qs.get('last') or [None])[0]
        if raw is None:
            return default
        try:
            v = int(raw)
        except (TypeError, ValueError):
            return default
        return v if v > 0 else default

    @staticmethod
    def _import_metrics_cli():
        """metrics_cli 모듈을 lazy import 한다.

        engine/ 디렉터리를 sys.path 에 추가한 뒤 ``flow.metrics_cli`` 를
        import. board 서버의 sys.path 에는 board/ 만 등록되어 있으므로
        엔진 import 가 필요한 시점에서만 path 를 보충한다.
        """
        engine_dir = os.path.normpath(
            os.path.join(os.getcwd(), '.claude-organic', 'engine'),
        )
        if engine_dir not in sys.path:
            sys.path.insert(0, engine_dir)
        from flow import metrics_cli  # noqa: WPS433
        return metrics_cli

    def _handle_metrics_run(self, registry_key: str) -> None:
        """GET /api/metrics/run/<registryKey> — 단일 워크플로우 집계 결과 응답."""
        if not registry_key or len(registry_key) != 15 or registry_key[8] != '-':
            self._send_error(400, 'Invalid registryKey (expected YYYYMMDD-HHMMSS)')
            return
        try:
            cli = self._import_metrics_cli()
            data = cli.aggregate_run(registry_key)
        except Exception as exc:  # noqa: BLE001
            logger.exception('metrics.run failed: %s', exc)
            self._send_error(500, f'aggregate_run failed: {exc}')
            return
        self._send_json(data)

    def _handle_metrics_aggregate(self, last: int) -> None:
        """GET /api/metrics/aggregate?last=N — 최근 N개 run summary list 응답."""
        try:
            cli = self._import_metrics_cli()
            data = cli.aggregate_recent(last)
        except Exception as exc:  # noqa: BLE001
            logger.exception('metrics.aggregate failed: %s', exc)
            self._send_error(500, f'aggregate_recent failed: {exc}')
            return
        # 프론트가 쉽게 다루도록 list 를 dict 로 한번 더 감싼다 (last 메타 포함).
        self._send_json({
            'last': last,
            'count': len(data),
            'runs': data,
        })

    def _handle_metrics_regression(self, last: int) -> None:
        """GET /api/metrics/regression?last=N — 회귀 패턴 빈도 + 예시 응답."""
        try:
            cli = self._import_metrics_cli()
            data = cli.regression_counts(last)
        except Exception as exc:  # noqa: BLE001
            logger.exception('metrics.regression failed: %s', exc)
            self._send_error(500, f'regression_counts failed: {exc}')
            return
        # last 를 결과에 합쳐서 프론트가 호출 컨텍스트를 알 수 있게 한다.
        data = dict(data)
        data['last'] = last
        self._send_json(data)

    # ---------------- Worktree status handlers (T-419) ----------------

    @staticmethod
    def _import_worktree_status():
        """worktree_status 모듈을 lazy import 한다.

        engine/ 디렉터리를 sys.path 에 추가한 뒤 ``flow.worktree_status`` 를
        import. _import_metrics_cli 패턴과 동일한 방식으로 board 서버 sys.path
        를 보충한다.
        """
        engine_dir = os.path.normpath(
            os.path.join(os.getcwd(), '.claude-organic', 'engine'),
        )
        if engine_dir not in sys.path:
            sys.path.insert(0, engine_dir)
        from flow import worktree_status  # noqa: WPS433
        return worktree_status

    def _handle_worktree_status(self, ticket: str) -> None:
        """GET /api/worktree/status?ticket=T-NNN — 단일 티켓 워크트리 상태 응답.

        결과가 None(티켓에 해당하는 워크트리 미존재)이어도 200 + {exists: false} 응답.
        클라이언트가 exists 필드로 존재 여부를 판단한다.
        """
        try:
            mod = self._import_worktree_status()
            data = mod.get_worktree_status(ticket)
        except Exception as exc:  # noqa: BLE001
            logger.exception('worktree_status.single failed: %s', exc)
            self._send_error(500, f'get_worktree_status failed: {exc}')
            return
        if data is None:
            data = {'ticket': ticket, 'exists': False}
        self._send_json(data)

    def _handle_worktree_status_all(self) -> None:
        """GET /api/worktree/status/all — 전체 워크트리 상태 list 응답."""
        try:
            mod = self._import_worktree_status()
            data = mod.get_all_worktree_statuses()
        except Exception as exc:  # noqa: BLE001
            logger.exception('worktree_status.all failed: %s', exc)
            self._send_error(500, f'get_all_worktree_statuses failed: {exc}')
            return
        self._send_json(data)

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

    def _get_dirty_files(self, wt_path: str) -> list[str]:
        """워크트리 경로에서 미커밋 파일 목록을 반환한다.

        ``git status --porcelain`` 출력을 파싱하여 파일 경로 목록을 반환한다.
        경로가 존재하지 않거나 git 명령 실패 시 빈 리스트를 반환한다.

        Args:
            wt_path: 검사할 worktree 디렉터리 절대경로.

        Returns:
            미커밋 파일 경로 목록 (상대 경로).
        """
        import subprocess
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=wt_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return []
            files = []
            for line in result.stdout.splitlines():
                # porcelain 형식: "XY path" 또는 "XY orig -> path"
                parts = line[3:].split(' -> ')
                files.append(parts[-1].strip())
            return files
        except Exception:
            return []

    def _check_derived_blocked(self, ticket: str, kanban_base: str) -> list[str]:
        """ticket 을 derived-from 으로 참조하는 파생 티켓 중 Done 이외 상태인 것을 반환한다.

        done_relation_guard.py 의 _find_derived_tickets + _get_ticket_status 패턴 답습.

        Args:
            ticket: 원본 티켓 번호 (예: 'T-NNN').
            kanban_base: .claude-organic/tickets/ 절대경로.

        Returns:
            Done 이외 상태인 파생 티켓 문자열 목록 (예: ['T-001(Open)', 'T-002(In Progress)']).
        """
        import xml.etree.ElementTree as ET

        not_done: list[str] = []
        for d in _KANBAN_ALL_DIRS:
            dir_path = os.path.join(kanban_base, d)
            if not os.path.isdir(dir_path):
                continue
            try:
                for entry in os.scandir(dir_path):
                    if not entry.is_file() or not entry.name.endswith('.xml'):
                        continue
                    try:
                        tree = ET.parse(entry.path)
                        for rel in tree.findall('.//relations/relation'):
                            if (rel.get('type') == 'derived-from'
                                    and rel.get('ticket') == ticket):
                                num_el = tree.find('.//metadata/number')
                                status_el = tree.find('.//metadata/status')
                                num = (num_el.text or '').strip() if num_el is not None else ''
                                status = (status_el.text or '').strip() if status_el is not None else ''
                                if status != 'Done' and num:
                                    not_done.append(f'{num}({status or "?"})')
                    except Exception:
                        continue
            except OSError:
                continue
        return not_done

    def _handle_kanban_done(self) -> None:
        """POST /api/kanban/done — body {"ticket": "T-NNN", "force": bool, "force_dirty": bool}.

        칸반 보드 DnD 의 단일 진입점.

        force=false (기본): Review → Done 전이.
            내부적으로 `flow-kanban done <ticket>` 을 호출하여
            merge_to_develop + worktree 정리 + 칸반 Done 전이를 위임한다 (T-906).

        force=true (T-418 신규): Open → Done 직접 전이.
            1. open/<ticket>.xml 존재 검증
            2. dirty 워크트리 가드 (force_dirty=false 면 409 차단)
            3. flow-kanban move <ticket> done --force 호출
            4. worktree_manager.remove_worktree 로 워크트리/브랜치 정리

        성공 응답 (200):
            Review→Done: {ok: true, ticket, merge_commit, merged_branch, stdout}
            Open→Done:   {ok: true, ticket, force: true, stdout}

        실패 응답 (409):
            {ok: false, error_kind: 'merge_conflict'|'dirty_worktree'|'derived_blocked'|'other',
             conflicts: [...], dirty_files: [...], message}

        타임아웃(504) / 실행파일 없음(500) 은 기존 핸들러 패턴과 동일.
        """
        import subprocess

        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        force = bool(data.get('force', False))
        force_dirty = bool(data.get('force_dirty', False))

        # 입력 검증 — ^T-\d+$ 형식만 허용
        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        project_root = os.getcwd()
        flow_kanban = os.path.join(
            project_root, '.claude-organic', 'bin', 'flow-kanban',
        )

        # ── force=true 분기: Open → Done 직접 전이 (T-418) ──────────────────
        if force:
            open_xml = os.path.join(
                project_root, '.claude-organic', 'tickets', 'open', f'{ticket}.xml',
            )
            if not os.path.isfile(open_xml):
                self._send_error(
                    400,
                    f'{ticket} is not in Open column (force done requires Open status)',
                )
                return

            # 워크트리 dirty 가드
            wt_path: str | None = None
            try:
                engine_dir = os.path.join(project_root, '.claude-organic', 'engine')
                if engine_dir not in sys.path:
                    sys.path.insert(0, engine_dir)
                from flow import worktree_manager  # noqa: WPS433
                wt_path = worktree_manager.get_worktree_path(ticket, repo_path=project_root)
                if wt_path and worktree_manager.has_uncommitted_changes(wt_path):
                    if not force_dirty:
                        dirty_files = self._get_dirty_files(wt_path)
                        self._send_json_with_status(409, {
                            'ok': False,
                            'error_kind': 'dirty_worktree',
                            'conflicts': [],
                            'dirty_files': dirty_files,
                            'message': f'{ticket} 워크트리에 미커밋 변경이 있습니다. force_dirty=true 로 재시도하거나 취소하세요.',
                            'ticket': ticket,
                        })
                        return
            except ImportError:
                # 워크트리 비활성 환경 — 가드 생략
                wt_path = None

            # flow-kanban move <ticket> done --force 호출
            try:
                result = subprocess.run(
                    [flow_kanban, 'move', ticket, 'done', '--force'],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.TimeoutExpired:
                self._send_error(504, 'flow-kanban move timed out (30s)')
                return
            except FileNotFoundError:
                self._send_error(500, f'flow-kanban not found: {flow_kanban}')
                return

            if result.returncode != 0:
                stderr = (result.stderr or result.stdout or '').strip()
                self._send_json_with_status(409, {
                    'ok': False,
                    'error_kind': 'other',
                    'conflicts': [],
                    'dirty_files': [],
                    'message': stderr or 'flow-kanban move done --force failed',
                    'ticket': ticket,
                })
                return

            # 워크트리 정리 (force=True: lock 해제 후 강제 삭제)
            worktree_removed = False
            if wt_path:
                try:
                    engine_dir = os.path.join(project_root, '.claude-organic', 'engine')
                    if engine_dir not in sys.path:
                        sys.path.insert(0, engine_dir)
                    from flow import worktree_manager as _wm  # noqa: WPS433
                    worktree_removed = _wm.remove_worktree(
                        ticket, delete_branch=True, repo_path=project_root,
                    )
                except ImportError:
                    pass

            self._send_json({
                'ok': True,
                'ticket': ticket,
                'force': True,
                'worktree_removed': worktree_removed,
                'stdout': (result.stdout or '').strip(),
            })
            return

        # ── force=false 분기: Review → Done 전이 (기존 T-906 로직) ──────────
        # Review 상태 사전 확인 — review/ 디렉터리에 티켓 XML 존재 여부로 판별
        # (T-906 워커가 _read_kanban_tickets 반환 타입 dict[파일명,XML]을 list[dict]로 잘못 가정해
        # 항상 fail 하던 회귀 수정)
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

            # rc=0 이지만 merge_commit 이 비어있는 경우 — 충돌 또는 백엔드 응답 형식 오류
            if not merge_commit:
                failure = _classify_done_failure(stdout, result.stderr or '')
                if failure['error_kind'] == 'merge_conflict':
                    # stdout 에 충돌 시그널이 확인된 경우
                    self._send_json_with_status(409, {
                        'ok': False,
                        'error_kind': 'merge_conflict',
                        'conflicts': failure['conflicts'],
                        'dirty_files': failure['dirty_files'],
                        'message': failure['message'],
                        'ticket': ticket,
                    })
                else:
                    # 충돌 시그널 없음 — 백엔드 응답 형식 오류
                    self._send_json_with_status(409, {
                        'ok': False,
                        'error_kind': 'other',
                        'conflicts': [],
                        'dirty_files': [],
                        'message': 'merge_commit 누락 — 백엔드 응답 형식 오류',
                        'ticket': ticket,
                    })
                return

            self._send_json({
                'ok': True,
                'ticket': ticket,
                'merge_commit': merge_commit,
                'merged_branch': merged_branch,
                'stdout': stdout.strip(),
            })
            return

        # 실패 — stdout 줄 단위 분석으로 error_kind 분류
        failure = _classify_done_failure(stdout, result.stderr or '')
        self._send_json_with_status(409, {
            'ok': False,
            'error_kind': failure['error_kind'],
            'conflicts': failure['conflicts'],
            'dirty_files': failure['dirty_files'],
            'message': failure['message'],
            'ticket': ticket,
        })

    def _handle_kanban_delete(self) -> None:
        r"""POST /api/kanban/delete — body {"ticket": "T-NNN"}.

        Open 카드 우클릭 [삭제] 의 단일 진입점 (T-418).

        1. ^T-\d+$ 형식 검증
        2. derived-from 가드 — 파생 티켓 중 Done 이외 상태면 409 + error_kind='derived_blocked'
        3. flow-kanban delete <ticket> 호출
        4. worktree_manager.remove_worktree 로 워크트리/브랜치 정리 (비활성 환경 silent)

        성공 응답 (200):
            {ok: true, ticket, stdout, worktree_removed: bool}

        실패 응답 (409):
            {ok: false, error_kind: 'derived_blocked'|'other', message, blocked_by: [...]}

        타임아웃(504) / 실행파일 없음(500) 은 기존 핸들러 패턴과 동일.
        """
        import subprocess

        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()

        # 입력 검증 — ^T-\d+$ 형식만 허용
        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        project_root = os.getcwd()
        kanban_base = os.path.join(project_root, '.claude-organic', 'tickets')

        # derived-from 가드 — 파생 티켓이 Done 이외 상태면 차단
        not_done = self._check_derived_blocked(ticket, kanban_base)
        if not_done:
            self._send_json_with_status(409, {
                'ok': False,
                'error_kind': 'derived_blocked',
                'blocked_by': not_done,
                'message': (
                    f'{ticket} 삭제 차단: 파생 티켓 {", ".join(not_done)}이 '
                    f'아직 완료되지 않았습니다. 파생 티켓 완료 후 삭제하세요.'
                ),
                'ticket': ticket,
            })
            return

        # flow-kanban delete 호출
        flow_kanban = os.path.join(
            project_root, '.claude-organic', 'bin', 'flow-kanban',
        )
        try:
            result = subprocess.run(
                [flow_kanban, 'delete', ticket],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-kanban delete timed out (30s)')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-kanban not found: {flow_kanban}')
            return

        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or '').strip()
            self._send_json_with_status(409, {
                'ok': False,
                'error_kind': 'other',
                'blocked_by': [],
                'message': stderr or 'flow-kanban delete failed',
                'ticket': ticket,
            })
            return

        # 워크트리 정리 (비활성 환경 silent)
        worktree_removed = False
        try:
            engine_dir = os.path.join(project_root, '.claude-organic', 'engine')
            if engine_dir not in sys.path:
                sys.path.insert(0, engine_dir)
            from flow import worktree_manager as _wm  # noqa: WPS433
            worktree_removed = _wm.remove_worktree(
                ticket, delete_branch=True, repo_path=project_root,
            )
        except ImportError:
            pass

        self._send_json({
            'ok': True,
            'ticket': ticket,
            'stdout': (result.stdout or '').strip(),
            'worktree_removed': worktree_removed,
        })

    def _handle_workflow_undo_done(self) -> None:
        """POST /api/workflow/undo-done — body {"ticket": "T-NNN", "force": bool}.

        Done 처리된 워크플로우를 Review 단계로 자동 롤백한다 (T-905 Phase 3).

        내부적으로 `flow-undo-done T-NNN [--force]` 를 호출하여
        develop reset/revert + feature 브랜치 + worktree 재생성 + 칸반 force 전이
        를 위임한다. stdout 을 파싱해 전략(reset/revert), 재생성된 worktree 정보,
        에러 메시지를 추출하여 프론트로 반환한다.

        성공 응답 (200):
            {ok: true, kind: 'reset_ok'|'revert_ok',
             ticket, strategy, merge_commit?, branch?, worktree_path?,
             stdout, message}

        실패 응답 (409):
            {ok: false, kind: 'error', error: <message>, ticket, stdout, stderr}

        타임아웃(504) / 실행파일 없음(500) 패턴은 _handle_kanban_done 답습.
        """
        import subprocess

        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        force = bool(data.get('force', False))

        # 입력 검증 — ^T-\d+$ 형식만 허용
        if not ticket or not re.match(r'^T-\d+$', ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        # Done 상태 사전 확인 — _read_kanban_tickets 재사용
        project_root = os.getcwd()
        kanban_data = _read_kanban_tickets(project_root)
        done_tickets = [
            t.get('number') or t.get('id')
            for t in kanban_data.get('done', [])
        ]
        if ticket not in done_tickets:
            self._send_error(
                400,
                f'{ticket} is not in Done column (undo-done targets Done tickets only)',
            )
            return

        # flow-undo-done 호출 — 워크트리 재생성 등을 고려해 timeout 180초
        flow_undo_done = os.path.join(
            project_root, '.claude-organic', 'bin', 'flow-undo-done',
        )
        cmd_args = [flow_undo_done, ticket]
        if force:
            cmd_args.append('--force')
        try:
            result = subprocess.run(
                cmd_args,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-undo-done timed out (180s)')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-undo-done not found: {flow_undo_done}')
            return

        stdout = result.stdout or ''
        stderr = result.stderr or ''

        # stdout + stderr 모두 라인 단위 파싱 — undo_done.py 는 _log 를 stdout 으로,
        # _err / _warn 을 stderr 로 출력한다. 전략/워크트리 메시지는 stdout, 에러는 stderr.
        all_lines = stdout.splitlines() + stderr.splitlines()

        strategy = ''
        worktree_path = ''
        branch = ''
        error_message = ''

        for line in all_lines:
            if not strategy and _UNDO_STRATEGY_RESET.search(line):
                strategy = 'reset'
            elif not strategy and _UNDO_STRATEGY_REVERT.search(line):
                strategy = 'revert'
            wt_match = _UNDO_WORKTREE_RE.search(line)
            if wt_match:
                worktree_path = wt_match.group(1).strip()
                branch = wt_match.group(2).strip()
            err_match = _UNDO_ERROR_RE.search(line)
            if err_match and not error_message:
                error_message = err_match.group(1).strip()

        if result.returncode == 0:
            kind = 'reset_ok' if strategy == 'reset' else 'revert_ok' if strategy == 'revert' else 'unknown_ok'
            self._send_json({
                'ok': True,
                'kind': kind,
                'ticket': ticket,
                'strategy': strategy,
                'branch': branch,
                'worktree_path': worktree_path,
                'message': f'{ticket} 롤백 완료 (전략: {strategy or "?"})',
                'stdout': stdout.strip(),
            })
            return

        # 실패 — error_message 우선, 없으면 stderr 끝에서 비어있지 않은 라인 사용
        if not error_message:
            for line in reversed(stderr.splitlines()):
                stripped = line.strip()
                if stripped:
                    error_message = stripped
                    break
        if not error_message:
            error_message = f'flow-undo-done exited with code {result.returncode}'

        self._send_json_with_status(409, {
            'ok': False,
            'kind': 'error',
            'ticket': ticket,
            'error': error_message,
            'message': error_message,
            'stdout': stdout.strip(),
            'stderr': stderr.strip(),
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
