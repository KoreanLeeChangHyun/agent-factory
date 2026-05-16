"""V2WorkflowSession + V2WorkflowSessionRegistry — v2 driver subprocess 전용 세션 모델.

v1 WorkflowSession 과 분리된 별도 데이터 모델. ClaudeProcess 의존 0건.
SSE fan-out 은 V2WorkflowSSEChannel 이 담당 (TerminalSSEChannel 과 분리).

driver subprocess 가 발급한 session_id 로 board 측이 명시 등록한다
(POST /api/v2/sessions). lazy create 인프라는 폐기 — 모든 진입은 명시 POST.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._common import logger

if TYPE_CHECKING:
    from .v2_sse_channel import V2WorkflowSSEChannel


@dataclass
class V2WorkflowSession:
    """v2 driver subprocess 가 발급한 워크플로우 세션 메타.

    v1 WorkflowSession 과 다른 점:
    - ClaudeProcess 필드 제거 (driver subprocess 가 외부 process 로 실행)
    - status / current_step / current_phase / cycle_start_ts / step_ts 자체 보유
      (frontend 카운터 + 탭 가시성용)
    - artifacts dict 자체 보유 (생성된 산출물 경로 + size)
    - channel 은 V2WorkflowSSEChannel 인스턴스 (TerminalSSEChannel 과 분리)

    Attributes:
        session_id: driver 발급 세션 ID (wf-T-NNN-<uuid>)
        ticket_id: 칸반 티켓 ID (T-NNN)
        command: implement / research / review
        work_dir: runs/<registryKey>/ 절대 경로
        worktree_path: implement 전용 worktree 절대 경로 (없으면 빈 문자열)
        status: idle | running | completed | failed
        current_step: NONE | INIT | PLAN | WORK | VALIDATE | REPORT | DONE | FAILED
        current_phase: WORK 내부 sub-phase (P1, P2, ... 없으면 빈 문자열)
        cycle_start_ts: 사이클 시작 epoch (frontend 사이클 누적 카운터)
        step_ts: 현재 step 진입 epoch (frontend step elapsed)
        artifacts: 산출물 경로 → 메타 dict (size, mtime)
        channel: V2WorkflowSSEChannel 인스턴스
        created_at: ISO 시각
    """

    session_id: str
    ticket_id: str
    command: str
    work_dir: str
    channel: 'V2WorkflowSSEChannel' = field(repr=False)
    worktree_path: str = ''
    status: str = 'idle'
    current_step: str = 'NONE'
    current_phase: str = ''
    cycle_start_ts: float = field(default_factory=time.time)
    step_ts: float = field(default_factory=time.time)
    artifacts: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%S'))


class V2WorkflowSessionRegistry:
    """v2 driver 세션 레지스트리.

    thread-safe 하게 세션을 생성·조회·삭제한다.
    v1 WorkflowSessionRegistry 와 별도 (workflow_registry / v2_workflow_registry 이원화).

    persist 디렉터리는 `.claude-organic/.workflow-sessions-v2/` (v1 과 분리).
    """

    def __init__(self, persist_dir: str | None = None) -> None:
        """초기화한다.

        Args:
            persist_dir: 세션 jsonl 을 저장할 디렉터리. None 이면 persist 비활성.
        """
        self._sessions: dict[str, V2WorkflowSession] = {}
        self._lock: threading.Lock = threading.Lock()
        self._persist_dir: str | None = persist_dir
        if self._persist_dir is not None:
            try:
                os.makedirs(self._persist_dir, exist_ok=True)
            except OSError:
                self._persist_dir = None

    def _session_file(self, session_id: str) -> str | None:
        """세션 NDJSON 파일 경로를 반환한다."""
        if self._persist_dir is None:
            return None
        return os.path.join(self._persist_dir, f'{session_id}.jsonl')

    def create(
        self,
        session_id: str,
        ticket_id: str,
        command: str,
        work_dir: str,
        worktree_path: str = '',
    ) -> V2WorkflowSession:
        """driver 가 발급한 session_id 로 세션을 명시 등록한다.

        동일 session_id 로 재호출 시 기존 세션 반환 (idempotent).
        v1 create_external 의 lazy create 와 달리 명시 POST /api/v2/sessions 진입점.

        Args:
            session_id: driver 발급 세션 ID (wf-T-NNN-<uuid>)
            ticket_id: T-NNN
            command: implement / research / review
            work_dir: runs/<registryKey>/ 절대 경로
            worktree_path: implement 전용 worktree 절대 경로 (research/review 시 빈 문자열)

        Returns:
            등록된 V2WorkflowSession 인스턴스
        """
        with self._lock:
            existing = self._sessions.get(session_id)
            if existing is not None:
                return existing

        persist_path = self._session_file(session_id)
        # circular import 회피 — 런타임 import
        from .v2_sse_channel import V2WorkflowSSEChannel
        channel = V2WorkflowSSEChannel(session_id=session_id, persist_path=persist_path)

        session = V2WorkflowSession(
            session_id=session_id,
            ticket_id=ticket_id,
            command=command,
            work_dir=work_dir,
            worktree_path=worktree_path,
            channel=channel,
        )

        if persist_path is not None:
            try:
                meta = {
                    '_meta': {
                        'session_id': session_id,
                        'ticket_id': ticket_id,
                        'command': command,
                        'work_dir': work_dir,
                        'worktree_path': worktree_path,
                        'created_at': session.created_at,
                        'engine_version': 'v2',
                    }
                }
                with open(persist_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            except OSError as exc:
                logger.error(
                    "v2_workflow_session[%s]: meta persist 실패 (%s): %s",
                    session_id, persist_path, exc,
                )

        with self._lock:
            self._sessions[session_id] = session

        return session

    def get(self, session_id: str) -> V2WorkflowSession | None:
        """session_id 로 세션을 조회한다."""
        with self._lock:
            return self._sessions.get(session_id)

    def get_by_ticket(self, ticket_id: str) -> V2WorkflowSession | None:
        """티켓 ID 로 세션을 조회한다 (동일 티켓 다수 시 첫 매칭)."""
        with self._lock:
            for session in self._sessions.values():
                if session.ticket_id == ticket_id:
                    return session
            return None

    def remove(self, session_id: str) -> bool:
        """세션을 레지스트리에서 제거한다 (디스크 보존)."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def purge(self, session_id: str) -> bool:
        """세션을 레지스트리 + 디스크에서 완전히 제거한다."""
        removed = self.remove(session_id)
        if removed and self._persist_dir is not None:
            fpath = self._session_file(session_id)
            if fpath and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except OSError as exc:
                    logger.error(
                        "v2_workflow_session[%s]: 파일 삭제 실패 (%s): %s",
                        session_id, fpath, exc,
                    )
        return removed

    def list_all(self) -> list[dict]:
        """전체 세션 목록을 dict 리스트로 반환한다.

        Returns:
            세션 메타 dict 리스트. 키: session_id, ticket_id, command, work_dir,
            worktree_path, status, current_step, current_phase, cycle_start_ts,
            step_ts, created_at
        """
        with self._lock:
            return [
                {
                    'session_id': s.session_id,
                    'ticket_id': s.ticket_id,
                    'command': s.command,
                    'work_dir': s.work_dir,
                    'worktree_path': s.worktree_path,
                    'status': s.status,
                    'current_step': s.current_step,
                    'current_phase': s.current_phase,
                    'cycle_start_ts': s.cycle_start_ts,
                    'step_ts': s.step_ts,
                    'created_at': s.created_at,
                }
                for s in self._sessions.values()
            ]

    def update_step(
        self,
        session_id: str,
        step: str,
        phase: str = '',
    ) -> V2WorkflowSession | None:
        """current_step + current_phase + step_ts 를 thread-safe 갱신한다.

        status 자동 매핑:
        - DONE → completed
        - FAILED → failed
        - 그 외 → running (idle 진입은 명시 set_status 로만)
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.current_step = step
            session.current_phase = phase
            session.step_ts = time.time()
            if step == 'DONE':
                session.status = 'completed'
            elif step == 'FAILED':
                session.status = 'failed'
            elif session.status == 'idle':
                session.status = 'running'
            return session

    def set_status(self, session_id: str, status: str) -> V2WorkflowSession | None:
        """status 를 명시 set 한다 (예: 외부 종결 신호)."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.status = status
            return session

    def add_artifact(
        self,
        session_id: str,
        path: str,
        size: int = 0,
    ) -> V2WorkflowSession | None:
        """산출물 메타를 등록한다 (path → {size, mtime})."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.artifacts[path] = {
                'size': size,
                'mtime': time.time(),
            }
            return session

    def load_from_disk(self) -> int:
        """persist 디렉터리에서 세션 메타를 로드하여 레지스트리를 복원한다.

        v1 load_from_disk 와 같은 패턴 — 첫 줄 _meta 만 읽어 세션 객체 재생성.
        이벤트 데이터는 메모리에 복원 안 함 (재접속 시 클라이언트가 NDJSON 파일 직접 read).
        status='completed' 또는 'failed' 로 복원 (server 재기동 시 진행 중인 세션은 의미 없음).

        Returns:
            로드된 세션 개수
        """
        if self._persist_dir is None or not os.path.isdir(self._persist_dir):
            return 0

        from .v2_sse_channel import V2WorkflowSSEChannel
        loaded = 0
        for fname in sorted(os.listdir(self._persist_dir)):
            if not fname.endswith('.jsonl'):
                continue
            fpath = os.path.join(self._persist_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    first_line = f.readline()
            except OSError:
                continue
            if not first_line:
                continue
            try:
                first = json.loads(first_line)
                meta = first.get('_meta')
                if not meta or not meta.get('session_id'):
                    continue
            except (json.JSONDecodeError, ValueError):
                continue

            session_id = meta['session_id']
            channel = V2WorkflowSSEChannel(session_id=session_id, persist_path=fpath)
            session = V2WorkflowSession(
                session_id=session_id,
                ticket_id=meta.get('ticket_id', ''),
                command=meta.get('command', ''),
                work_dir=meta.get('work_dir', ''),
                worktree_path=meta.get('worktree_path', ''),
                channel=channel,
                status='completed',
                created_at=meta.get('created_at', time.strftime('%Y-%m-%dT%H:%M:%S')),
            )

            with self._lock:
                self._sessions[session_id] = session
            loaded += 1

        return loaded
