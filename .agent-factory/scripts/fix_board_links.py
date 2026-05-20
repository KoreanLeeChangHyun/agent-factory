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

# 구 구조 → 신 구조 정규식
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
            "changed_count": int,  # 총 치환 횟수
            "samples": list[str],  # 변경된 라인 샘플 (최대 5건)
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
        # 라인 수 불변 검증
        result_lines = new_content.splitlines(keepends=True)
        result["new_total_lines"] = len(result_lines)
        if len(result_lines) != len(lines):
            print(
                f"[ERROR] 라인 수 불일치: {path} "
                f"before={len(lines)} after={len(result_lines)}",
                file=sys.stderr,
            )
            sys.exit(1)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="board 메타 파일 링크 일괄 정정 (구 구조 → 신 구조)"
    )
    parser.add_argument(
        "--mode",
        choices=["dry-run", "apply"],
        default="dry-run",
        help="dry-run: 변경 내용 미리보기, apply: 실제 파일 수정 (default: dry-run)",
    )
    parser.add_argument(
        "--target",
        action="append",
        dest="targets",
        metavar="PATH",
        required=True,
        help="처리할 파일 경로 (반복 가능)",
    )
    args = parser.parse_args()

    total_changed_lines = 0
    total_changed_count = 0

    print(f"[mode={args.mode}]")
    print()

    for target_str in args.targets:
        path = Path(target_str)
        if not path.exists():
            print(f"[WARN] 파일 없음: {path}", file=sys.stderr)
            continue

        result = process_file(path, args.mode)
        total_changed_lines += result["changed_lines"]
        total_changed_count += result["changed_count"]

        print(f"파일: {result['path']}")
        print(f"  총 라인 수 : {result['total_lines']}")
        print(f"  변경 라인 수: {result['changed_lines']}")
        print(f"  치환 횟수  : {result['changed_count']}")

        if result["samples"]:
            print("  샘플 (최대 5건):")
            for s in result["samples"]:
                print(f"    {s}")

        if args.mode == "apply":
            new_total = result.get("new_total_lines", result["total_lines"])
            print(f"  적용 후 라인 수: {new_total} (불변 확인)")

        print()

    print("=" * 60)
    print(f"합계 — 변경 라인 수: {total_changed_lines}, 치환 횟수: {total_changed_count}")

    if args.mode == "dry-run":
        print()
        print("[dry-run 완료] apply 모드로 재실행하면 실제 파일이 수정됩니다.")
    else:
        print()
        print("[apply 완료]")


if __name__ == "__main__":
    main()
