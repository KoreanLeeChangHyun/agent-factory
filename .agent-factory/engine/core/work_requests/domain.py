"""Pure WorkRequest domain model.

`Ticket` remains a storage/UI compatibility term. New core code should model
the executable request as a WorkRequest and keep the stable external `T-123`
identifier through WorkRequestRef.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


_WORK_REQUEST_REF_RE = re.compile(r"^T-\d{3,}$")


class WorkRequestStatus(str, Enum):
    """Board-facing request lifecycle states."""

    TODO = "To Do"
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    REVIEW = "Review"
    DONE = "Done"


@dataclass(frozen=True)
class WorkRequestRef:
    """Stable external reference for a work request, for example `T-123`."""

    value: str

    def __post_init__(self) -> None:
        if not _WORK_REQUEST_REF_RE.match(self.value):
            raise ValueError(f"invalid WorkRequestRef: {self.value!r}")

    @classmethod
    def parse(cls, raw: str) -> "WorkRequestRef":
        value = raw.strip().upper()
        if re.fullmatch(r"\d+", value):
            value = f"T-{int(value):03d}"
        elif re.fullmatch(r"T-\d+", value):
            prefix, number = value.split("-", 1)
            value = f"{prefix}-{int(number):03d}"
        return cls(value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class AcceptanceCriteria:
    """Observable condition that must be true for completion."""

    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("acceptance criteria cannot be empty")
        object.__setattr__(self, "text", self.text.strip())


@dataclass(frozen=True)
class RiskNote:
    """Known ambiguity, risk, or caution attached to the request."""

    text: str
    severity: str = "note"

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("risk note cannot be empty")
        severity = self.severity.strip().lower() or "note"
        if severity not in {"note", "low", "medium", "high"}:
            raise ValueError(f"invalid risk severity: {self.severity!r}")
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(self, "severity", severity)


@dataclass(frozen=True)
class WorkflowRunStart:
    """Domain handoff from an accepted WorkRequest to one WorkflowRun."""

    work_request_ref: WorkRequestRef
    command: str
    title: str
    initial_stage: str = "PREPARE"

    @property
    def ticket_arg(self) -> str:
        """Compatibility argument for the current production-line driver."""

        return str(self.work_request_ref)


@dataclass
class WorkRequest:
    """Executable work request produced by authoring/refinement."""

    ref: WorkRequestRef
    title: str
    intent: str
    context: str = ""
    constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriteria] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    risk_notes: list[RiskNote] = field(default_factory=list)
    status: WorkRequestStatus = WorkRequestStatus.OPEN
    command: str = "implement"
    ouroboros_history: list[object] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.intent = self.intent.strip()
        self.context = self.context.strip()
        self.command = (self.command or "implement").strip().lower()
        if not self.title:
            raise ValueError("work request title cannot be empty")
        if not self.intent:
            raise ValueError("work request intent cannot be empty")
        if self.command not in {"implement", "research", "review"}:
            raise ValueError(f"invalid work request command: {self.command!r}")
        self.constraints = [c.strip() for c in self.constraints if c.strip()]
        self.non_goals = [n.strip() for n in self.non_goals if n.strip()]

    @property
    def is_accepted(self) -> bool:
        return bool(self.acceptance_criteria)

    def require_accepted(self) -> None:
        if not self.is_accepted:
            raise ValueError("accepted WorkRequest requires acceptance criteria")

    def start_workflow_run(self) -> WorkflowRunStart:
        """Create the provider-independent workflow handoff."""

        self.require_accepted()
        return WorkflowRunStart(
            work_request_ref=self.ref,
            command=self.command,
            title=self.title,
        )

