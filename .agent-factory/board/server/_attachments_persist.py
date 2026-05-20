"""jsonl sidecar

jsonl content is only short text according to T-429 policy
Keep and the attached ticket card will be preserved by separate sidecar files.

File path
---------
``~/.claude/projects/<project-slug>/<session_id>.attachments.jsonl``

- ``project-slug``` ``handlers/terminal.py` and ``claude process.py``
  the existing sidecar pattern (`os.getcwd().replace('/', '-')`).

Line Type
---------
``{"user_msg_ts": "<iso>", "attachments": [{number, command, title,
prompt, report, fetched_at}, ...]}``

- blank attachments will skip the append itself to prevent noise/turns.
- One line = one user message attached string. timeline append-only.

Graceful Folly
-------------
- When file deletion, `load map()` returns empty dict.
- The parsing failure line ignores.
- IO error is recorded on logger and does not interrupt the pipeline.

session id
------------------
- If `session id` is empty string, append/load will handle no-op.
  (Init event after workflow or terminal/start`)
  Unlike short sections, the protection branch is called.
"""

from __future__ import annotations

import json
import os

from ._common import logger


class AttachmentsSidecar:
    """``<session id>.attachments.jsonl` append/load helper.

    interrupt to sidecar`
    <% if (imgObj.width >= imgObj.height) { %> <kind>.jsonl`
    Toggle navigation
    """

    SIDECAR_SUFFIX = '.attachments.jsonl'

    def __init__(self, session_id: str) -> None:
        self.session_id = (session_id or '').strip()
        self._path = self._resolve_path()

    # Path ------------------------------------------------

    def _resolve_path(self) -> str:
        """output the sidecar file absolute path.

        if session id is empty, return the empty string, and all call calls are empty
        IO to no-op.
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
        """sidecar file path (test/debug exposure)."""
        return self._path

    # write ------------------------------------------------------------

    def append(self, user_msg_ts: str, attachments: list[dict]) -> None:
        """user message is append to sidecar

        - `attachments` is empty array/None, no-op (not creating file itself).
        - ``user msg ts` is the ISO timestamp string of user messages.
        - Automatically generates a directory (such as interrupted sidecar).
        - IO error swallow after logging (not throwing exceptions to export).
        """
        if not self._path:
            return
        if not attachments or not isinstance(attachments, list):
            return
        # number Keyless dict ignore (claude process. compose user content)
        # The same policy as validation.
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
                'attachments sidecar: directory generate failed (%s): %s',
                self._path, exc,
            )
            return
        try:
            with open(self._path, 'a', encoding='utf-8') as fp:
                fp.write(json.dumps(record, ensure_ascii=False) + '\n')
        except OSError as exc:
            logger.error(
                'Attachs sidecar: failed to write (%s): %s', self._path, exc,
            )

    # read -------------------------------------------------------------

    def load_map(self) -> dict[str, list[dict]]:
        """[user msg ts → attachments]

        If the same `user msg ts` appeared multiple times, the last line is priority
        (append-only case that the policy does not occur almost).

        return graceful to empty dict when file corruption/pasing failure.
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
                'attachments sidecar: read failed (%s): %s', self._path, exc,
            )
            return {}
        return result


__all__ = ['AttachmentsSidecar']
