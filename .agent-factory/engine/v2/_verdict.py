"""Compatibility exports for V2 validation verdict payloads."""

from __future__ import annotations

from engine.core.validation.verdict import (
    GATE_REGISTRY,
    SCHEMA_VERSION,
    Gate,
    build_final_verdict,
    compute_preliminary_verdict as _compute_preliminary_verdict,
    gate_registry_payload,
    get_blocking_rule_ids,
    read_verify_verdict,
    result_payload as _result_payload,
    save_final_verdict,
    write_report_manifest,
    write_verify_verdict,
)

__all__ = [
    "GATE_REGISTRY",
    "SCHEMA_VERSION",
    "Gate",
    "_compute_preliminary_verdict",
    "_result_payload",
    "build_final_verdict",
    "gate_registry_payload",
    "get_blocking_rule_ids",
    "read_verify_verdict",
    "save_final_verdict",
    "write_report_manifest",
    "write_verify_verdict",
]
