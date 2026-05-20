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
        f"plan.md (natural language body, plan/plan.md): \n {data.plan_body} \n \n"
        f"work/**/*.md (all in its entirety): \n {data.joined_work} \n \n"
        f"validate/report.md (LLM Quality Evaluation): \n {data.validate_body} \n \n"
        f"validate/verdict.json (driver structured VERIFY data):\n"
        f"{data.verify_verdict_body}\n\n"
        f"This cycle's human-readable report `report.html`"
        f"Written in `{data.report_html_path}`. \n"
        f"- Template: Fill in 4 types of placeholders based on `{data.template_path}`: \n"
        f"- `{{{{title}}}}` → Ticket title \n"
        f"- `{{{{summary}}}}` → 1-3 paragraph natural language summary (HTML <p> inline) \n"
        f"- `{{{{phase_sections}}}}` → Calculation quotation for each phase"
        f"(HTML <section> or <h3> split) \n"
        f"- `{{{{plan_md_link}}}}` → plan.md link text"
        f"(default 'plan/plan.md') \n"
        f"- The `plan.md` token must be cited in the text (R-PATH-1 matching). \n"
        f"- Summarize the status of request/plan/artifacts/checks in `validate/verdict.json`,"
        f"The final decision is specified as pending at the COMPLETE stage. \n"
        f"- **14+ rule verdict calculation and re-evaluation prohibited** (SPEC §0.1) —"
        f"driver `validate/rules.json` SSOT."
    )

