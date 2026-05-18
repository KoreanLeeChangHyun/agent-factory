"""REPORT Step — claude -p 1 spawn → report.html (T-504 cutover).

산출물 형식 캐논 §1 영역 3 — 사람 가독은 HTML. plan/plan.md (LLM 자연어) +
work/**/*.md (Phase 산출) + validate/report.md (Quality 평가) 통째 inject.
LLM 은 `templates/report.html` placeholder 를 채워 `report.html` 작성.
"""

from __future__ import annotations

from .._common import (
    TEMPLATES_DIR,
    WorkflowContext,
    load_prompt,
    write_context,
)
from .._retry import spawn_with_retry
from .._spawn import logical_session_name, new_session_uuid
from .._verify import verify_report_html


def report_step(ctx: WorkflowContext) -> None:
    plan_md_path = ctx.plan_md_path()
    plan_body = (
        plan_md_path.read_text(encoding="utf-8") if plan_md_path.exists() else ""
    )
    work_blocks: list[str] = []
    work_dir = ctx.work_dir / "work"
    if work_dir.exists():
        for md in sorted(work_dir.glob("**/*.md")):
            rel = md.relative_to(work_dir)
            work_blocks.append(
                f"### work/{rel.as_posix()}\n\n{md.read_text(encoding='utf-8')}\n"
            )
    joined_work = "\n".join(work_blocks) if work_blocks else "(work/ 비어있음)"
    validate_body = (
        ctx.validate_report_md_path().read_text(encoding="utf-8")
        if ctx.validate_report_md_path().exists()
        else ""
    )
    template_path = TEMPLATES_DIR / "report.html"
    initial_prompt = (
        f"plan.md (자연어 본문, plan/plan.md):\n{plan_body}\n\n"
        f"work/**/*.md (모두 통째):\n{joined_work}\n\n"
        f"validate/report.md (LLM Quality 평가):\n{validate_body}\n\n"
        f"본 사이클의 사람 가독 보고서 `report.html` 를 `{ctx.report_html_path()}` 에 작성.\n"
        f"- template: `{template_path}` 를 베이스로 placeholder 4종 채움:\n"
        f"  - `{{{{title}}}}` → 티켓 제목\n"
        f"  - `{{{{summary}}}}` → 1~3 문단 자연어 요약 (HTML <p> 인라인)\n"
        f"  - `{{{{phase_sections}}}}` → Phase 별 산출 인용 (HTML <section> 또는 <h3> 분할)\n"
        f"  - `{{{{plan_md_link}}}}` → plan.md 링크 텍스트 (기본 'plan/plan.md')\n"
        f"- 본문에 `plan.md` 토큰 인용 필수 (R-PATH-1 정합).\n"
        f"- **14+룰 verdict 산출·재평가 금지** (SPEC §0.1) — driver `validate/rules.json` SSOT."
    )
    session_id = new_session_uuid()
    logical = logical_session_name(ctx.ticket_no, "REPORT")
    ctx.session_ids[logical] = session_id
    write_context(ctx)
    spawn_with_retry(
        ctx,
        step="REPORT",
        initial_prompt=initial_prompt,
        system_prompt=load_prompt("report"),
        session_id=session_id,
        verify=lambda: verify_report_html(
            ctx.report_html_path(), ctx.plan_md_path()
        ),
        artifact_path=ctx.report_html_path(),
    )
