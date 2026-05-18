"""v2 driver — entrypoint + 6 Step orchestration.

SPEC.md §7 (책임 분담) + §7.2 의사 코드. LLM 호출 0 (claude -p subprocess 만).

Step 함수는 `steps/*.py` 에 분리. driver.py 는 main() + argparse 만.

CLI:
    python -m engine.v2.driver T-NNN
    python -m engine.v2.driver T-NNN --step PLAN
"""

from __future__ import annotations

import argparse
import sys

from ._common import update_step
from .steps import (
    done_step,
    fail_step,
    init_step,
    plan_step,
    report_step,
    validate_step,
    work_step,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v2 workflow driver")
    parser.add_argument("ticket", help="T-NNN")
    parser.add_argument(
        "--step",
        choices=["INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE"],
        help="(디버그) 특정 Step 까지 실행 후 종료. registry_key 는 신규 발급.",
    )
    args = parser.parse_args(argv)

    ctx = init_step(args.ticket)
    if args.step == "INIT":
        return 0

    try:
        plan_step(ctx)
        if not ctx.plan_json_path().exists() or not ctx.plan_md_path().exists():
            fail_step(ctx, "plan/plan.json or plan/plan.md not produced after retries")
            return 2
        update_step(ctx, "PLAN", "WORK")
        if args.step == "PLAN":
            return 0

        if not work_step(ctx):
            return 2
        update_step(ctx, "WORK", "VALIDATE")
        if args.step == "WORK":
            return 0

        validate_step(ctx)
        update_step(ctx, "VALIDATE", "REPORT")
        if args.step == "VALIDATE":
            return 0

        report_step(ctx)
        if not ctx.report_html_path().exists():
            fail_step(ctx, "report.html not produced after retries")
            return 2
        update_step(ctx, "REPORT", "DONE")
        if args.step == "REPORT":
            return 0

        done_step(ctx)
        return 0
    except Exception as exc:
        fail_step(ctx, f"unhandled exception: {exc!r}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
