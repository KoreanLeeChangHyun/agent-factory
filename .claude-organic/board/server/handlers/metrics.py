"""Metrics handlers (W06): run/aggregate/regression."""

from __future__ import annotations

import logging

from ._handler_common import _import_metrics_cli, _import_launch_metrics_cli

logger = logging.getLogger(__name__)


class MetricsHandlerMixin:
    """Metrics handlers (W06): run/aggregate/regression."""

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

    def _handle_metrics_run(self, registry_key: str) -> None:
        """GET /api/metrics/run/<registryKey> — 단일 워크플로우 집계 결과 응답."""
        if not registry_key or len(registry_key) != 15 or registry_key[8] != '-':
            self._send_error(400, 'Invalid registryKey (expected YYYYMMDD-HHMMSS)')
            return
        try:
            cli = _import_metrics_cli()
            data = cli.aggregate_run(registry_key)
        except Exception as exc:  # noqa: BLE001
            logger.exception('metrics.run failed: %s', exc)
            self._send_error(500, f'aggregate_run failed: {exc}')
            return
        self._send_json(data)

    def _handle_metrics_aggregate(self, last: int) -> None:
        """GET /api/metrics/aggregate?last=N — 최근 N개 run summary list 응답."""
        try:
            cli = _import_metrics_cli()
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
            cli = _import_metrics_cli()
            data = cli.regression_counts(last)
        except Exception as exc:  # noqa: BLE001
            logger.exception('metrics.regression failed: %s', exc)
            self._send_error(500, f'regression_counts failed: {exc}')
            return
        # last 를 결과에 합쳐서 프론트가 호출 컨텍스트를 알 수 있게 한다.
        data = dict(data)
        data['last'] = last
        self._send_json(data)

    def _handle_metrics_launch_latency(self, last: int = 10) -> None:
        """GET /api/metrics/launch_latency?last=N — launch spawn_duration_ms 분포 응답.

        workflow.log 의 LAUNCH_START/LAUNCH_OK 이벤트를 파싱해 spawn_duration_ms
        분포 통계(p50/p95/p99/min/max/mean)와 느린 spawn 목록, per-run 요약을 반환한다.

        T-475 미배포 시에는 LAUNCH_* 이벤트 0건으로 graceful 응답한다.
        (distribution.count=0, p50/p95/p99/min/max/mean=None)
        """
        import subprocess
        from pathlib import Path

        try:
            # runs_dir 은 git rev-parse --show-toplevel 기준으로 결정한다.
            # 실패 시 __file__ 기반 parents[3] 로 fallback 한다.
            try:
                root = subprocess.check_output(
                    ['git', 'rev-parse', '--show-toplevel'],
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
                runs_dir = Path(root) / '.claude-organic' / 'runs'
            except Exception:  # noqa: BLE001
                runs_dir = Path(__file__).resolve().parents[3] / '.claude-organic' / 'runs'

            lm_cli = _import_launch_metrics_cli()
            result = lm_cli.aggregate_recent_launch(last=last, runs_dir=runs_dir)
        except Exception as exc:  # noqa: BLE001
            logger.exception('metrics.launch_latency failed: %s', exc)
            self._send_error(500, f'aggregate_recent_launch failed: {exc}')
            return

        self._send_json({
            'ok': True,
            'data': {
                'last': last,
                'runs_scanned': result.get('runs_scanned', 0),
                'events_total': result.get('events_total', 0),
                'distribution': result.get('distribution', {
                    'count': 0,
                    'p50': None,
                    'p95': None,
                    'p99': None,
                    'min': None,
                    'max': None,
                    'mean': None,
                }),
                'slow_spawns': result.get('slow_spawns', []),
                'per_run': result.get('per_run', []),
            },
        })
