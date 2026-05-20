"""Ouroboros refinement model for WorkRequest authoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class OuroborosPhase(str, Enum):
    DRAFT = "DRAFT"
    CLARIFY = "CLARIFY"
    CRITIQUE = "CRITIQUE"
    REWRITE = "REWRITE"
    ACCEPT = "ACCEPT"


_NEXT_PHASE: dict[OuroborosPhase, tuple[OuroborosPhase, ...]] = {
    OuroborosPhase.DRAFT: (OuroborosPhase.CLARIFY,),
    OuroborosPhase.CLARIFY: (OuroborosPhase.CRITIQUE,),
    OuroborosPhase.CRITIQUE: (OuroborosPhase.REWRITE, OuroborosPhase.ACCEPT),
    OuroborosPhase.REWRITE: (OuroborosPhase.CLARIFY, OuroborosPhase.ACCEPT),
    OuroborosPhase.ACCEPT: (),
}


@dataclass(frozen=True)
class OuroborosEntry:
    phase: OuroborosPhase
    text: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("ouroboros entry text cannot be empty")
        object.__setattr__(self, "text", self.text.strip())


@dataclass
class OuroborosState:
    """Tracks legal refinement transitions before WorkRequest execution."""

    current: OuroborosPhase = OuroborosPhase.DRAFT
    history: list[OuroborosEntry] = field(default_factory=list)

    def advance(self, phase: OuroborosPhase, text: str) -> None:
        allowed = _NEXT_PHASE[self.current]
        if phase not in allowed:
            allowed_s = ", ".join(p.value for p in allowed) or "(terminal)"
            raise ValueError(
                f"illegal Ouroboros transition {self.current.value} -> {phase.value}; "
                f"allowed: {allowed_s}"
            )
        self.history.append(OuroborosEntry(phase=phase, text=text))
        self.current = phase

    @property
    def accepted(self) -> bool:
        return self.current is OuroborosPhase.ACCEPT

