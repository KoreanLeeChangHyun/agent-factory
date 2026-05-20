"""Slack adapter placement coverage."""

from __future__ import annotations


def test_slack_adapter_modules_import_from_adapter_boundary() -> None:
    from engine.adapters.slack import slack_ask, slack_common, slack_notify

    assert slack_ask.extract_json_field is slack_common.extract_json_field
    assert slack_notify.build_json_payload is slack_common.build_json_payload
