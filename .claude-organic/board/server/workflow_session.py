"""WorkflowSession + WorkflowSessionRegistry — workflow session lifecycle."""

from __future__ import annotations

import datetime
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field

from ._common import logger
from .claude_process import ClaudeProcess
from .terminal_channel import TerminalSSEChannel


@dataclass
class WorkflowSession:
    """워크플로우 세션 하나를 나타내는 데이터 클래스.

    각 워크플로우 티켓 실행은 독립된 ClaudeProcess와 TerminalSSEChannel을
    가지며, session_id로 식별된다.

    Attributes:
        session_id: 세션 고유 ID (형식: wf-T-NNN-timestamp)
        ticket_id: 칸반 티켓 ID (예: T-238)
        command: 실행 명령어 (implement, review, research 등)
        work_dir: 작업 디렉터리 절대 경로
        process: Claude CLI 프로세스 관리자 인스턴스
        channel: 터미널 SSE 브로드캐스트 채널 인스턴스
        created_at: 세션 생성 시각 (ISO 형식)
        current_step: 현재 진행 중인 워크플로우 단계 (예: PLAN, WORK, REPORT)
        last_artifact: 최근 생성된 산출물 경로 (예: work/W01-design.md)
    """

    session_id: str
    ticket_id: str
    command: str
    work_dir: str
    process: ClaudeProcess = field(repr=False)
    channel: TerminalSSEChannel = field(repr=False)
    created_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%S'))
    current_step: str = ''
    last_artifact: str = ''


class WorkflowSessionRegistry:
    """다중 워크플로우 세션 레지스트리.

    thread-safe하게 워크플로우 세션을 생성·조회·삭제한다.
    각 세션은 독립된 ClaudeProcess + TerminalSSEChannel 쌍을 보유한다.

    Attributes:
        _sessions: session_id -> WorkflowSession 매핑
        _lock: thread-safe 접근용 Lock
    """

    def __init__(self, persist_dir: str | None = None) -> None:
        """초기화한다.

        Args:
            persist_dir: 세션을 저장할 디렉터리. None이면 persist 비활성.
        """
        self._sessions: dict[str, WorkflowSession] = {}
        self._lock: threading.Lock = threading.Lock()
        self._persist_dir: str | None = persist_dir
        if self._persist_dir is not None:
            try:
                os.makedirs(self._persist_dir, exist_ok=True)
            except OSError:
                self._persist_dir = None

    def _session_file(self, session_id: str) -> str | None:
        """세션 이벤트 파일 경로를 반환한다."""
        if self._persist_dir is None:
            return None
        return os.path.join(self._persist_dir, f'{session_id}.jsonl')

    def create(
        self,
        ticket_id: str,
        command: str,
        work_dir: str,
    ) -> WorkflowSession:
        """새 워크플로우 세션을 생성한다.

        독립된 TerminalSSEChannel과 ClaudeProcess 인스턴스를 할당하고,
        session_id를 생성하여 레지스트리에 등록한다.

        Args:
            ticket_id: 칸반 티켓 ID (예: T-238)
            command: 실행 명령어 (implement, review, research 등)
            work_dir: 작업 디렉터리 절대 경로

        Returns:
            생성된 WorkflowSession 인스턴스
        """
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        session_id = f'wf-{ticket_id}-{timestamp}'

        persist_path = self._session_file(session_id)
        channel = TerminalSSEChannel(persist_path=persist_path)
        process = ClaudeProcess(channel)

        session = WorkflowSession(
            session_id=session_id,
            ticket_id=ticket_id,
            command=command,
            work_dir=work_dir,
            process=process,
            channel=channel,
        )

        # stdout 기반 단계 감지 시 session.current_step 자동 갱신
        def _on_step(step_name: str, _payload: dict) -> None:
            session.current_step = step_name
        channel.on_step = _on_step

        # 메타데이터를 파일 첫 줄에 기록
        if persist_path is not None:
            try:
                meta = {
                    '_meta': {
                        'session_id': session_id,
                        'ticket_id': ticket_id,
                        'command': command,
                        'work_dir': work_dir,
                        'created_at': session.created_at,
                    }
                }
                with open(persist_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            except OSError as exc:
                logger.error("workflow_session[%s]: 메타데이터 persist 쓰기 실패 (%s): %s", session_id, persist_path, exc)

        with self._lock:
            self._sessions[session_id] = session

        return session

    def load_from_disk(self) -> int:
        """persist 디렉터리에서 세션을 로드하여 레지스트리를 복원한다.

        각 *.jsonl 파일을 읽어:
          - 첫 줄의 _meta로 WorkflowSession 객체를 재생성
          - 나머지 줄의 이벤트들을 채널 히스토리에 복원
          - process는 새 ClaudeProcess (status='stopped')로 생성

        Returns:
            로드된 세션 개수
        """
        if self._persist_dir is None or not os.path.isdir(self._persist_dir):
            return 0

        loaded = 0
        for fname in sorted(os.listdir(self._persist_dir)):
            if not fname.endswith('.jsonl'):
                continue
            fpath = os.path.join(self._persist_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except OSError:
                continue
            if not lines:
                continue
            try:
                first = json.loads(lines[0])
                meta = first.get('_meta')
                if not meta or not meta.get('session_id'):
                    continue
            except (json.JSONDecodeError, ValueError):
                continue

            channel = TerminalSSEChannel(persist_path=fpath)
            process = ClaudeProcess(channel)
            session = WorkflowSession(
                session_id=meta['session_id'],
                ticket_id=meta.get('ticket_id', ''),
                command=meta.get('command', ''),
                work_dir=meta.get('work_dir', ''),
                process=process,
                channel=channel,
                created_at=meta.get('created_at', time.strftime('%Y-%m-%dT%H:%M:%S')),
            )

            # 이벤트 복원 (파일 쓰기 없이 히스토리만)
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    channel.replay_from_history(data)
                except (json.JSONDecodeError, ValueError):
                    continue

            with self._lock:
                self._sessions[session.session_id] = session
            loaded += 1

        return loaded

    def purge(self, session_id: str) -> bool:
        """세션을 레지스트리와 디스크에서 완전히 제거한다."""
        removed = self.remove(session_id)
        if removed and self._persist_dir is not None:
            fpath = self._session_file(session_id)
            if fpath and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except OSError as exc:
                    logger.error("workflow_session[%s]: 세션 파일 삭제 실패 (%s): %s", session_id, fpath, exc)
        return removed

    def load_archived(self, session_id: str) -> 'WorkflowSession | None':
        """디스크 아카이브에서 완료 세션을 on-demand로 복원한다.

        registry에 없지만 .jsonl 파일이 남아있는 경우 읽기 전용으로 복원한다.
        process는 status='stopped'로 설정되며 신규 입력은 거부된다. 본 메서드는
        registry에 세션을 삽입하지 않고, 호출자가 일회성으로 사용한 뒤 참조를 놓는다.
        """
        if self._persist_dir is None:
            return None
        fpath = self._session_file(session_id)
        if fpath is None or not os.path.exists(fpath):
            return None
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except OSError:
            return None
        if not lines:
            return None
        try:
            first = json.loads(lines[0])
            meta = first.get('_meta') or {}
        except (json.JSONDecodeError, ValueError):
            return None
        if not meta.get('session_id'):
            return None

        channel = TerminalSSEChannel(persist_path=None)
        process = ClaudeProcess(channel)
        session = WorkflowSession(
            session_id=meta['session_id'],
            ticket_id=meta.get('ticket_id', ''),
            command=meta.get('command', ''),
            work_dir=meta.get('work_dir', ''),
            process=process,
            channel=channel,
            created_at=meta.get('created_at', time.strftime('%Y-%m-%dT%H:%M:%S')),
        )
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                channel.replay_from_history(data)
            except (json.JSONDecodeError, ValueError):
                continue
        return session

    def get(self, session_id: str) -> WorkflowSession | None:
        """session_id로 세션을 조회한다.

        Args:
            session_id: 조회할 세션 ID

        Returns:
            WorkflowSession 인스턴스. 존재하지 않으면 None.
        """
        with self._lock:
            return self._sessions.get(session_id)

    def remove(self, session_id: str) -> bool:
        """세션을 레지스트리에서 제거한다.

        프로세스 종료는 호출자가 별도로 처리해야 한다.

        Args:
            session_id: 제거할 세션 ID

        Returns:
            제거 성공 시 True, 세션이 존재하지 않으면 False.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def list_all(self) -> list[dict]:
        """전체 세션 목록을 dict 리스트로 반환한다.

        Returns:
            세션 메타데이터 dict 리스트. 각 dict 키:
            session_id, ticket_id, command, work_dir, status, created_at
        """
        with self._lock:
            return [
                {
                    'session_id': s.session_id,
                    'ticket_id': s.ticket_id,
                    'command': s.command,
                    'work_dir': s.work_dir,
                    'status': s.process.status,
                    'created_at': s.created_at,
                }
                for s in self._sessions.values()
            ]

    def get_by_ticket(self, ticket_id: str) -> WorkflowSession | None:
        """티켓 ID로 세션을 조회한다.

        동일 티켓에 여러 세션이 있을 경우 첫 번째 매칭을 반환한다.

        Args:
            ticket_id: 조회할 티켓 ID (예: T-238)

        Returns:
            WorkflowSession 인스턴스. 존재하지 않으면 None.
        """
        with self._lock:
            for session in self._sessions.values():
                if session.ticket_id == ticket_id:
                    return session
            return None


# 모듈 레벨 워크플로우 세션 레지스트리 싱글톤
