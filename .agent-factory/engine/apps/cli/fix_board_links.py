#!/usr/bin/env python3
"""
fix_board_links.py — board 메타 파일 링크 일괄 정정 스크립트

구 구조: runs/<key>/<work_name>/<command>/<file>
신 구조: runs/<key>/<file>

Usage:
    python3 fix_board_links.py --mode dry-run --target <path> [--target <path> ...]
    python3 fix_board_links.py --mode apply   --target <path> [--target <path> ...]
"""

import argparse
import re
import sys
from pathlib import Path

# Old structure → New structure regular expression
# runs(/.history)?/<key>/<work_name>/(implement|research|review)/<file>
# → runs(/.history)?/<key>/<file>
PATTERN = re.compile(
    r'(runs(?:/\.history)?/\d{8}-\d{6})/[^/\s\)\]\"\']+/(?:implement|research|review)/'
    r'(workflow\.log|metrics\.jsonl|usage\.json|report\.md|plan\.md|status\.json'
    r'|init-result\.json|summary\.txt|work/skill-map\.md)'
)
REPLACEMENT = r'\1/\2'


def process_file(path: Path, mode: str) -> dict:
    """
    파일을 처리하고 결과 통계를 반환한다.

    Returns:
        {
            "path": str,
            "total_lines": int,
            "changed_lines": int,
            "changed_count": int,  # total number of substitutions
            "samples": list[str],  # Changed line samples (maximum 5)
        }
    """
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)

    changed_lines = 0
    changed_count = 0
    samples = []
    new_lines = []

    for line in lines:
        new_line, n = PATTERN.subn(REPLACEMENT, line)
        if n > 0:
            changed_lines += 1
            changed_count += n
            if len(samples) < 5:
                samples.append(f"  - {line.rstrip()}\n  + {new_line.rstrip()}")
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    result = {
        "path": str(path),
        "total_lines": len(lines),
        "changed_lines": changed_lines,
        "changed_count": changed_count,
        "samples": samples,
    }

    if mode == "apply" and changed_count > 0:
        new_content = "".join(new_lines)
        path.write_text(new_content, encoding="utf-8")
        # Line count invariant verification
        result_lines = new_content.splitlines(keepends=True)
        result["new_total_lines"] = len(result_lines)
        if len(result_lines) != len(lines):
            print(
                f"[ERROR] Line count mismatch: {path}"
                f"before={len(lines)} after={len(result_lines)}",
                file=sys.stderr,
            )
            sys.exit(1)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Batch correction of board meta file links (old structure → new structure)"
    )
    parser.add_argument(
        "--mode",
        choices=["dry-run", "apply"],
        default="dry-run",
        help="dry-run: Preview changes, apply: Modify actual files (default: dry-run)",
    )
    parser.add_argument(
        "--target",
        action="append",
        dest="targets",
        metavar="PATH",
        required=True,
        help="File path to process (repeatable)",
    )
    args = parser.parse_args()

    total_changed_lines = 0
    total_changed_count = 0

    print(f"[mode={args.mode}]")
    print()

    for target_str in args.targets:
        path = Path(target_str)
        if not path.exists():
            print(f"[WARN] No file: {path}", file=sys.stderr)
            continue

        result = process_file(path, args.mode)
        total_changed_lines += result["changed_lines"]
        total_changed_count += result["changed_count"]

        print(f"File: {result['path']}")
        print(f"Total number of lines: {result['total_lines']}")
        print(f"Number of changed lines: {result['changed_lines']}")
        print(f"Number of substitutions: {result['changed_count']}")

        if result["samples"]:
            print("Samples (up to 5):")
            for s in result["samples"]:
                print(f"    {s}")

        if args.mode == "apply":
            new_total = result.get("new_total_lines", result["total_lines"])
            print(f"Number of lines after applying: {new_total} (check for immutability)")

        print()

    print("=" * 60)
    print(f"Total — Number of lines changed: {total_changed_lines}, Number of substitutions: {total_changed_count}")

    if args.mode == "dry-run":
        print()
        print("[dry-run complete] If you rerun in apply mode, the actual file will be modified.")
    else:
        print()
        print("[apply completed]")


if __name__ == "__main__":
    main()
