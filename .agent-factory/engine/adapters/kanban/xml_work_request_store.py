"""WorkRequestStore backed by the existing kanban XML ticket layout."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from engine.core.work_requests.domain import (
    AcceptanceCriteria,
    RiskNote,
    WorkRequest,
    WorkRequestRef,
    WorkRequestStatus,
)
from engine.core.work_requests.ouroboros import OuroborosEntry, OuroborosPhase
from engine.core.work_requests.repository import WorkRequestStore


_STATUS_DIRS = {
    WorkRequestStatus.TODO: "todo",
    WorkRequestStatus.OPEN: "open",
    WorkRequestStatus.IN_PROGRESS: "progress",
    WorkRequestStatus.REVIEW: "review",
    WorkRequestStatus.DONE: "done",
}
_STATUS_BY_VALUE = {status.value: status for status in WorkRequestStatus}


class XmlWorkRequestStore(WorkRequestStore):
    """Adapter for `.agent-factory/tickets/{state}/T-NNN.xml` files."""

    def __init__(self, tickets_root: str | Path) -> None:
        self.tickets_root = Path(tickets_root)

    def get(self, ref: WorkRequestRef) -> WorkRequest:
        path = self._find_path(ref)
        if path is None:
            raise FileNotFoundError(f"work request not found: {ref}")
        return self._parse(path)

    def save(self, request: WorkRequest) -> None:
        current_path = self._find_path(request.ref)
        target_dir = self.tickets_root / _STATUS_DIRS[request.status]
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{request.ref}.xml"

        if current_path is None:
            root = ET.Element("ticket")
        else:
            tree = ET.parse(current_path)
            root = tree.getroot()

        self._write_model(root, request)
        ET.indent(root, space="  ")
        ET.ElementTree(root).write(target_path, encoding="utf-8", xml_declaration=True)

        if current_path is not None and current_path != target_path:
            current_path.unlink()

    def _find_path(self, ref: WorkRequestRef) -> Path | None:
        filename = f"{ref}.xml"
        for dirname in ("todo", "open", "progress", "review", "done", "active", ""):
            candidate = self.tickets_root / dirname / filename if dirname else self.tickets_root / filename
            if candidate.is_file():
                return candidate
        return None

    def _parse(self, path: Path) -> WorkRequest:
        root = ET.parse(path).getroot()
        metadata = root.find("metadata")
        if metadata is None:
            metadata = root
        prompt = root.find("prompt")

        ref = WorkRequestRef.parse(_child_text(metadata, "number") or path.stem)
        status = _STATUS_BY_VALUE.get(_child_text(metadata, "status"), WorkRequestStatus.OPEN)
        command = _child_text(metadata, "command") or "implement"
        title = _child_text(metadata, "title") or str(ref)

        intent = _child_text(prompt, "goal") or title
        context = _child_text(prompt, "context")
        constraints = _split_lines(_child_text(prompt, "constraints"))
        criteria = [
            AcceptanceCriteria(line)
            for line in _split_lines(_child_text(prompt, "criteria"))
        ]
        risk_notes = [
            RiskNote(line)
            for line in _split_lines(_child_text(prompt, "risk_notes"))
        ]
        non_goals = _split_lines(_child_text(prompt, "non_goals"))
        ouroboros_history = _parse_ouroboros_history(root)

        return WorkRequest(
            ref=ref,
            title=title,
            intent=intent,
            context=context,
            constraints=constraints,
            acceptance_criteria=criteria,
            non_goals=non_goals,
            risk_notes=risk_notes,
            status=status,
            command=command,
            ouroboros_history=ouroboros_history,
        )

    def _write_model(self, root: ET.Element, request: WorkRequest) -> None:
        metadata = _ensure_child(root, "metadata")
        _set_child_text(metadata, "number", str(request.ref))
        _set_child_text(metadata, "title", request.title)
        _set_child_text(metadata, "status", request.status.value)
        _set_child_text(metadata, "command", request.command)

        prompt = _ensure_child(root, "prompt")
        _set_child_text(prompt, "goal", request.intent)
        _set_child_text(prompt, "context", request.context)
        _set_child_text(prompt, "constraints", "\n".join(request.constraints))
        _set_child_text(
            prompt,
            "criteria",
            "\n".join(c.text for c in request.acceptance_criteria),
        )
        _set_child_text(prompt, "non_goals", "\n".join(request.non_goals))
        _set_child_text(prompt, "risk_notes", "\n".join(r.text for r in request.risk_notes))

        history = _ensure_child(root, "ouroboros_history")
        history.clear()
        for item in request.ouroboros_history:
            entry = _coerce_ouroboros_entry(item)
            node = ET.SubElement(
                history,
                "entry",
                {"phase": entry.phase.value, "created_at": entry.created_at},
            )
            node.text = entry.text


def _child_text(elem: ET.Element | None, tag: str) -> str:
    if elem is None:
        return ""
    child = elem.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _ensure_child(elem: ET.Element, tag: str) -> ET.Element:
    child = elem.find(tag)
    if child is None:
        child = ET.SubElement(elem, tag)
    return child


def _set_child_text(elem: ET.Element, tag: str, value: str) -> None:
    child = _ensure_child(elem, tag)
    child.text = value


def _split_lines(value: str) -> list[str]:
    return [line.strip(" -\t") for line in value.splitlines() if line.strip(" -\t")]


def _parse_ouroboros_history(root: ET.Element) -> list[OuroborosEntry]:
    history = root.find("ouroboros_history")
    if history is None:
        return []
    entries: list[OuroborosEntry] = []
    for node in history.findall("entry"):
        phase = OuroborosPhase((node.get("phase") or "").strip())
        created_at = (node.get("created_at") or "").strip()
        text = node.text or ""
        entries.append(OuroborosEntry(phase=phase, text=text, created_at=created_at))
    return entries


def _coerce_ouroboros_entry(item: object) -> OuroborosEntry:
    if isinstance(item, OuroborosEntry):
        return item
    if isinstance(item, dict):
        return OuroborosEntry(
            phase=OuroborosPhase(str(item.get("phase") or "")),
            text=str(item.get("text") or ""),
            created_at=str(item.get("created_at") or ""),
        )
    raise TypeError(f"invalid ouroboros history entry: {item!r}")
