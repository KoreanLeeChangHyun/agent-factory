"""Metrics handlers (W06): run/aggregate/regression."""

from __future__ import annotations

import logging

from board.server.support.common import api_endpoint
from engine.apps.board_api.handler_common import (
    _import_launch_metrics_cli,
    _import_metrics_cli,
)

logger = logging.getLogger(__name__)


class MetricsHandlerMixin:
    """Metrics handlers (W06): run/aggregate/regression."""

    @staticmethod
    def _parse_metrics_last(qs: dict, default: int) -> int:
        """internal helper — not exposed as endpoint.

        Safely parses the query string last parameter as an integer.
        Negative numbers/0/non-integers are corrected by default (graceful processing for incorrect input).
        """
        raw = (qs.get('last') or [None])[0]
        if raw is None:
            return default
        try:
            v = int(raw)
        except (TypeError, ValueError):
            return default
        return v if v > 0 else default

    @api_endpoint("MET", "run")
    def _handle_metrics_run(self, registry_key: str) -> None:
        """GET /api/metrics/run/<registryKey> — Single workflow aggregate result response.

        method: GET
        url: /api/metrics/run/<registry_key>
        domain: MET
        handler: MetricsHandlerMixin._handle_metrics_run
        request: path {registry_key: str (YYYYMMDD-HHMMSS)}
        response_ok: {registry_key, summary, events: [...]}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 500
        auth: none (local-only)
        side_effects: read .agent-factory/runs/<key>/metrics.jsonl
        sse_events: none
        """
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

    @api_endpoint("MET", "aggregate")
    def _handle_metrics_aggregate(self, last: int) -> None:
        """GET /api/metrics/aggregate?last=N — Last N run summary list responses.

        method: GET
        url: /api/metrics/aggregate
        domain: MET
        handler: MetricsHandlerMixin._handle_metrics_aggregate
        request: query {last: int (default 20)}
        response_ok: {last: int, count: int, runs: [{...}]}
        response_error: {ok: false, error: str}
        status_codes: 200, 500
        auth: none (local-only)
        side_effects: scan .agent-factory/runs/ recent N dirs
        sse_events: none
        """
        try:
            cli = _import_metrics_cli()
            data = cli.aggregate_recent(last)
        except Exception as exc:  # noqa: BLE001
            logger.exception('metrics.aggregate failed: %s', exc)
            self._send_error(500, f'aggregate_recent failed: {exc}')
            return
        # To make it easier for the front desk to handle, wrap the list with a dict once again (including the last meta).
        self._send_json({
            'last': last,
            'count': len(data),
            'runs': data,
        })

    @api_endpoint("MET", "regression")
    def _handle_metrics_regression(self, last: int) -> None:
        """GET /api/metrics/regression?last=N — Regression pattern frequency + example response.

        method: GET
        url: /api/metrics/regression
        domain: MET
        handler: MetricsHandlerMixin._handle_metrics_regression
        request: query {last: int (default 20)}
        response_ok: {last: int, patterns: {<pattern>: count}, examples: [...]}
        response_error: {ok: false, error: str}
        status_codes: 200, 500
        auth: none (local-only)
        side_effects: scan metrics.jsonl for regression.pattern events
        sse_events: none
        """
        try:
            cli = _import_metrics_cli()
            data = cli.regression_counts(last)
        except Exception as exc:  # noqa: BLE001
            logger.exception('metrics.regression failed: %s', exc)
            self._send_error(500, f'regression_counts failed: {exc}')
            return
        # We add last to the result so the front knows the calling context.
        data = dict(data)
        data['last'] = last
        self._send_json(data)

    @api_endpoint("MET", "launch_latency")
    def _handle_metrics_launch_latency(self, last: int = 10) -> None:
        """GET /api/metrics/launch_latency?last=N — launch spawn_duration_ms distributed response.

        Parse LAUNCH_START/LAUNCH_OK events in workflow.log and spawn_duration_ms
        Returns distribution statistics (p50/p95/p99/min/max/mean), list of slow spawns, and per-run summary.

        When T-475 is not distributed, it responds gracefully with 0 LAUNCH_* events.
        (distribution.count=0, p50/p95/p99/min/max/mean=None)

        method: GET
        url: /api/metrics/launch_latency
        domain: MET
        handler: MetricsHandlerMixin._handle_metrics_launch_latency
        request: query {last: int (default 10)}
        response_ok: {ok: true, data: {last, runs_scanned, events_total, distribution, slow_spawns, per_run}}
        response_error: {ok: false, error: str}
        status_codes: 200, 500
        auth: none (local-only)
        side_effects: scan workflow.log files for LAUNCH_* events
        sse_events: none
        """
        import subprocess
        from pathlib import Path

        try:
            # runs_dir is determined based on git rev-parse --show-toplevel.
            # In case of failure, it falls back based on the current board server cwd.
            try:
                root = subprocess.check_output(
                    ['git', 'rev-parse', '--show-toplevel'],
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
                runs_dir = Path(root) / '.agent-factory' / 'runs'
            except Exception:  # noqa: BLE001
                runs_dir = Path.cwd() / '.agent-factory' / 'runs'

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
