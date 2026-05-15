"""test_steps_init.py — INIT Step 헬퍼 단위 테스트.

대상 (SPEC.md §9.1.1, Stage 3-D):
  - _parse_ticket_meta: kanban_show 출력에서 (command, title) 추출
  - _maybe_create_worktree: command=research|review 시 (None, None) 반환

통합 (worktree 실제 생성) 은 smoke 사이클로 검증.
"""

from __future__ import annotations

from engine.v2.steps.init import _maybe_create_worktree, _parse_ticket_meta


_KANBAN_DUMP_TEMPLATE = """## T-491: 샘플 티켓

### Metadata
- Number: T-491
- Title: {title}
- Status: Review
- Command: {command}

### Relations
- derived-from: T-489

### Prompt
- Goal: 검증
"""


def test_parse_ticket_meta_implement() -> None:
    dump = _KANBAN_DUMP_TEMPLATE.format(command="implement", title="구현 티켓 샘플")
    command, title = _parse_ticket_meta(dump)
    assert command == "implement"
    assert title == "구현 티켓 샘플"


def test_parse_ticket_meta_research() -> None:
    dump = _KANBAN_DUMP_TEMPLATE.format(command="research", title="연구 조사")
    command, title = _parse_ticket_meta(dump)
    assert command == "research"
    assert title == "연구 조사"


def test_parse_ticket_meta_review() -> None:
    dump = _KANBAN_DUMP_TEMPLATE.format(command="review", title="리뷰 작업")
    command, title = _parse_ticket_meta(dump)
    assert command == "review"
    assert title == "리뷰 작업"


def test_parse_ticket_meta_unknown_command_fallback() -> None:
    """미지 command 는 implement 로 fallback (안전 default)."""
    dump = _KANBAN_DUMP_TEMPLATE.format(command="bogus", title="제목")
    command, _ = _parse_ticket_meta(dump)
    assert command == "implement"


def test_parse_ticket_meta_missing_command_default() -> None:
    """Command 라인 누락 시 implement default."""
    dump = "### Metadata\n- Number: T-1\n- Title: 제목\n"
    command, title = _parse_ticket_meta(dump)
    assert command == "implement"
    assert title == "제목"


def test_maybe_create_worktree_research_returns_none() -> None:
    """command=research → worktree 생성 X."""
    fb, wp = _maybe_create_worktree("T-491", "연구", "research")
    assert fb is None
    assert wp is None


def test_maybe_create_worktree_review_returns_none() -> None:
    """command=review → worktree 생성 X."""
    fb, wp = _maybe_create_worktree("T-491", "리뷰", "review")
    assert fb is None
    assert wp is None
