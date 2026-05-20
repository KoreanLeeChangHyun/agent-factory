"""Agent Factory production-line app entrypoint.

This is the operator-facing production line for processing one ticket.
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
    parser.add_argument("ticket", help="T-NNN")
    parser.add_argument(
        "--step",
        choices=["INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE"],
        help="(debug) run through a specific station. registry_key is newly issued.",
    )
    args = parser.parse_args(argv)

    ticket = init_step(args.ticket)
    if args.step == "INIT":
        return 0

    try:
        plan_step(ticket)
        if not ticket.plan_json_path().exists() or not ticket.plan_md_path().exists():
            fail_step(ticket, "plan/plan.json or plan/plan.md not produced after retries")
            return 2
        update_step(ticket, "PLAN", "WORK")
        if args.step == "PLAN":
            return 0

        if not work_step(ticket):
            return 2
        update_step(ticket, "WORK", "VALIDATE")
        if args.step == "WORK":
            return 0

        validate_step(ticket)
        update_step(ticket, "VALIDATE", "REPORT")
        if args.step == "VALIDATE":
            return 0

        report_step(ticket)
        if not ticket.report_html_path().exists():
            fail_step(ticket, "report.html not produced after retries")
            return 2
        update_step(ticket, "REPORT", "DONE")
        if args.step == "REPORT":
            return 0

        done_step(ticket)
        return 0
    except Exception as exc:
        try:
            (ticket.work_dir / "failure.md").write_text(
                f"# production line failure\n\n"
                f"- ts: {datetime.now().isoformat(timespec='seconds')}\n"
                f"- exception: `{exc!r}`\n\n"
                f"```\n{traceback.format_exc()}```\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        fail_step(ticket, f"unhandled exception: {exc!r}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
