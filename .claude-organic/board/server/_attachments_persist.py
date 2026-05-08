"""사용자 메시지에 결합된 첨부 티켓 메타를 jsonl sidecar 로 영속화한다.

T-429 의 정책에 따라 사용자 메시지 본문(jsonl content) 은 짧은 텍스트만
유지하고, 첨부 티켓 카드는 별도 sidecar 파일로 분리하여 보존한다.

파일 경로
---------
``~/.claude/projects/<project-slug>/<session_id>.attachments.jsonl``

- ``project-slug`` 결정은 ``handlers/terminal.py`` 와 ``claude_process.py`` 의
  기존 sidecar 패턴(``os.getcwd().replace('/', '-')``) 을 답습한다.

라인 형식
---------
``{"user_msg_ts": "<iso>", "attachments": [{number, command, title,
prompt, report, fetched_at}, ...]}``

- 빈 attachments 는 append 자체를 skip 하여 노이즈/회귀를 방지한다.
- 한 줄 = 한 user 메시지 첨부 묶음. 시간순 append-only.

graceful 폴백
-------------
- 파일 부재 시 ``load_map()`` 은 빈 dict 를 반환한다.
- 파싱 실패 라인은 무시한다.
- IO 오류는 logger 에 기록하고 파이프라인을 중단시키지 않는다.

session_id 미정 시
------------------
- ``session_id`` 가 빈 문자열인 경우 append/load 모두 no-op 처리한다.
  (워크플로우 외 시점이나 ``/terminal/start`` 직후 init 이벤트가 도착하지
  않은 짧은 구간에서 호출되는 보호용 분기)
"""

from __future__ import annotations

import json
import os

from ._common import logger


class AttachmentsSidecar:
    """``<session_id>.attachments.jsonl`` append/load 헬퍼.

    interrupted sidecar 패턴(``claude_process._record_user_interrupt_to_sidecar``)
    을 답습하여 동일한 ``~/.claude/projects/<slug>/<session_id>.<kind>.jsonl``
    경로 컨벤션을 유지한다.
    """

    SIDECAR_SUFFIX = '.attachments.jsonl'

    def __init__(self, session_id: str) -> None:
        self.session_id = (session_id or '').strip()
        self._path = self._resolve_path()

    # 경로 -------------------------------------------------------------

    def _resolve_path(self) -> str:
        """sidecar 파일 절대 경로를 산출한다.

        session_id 가 비어 있으면 빈 문자열을 반환하고, 호출부는 모든
        IO 를 no-op 으로 처리한다.
        """
        if not self.session_id:
            return ''
        project_root = os.getcwd()
        home_dir = os.path.expanduser('~')
        project_slug = project_root.replace('/', '-')
        return os.path.join(
            home_dir, '.claude', 'projects', project_slug,
            f'{self.session_id}{self.SIDECAR_SUFFIX}',
        )

    @property
    def path(self) -> str:
        """sidecar 파일 경로 (테스트/디버그용 노출)."""
        return self._path

    # write ------------------------------------------------------------

    def append(self, user_msg_ts: str, attachments: list[dict]) -> None:
        """user 메시지 1건의 첨부 묶음을 sidecar 에 append 한다.

        - ``attachments`` 가 빈 배열/None 이면 no-op (파일 자체를 만들지 않음).
        - ``user_msg_ts`` 는 사용자 메시지의 ISO timestamp 문자열.
        - 디렉터리 부재 시 자동 생성한다 (interrupted sidecar 와 동일한 디렉터리).
        - IO 오류는 로깅 후 swallow (호출부에 예외를 던지지 않음).
        """
        if not self._path:
            return
        if not attachments or not isinstance(attachments, list):
            return
        # number 키가 없는 dict 는 무시 (claude_process._compose_user_content
        # 의 검증과 동일한 정책).
        valid: list[dict] = []
        for att in attachments:
            if isinstance(att, dict) and 'number' in att:
                valid.append(att)
        if not valid:
            return

        record = {
            'user_msg_ts': user_msg_ts or '',
            'attachments': valid,
        }
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
        except OSError as exc:
            logger.error(
                'attachments sidecar: 디렉터리 생성 실패 (%s): %s',
                self._path, exc,
            )
            return
        try:
            with open(self._path, 'a', encoding='utf-8') as fp:
                fp.write(json.dumps(record, ensure_ascii=False) + '\n')
        except OSError as exc:
            logger.error(
                'attachments sidecar: 쓰기 실패 (%s): %s', self._path, exc,
            )

    # read -------------------------------------------------------------

    def load_map(self) -> dict[str, list[dict]]:
        """sidecar 라인을 모두 읽어 ``user_msg_ts → attachments`` 맵을 만든다.

        같은 ``user_msg_ts`` 가 여러 번 등장하면 마지막 라인이 우선한다
        (append-only 정책상 거의 발생하지 않는 케이스).

        파일 부재/파싱 실패 시 graceful 하게 빈 dict 를 반환한다.
        """
        if not self._path or not os.path.isfile(self._path):
            return {}

        result: dict[str, list[dict]] = {}
        try:
            with open(self._path, 'r', encoding='utf-8') as fp:
                for line in fp:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        rec = json.loads(stripped)
                    except (ValueError, json.JSONDecodeError):
                        continue
                    if not isinstance(rec, dict):
                        continue
                    ts = rec.get('user_msg_ts')
                    atts = rec.get('attachments')
                    if not isinstance(ts, str) or not ts:
                        continue
                    if not isinstance(atts, list):
                        continue
                    result[ts] = atts
        except OSError as exc:
            logger.error(
                'attachments sidecar: 읽기 실패 (%s): %s', self._path, exc,
            )
            return {}
        return result


__all__ = ['AttachmentsSidecar']
