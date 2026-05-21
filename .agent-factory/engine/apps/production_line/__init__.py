"""Agent Factory production-line app entrypoint.

This is the operator-facing production line for processing one WorkRequest.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime

from ._common import update_step
from .stations import (
    done_step,
    fail_step,
    init_step,
    plan_step,
    report_step,
    validate_step,
    work_step,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent Factory production line")
    parser.add_argument("work_request", help="WR-NNN")
    parser.add_argument(
        "--step",
        choices=["INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE"],
        help="(debug) run through a specific station. registry_key is newly issued.",
    )
    args = parser.parse_args(argv)

    work_request = init_step(args.work_request)
    if args.step == "INIT":
        return 0

    try:
        plan_step(work_request)
        if not work_request.plan_json_path().exists() or not work_request.plan_md_path().exists():
            fail_step(work_request, "plan/plan.json or plan/plan.md not produced after retries")
            return 2
        update_step(work_request, "PLAN", "WORK")
        if args.step == "PLAN":
            return 0

        if not work_step(work_request):
            return 2
        update_step(work_request, "WORK", "VALIDATE")
        if args.step == "WORK":
            return 0

        validate_step(work_request)
        update_step(work_request, "VALIDATE", "REPORT")
        if args.step == "VALIDATE":
            return 0

        report_step(work_request)
        if not work_request.report_html_path().exists():
            fail_step(work_request, "report.html not produced after retries")
            return 2
        update_step(work_request, "REPORT", "DONE")
        if args.step == "REPORT":
            return 0

        done_step(work_request)
        return 0
    except Exception as exc:
        try:
            (work_request.work_dir / "failure.md").write_text(
                f"# production line failure\n\n"
                f"- ts: {datetime.now().isoformat(timespec='seconds')}\n"
                f"- exception: `{exc!r}`\n\n"
                f"```\n{traceback.format_exc()}```\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        fail_step(work_request, f"unhandled exception: {exc!r}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
