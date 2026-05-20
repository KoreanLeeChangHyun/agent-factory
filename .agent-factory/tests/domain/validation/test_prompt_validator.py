"""Core prompt validator coverage."""

from __future__ import annotations

from engine.core.validation import prompt_validator


def test_prompt_validator_scores_complete_prompt() -> None:
    result = prompt_validator.validate(
        """
        <prompt>
          <goal>Build the requested workflow integration.</goal>
          <target>Update the Agent Factory implementation.</target>
          <constraints>Keep changes scoped and covered by tests.</constraints>
          <criteria>All relevant tests pass after the change.</criteria>
        </prompt>
        """
    )

    assert result["quality_score"] == 1.0
    assert result["missing_tags"] == []
    assert result["empty_tags"] == []


def test_extract_active_prompt_reads_flat_prompt() -> None:
    xml = "<ticket><prompt><goal>Done</goal></prompt></ticket>"

    assert prompt_validator.extract_active_prompt(xml) == "<goal>Done</goal>"
