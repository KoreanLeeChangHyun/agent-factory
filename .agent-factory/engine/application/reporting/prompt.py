"""Build REPORT-stage LLM prompts from deterministic inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReportPromptInput:
    plan_body: str
    joined_work: str
    validate_body: str
    verify_verdict_body: str
    report_html_path: Path
    template_path: Path


def build_report_initial_prompt(data: ReportPromptInput) -> str:
    return (
        f"plan.md (자연어 본문, plan/plan.md):\n{data.plan_body}\n\n"
        f"work/**/*.md (모두 통째):\n{data.joined_work}\n\n"
        f"validate/report.md (LLM Quality 평가):\n{data.validate_body}\n\n"
        f"validate/verdict.json (driver structured VERIFY data):\n"
        f"{data.verify_verdict_body}\n\n"
        f"본 사이클의 사람 가독 보고서 `report.html` 를 "
        f"`{data.report_html_path}` 에 작성.\n"
        f"- template: `{data.template_path}` 를 베이스로 placeholder 4종 채움:\n"
        f"  - `{{{{title}}}}` → 티켓 제목\n"
        f"  - `{{{{summary}}}}` → 1~3 문단 자연어 요약 (HTML <p> 인라인)\n"
        f"  - `{{{{phase_sections}}}}` → Phase 별 산출 인용 "
        f"(HTML <section> 또는 <h3> 분할)\n"
        f"  - `{{{{plan_md_link}}}}` → plan.md 링크 텍스트 "
        f"(기본 'plan/plan.md')\n"
        f"- 본문에 `plan.md` 토큰 인용 필수 (R-PATH-1 정합).\n"
        f"- `validate/verdict.json` 의 request/plan/artifacts/checks 상태를 요약하고, "
        f"final decision 은 COMPLETE 단계 pending 으로 명시.\n"
        f"- **14+룰 verdict 산출·재평가 금지** (SPEC §0.1) — "
        f"driver `validate/rules.json` SSOT."
    )

