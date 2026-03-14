#!/usr/bin/env -S python3 -u
"""skill_mapper.py - Phase 0 스킬 매핑 스크립트.

plan.md의 태스크 skills 컬럼 + 명령어 기본 매핑으로
skill-map.md를 생성한다. LLM 불필요.

사용법:
  python3 .claude/scripts/flow/skill_mapper.py <registryKey>

입력:
  registryKey - YYYYMMDD-HHMMSS 형식 워크플로우 식별자
                workDir, plan.md 경로, command는 자동 해석

출력:
  <workDir>/work/skill-map.md (exit 0) 또는 에러 (exit 1) 또는 검증 실패 (exit 2)
  <workDir>/work/context/WXX-context.md (태스크별 컨텍스트 슬라이스)

exit code:
  0 - 성공 (스킬 매핑 완료 및 유효성 검증 통과)
  1 - 오류 (인자 누락, command 미발견 등 실행 오류)
  2 - 검증 실패 (스킬 미배정 또는 존재하지 않는 스킬명)
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta

# 프로젝트 루트 결정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import C_CLAUDE, C_DIM, C_RESET, load_json_file, resolve_abs_work_dir, resolve_project_root

# flow 디렉토리를 sys.path에 추가 (같은 디렉토리 내 모듈 직접 import용)
_flow_dir = os.path.dirname(os.path.abspath(__file__))
if _flow_dir not in sys.path:
    sys.path.insert(0, _flow_dir)

from plan_validator import parse_md_table_columns

PROJECT_ROOT = resolve_project_root()
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".claude", "skills")
CATALOG_FILE = os.path.join(SKILLS_DIR, "skill-catalog.md")

# 컨텍스트 토큰 예산 가드레일 (200K 기준 25%)
TOKEN_BUDGET_LIMIT = 50_000

EXTENSION_SKILL_MAP: dict[str, str] = {
    ".py": "convention-python",
    ".js": "convention-front",
    ".ts": "convention-front",
    ".jsx": "convention-front",
    ".tsx": "convention-front",
}


def resolve_skill_file(skill_name: str) -> str:
    """스킬의 로드 경로를 반환한다.

    COMPACT.md가 존재하면 COMPACT.md 경로를, 없으면 SKILL.md 경로를 반환한다.
    두 파일 모두 없으면 SKILL.md 경로를 반환한다 (존재 여부 보장 불가).

    Args:
        skill_name: 스킬 이름 (예: 'convention-python', 'review-code-quality')

    Returns:
        COMPACT.md 또는 SKILL.md의 절대 경로.

    Raises:
        경로 순회 시도 시 fallback으로 workflow-agent-worker/SKILL.md 경로 반환.
    """
    skill_dir = os.path.join(SKILLS_DIR, skill_name)
    skill_dir = os.path.normpath(skill_dir)
    if not skill_dir.startswith(os.path.normpath(SKILLS_DIR)):
        print(f"[WARN] 경로 순회 시도 차단: {skill_name}", file=sys.stderr)
        skill_dir = os.path.join(SKILLS_DIR, "workflow-agent-worker")
        return os.path.join(skill_dir, "SKILL.md")
    compact_path = os.path.join(skill_dir, "COMPACT.md")
    skill_path = os.path.join(skill_dir, "SKILL.md")
    if os.path.isfile(compact_path):
        return compact_path
    return skill_path


def estimate_token_budget(resolved_skills: list[str]) -> int:
    """스킬 목록의 예상 토큰 합산을 반환한다.

    각 스킬의 COMPACT.md 또는 SKILL.md 파일을 바이너리로 읽어
    ASCII 바이트(ascii_bytes // 4)와 non-ASCII 바이트(non_ascii_bytes // 6)를
    분리 계산하는 한국어 콘텐츠 보정 방식으로 토큰을 추정한다.
    합산이 TOKEN_BUDGET_LIMIT를 초과하면 경고 로그를 출력한다.

    Args:
        resolved_skills: 스킬 이름 목록

    Returns:
        예상 토큰 합산 정수값.
    """
    total_tokens = 0
    for skill_name in resolved_skills:
        file_path = resolve_skill_file(skill_name)
        if os.path.isfile(file_path):
            try:
                with open(file_path, "rb") as f:
                    data = f.read()
                ascii_bytes = sum(1 for b in data if b < 0x80)
                non_ascii_bytes = len(data) - ascii_bytes
                total_tokens += ascii_bytes // 4 + non_ascii_bytes // 6
            except OSError:
                pass

    if total_tokens > TOKEN_BUDGET_LIMIT:
        print(
            f"[WARN] 스킬 토큰 예산 초과: {total_tokens} > {TOKEN_BUDGET_LIMIT}",
            file=sys.stderr,
        )

    return total_tokens


def parse_catalog() -> dict[str, list[str]]:
    """skill-catalog.md에서 command defaults를 파싱한다.

    Returns:
        defaults: command -> [skill_names] 딕셔너리.
    """
    defaults: dict[str, list[str]] = {}

    if not os.path.isfile(CATALOG_FILE):
        return defaults

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    # Command Default Mapping 섹션 파싱
    in_cmd = False
    for line in lines:
        if "## Command Default Mapping" in line:
            in_cmd = True
            continue
        if in_cmd and line.startswith("## "):
            break
        if in_cmd and line.startswith("|") and not line.startswith("| 명령어") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                cmd = parts[1].strip()
                skills_str = parts[2].strip()
                if cmd and skills_str:
                    defaults[cmd] = [s.strip() for s in skills_str.split(",")]

    return defaults


def parse_plan_tasks(plan_path):
    """plan.md에서 태스크 테이블을 파싱하여 taskId, description, skills를 추출."""
    tasks = []

    if not os.path.isfile(plan_path):
        print(f"[ERROR] plan.md를 찾을 수 없습니다: {plan_path}", file=sys.stderr)
        return tasks

    with open(plan_path, "r", encoding="utf-8") as f:
        content = f.read()

    column_keywords = {
        "taskId": ["taskid", "태스크", "id"],
        "description": ["설명", "작업 내용", "description", "작업"],
        "skills": ["스킬", "skill"],
    }

    rows = parse_md_table_columns(content, None, column_keywords)

    for row in rows:
        task_id = row.get("taskId", "")
        if not (task_id and re.match(r"^W\d+", task_id)):
            continue

        raw_skills = row.get("skills", "")
        if raw_skills and raw_skills != "-" and raw_skills != "없음":
            skills = [s.strip() for s in re.split(r"[+,]", raw_skills) if s.strip()]
        else:
            skills = []

        tasks.append(
            {
                "taskId": task_id,
                "description": row.get("description", ""),
                "skills": skills,
            }
        )

    return tasks


def deduplicate(skills):
    """순서 유지하면서 중복 제거."""
    seen = set()
    result = []
    for s in skills:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def detect_extension_skills(description: str) -> list[str]:
    """태스크 description에서 파일 확장자를 감지하여 컨벤션 스킬 목록 반환."""
    found_exts = set()

    # (a) 파일경로.확장자: 단어문자들 + 점 + 확장자
    pattern_a = re.compile(r"\w+(\.[a-zA-Z]+)")
    for m in pattern_a.finditer(description):
        found_exts.add(m.group(1).lower())

    # (b) *.확장자
    pattern_b = re.compile(r"\*(\.[a-zA-Z]+)")
    for m in pattern_b.finditer(description):
        found_exts.add(m.group(1).lower())

    # (c) .확장자 뒤 공백/구두점/한글 (독립 확장자 표기)
    pattern_c = re.compile(r"(\.[a-zA-Z]+)(?=[\s,.\u3131-\uD7A3]|$)")
    for m in pattern_c.finditer(description):
        found_exts.add(m.group(1).lower())

    result = []
    seen = set()
    for ext in sorted(found_exts):
        skill = EXTENSION_SKILL_MAP.get(ext)
        if skill and skill not in seen:
            seen.add(skill)
            result.append(skill)

    return result


def resolve_skills(task: dict, command: str, defaults: dict) -> list[str]:
    """4단계(Level 0-1.5-2) 매칭으로 태스크의 최종 스킬 목록 결정.

    Level 0~1 매칭 결과가 비어있으면 skill_recommender.py의 TF-IDF 추천을 fallback으로 호출한다.
    """
    if not command:
        return []

    skills = []

    # Level 0: plan.md에 명시된 스킬
    if task["skills"]:
        skills.extend(task["skills"])

    # Level 1: 명령어 기본 매핑
    if command in defaults:
        skills.extend(defaults[command])

    skills = deduplicate(skills)

    # Level 1.5: 확장자 기반 컨벤션 스킬 자동 매핑
    if task.get("description"):
        ext_skills = detect_extension_skills(task["description"])
        for s in ext_skills:
            if s not in skills:
                skills.append(s)

    # Level 2 (fallback): 매칭 결과가 없을 때 TF-IDF 추천 호출
    fallback_skills = []
    if not skills and task.get("description"):
        try:
            # lazy import: fallback이 필요한 경우에만 로드
            from skill_recommender import recommend
            candidates = recommend(task["description"])
            # score 0.1 이상인 스킬명만 추출
            fallback_skills = [name for name, score in candidates if score >= 0.1]
            skills = list(fallback_skills)
        except Exception as e:
            # import 실패 또는 예상치 못한 오류 시 경고 로그 출력, 폴백 체인 정상 진행
            print(f"[WARN] skill_recommender 호출 실패: {e}", file=sys.stderr)

    task["fallback_skills"] = fallback_skills
    return skills


def _build_skill_map_header(tasks):
    """skill-map.md의 헤더 및 요약 테이블 행 목록을 생성."""
    lines = []
    lines.append("# Skill Map")
    lines.append("")
    lines.append("> 이 파일은 `skill_mapper.py`에 의해 자동 생성됩니다.")
    lines.append("> Worker는 매핑 테이블에서 스킬 목록을 확인한 후, 각 스킬 디렉터리의 COMPACT.md (없으면 SKILL.md)를 직접 Read하여 지침을 획득합니다.")
    lines.append("> `resolve_skill_file()` 기준: COMPACT.md 존재 시 우선 로드, 없으면 SKILL.md 로드.")
    lines.append("")
    lines.append("## 태스크별 스킬 매핑")
    lines.append("")
    lines.append("| 태스크 | 스킬 |")
    lines.append("|--------|------|")
    for task in tasks:
        lines.extend(_build_skill_map_rows(task))
    lines.append("")
    return lines


def _build_skill_map_rows(task):
    """태스크별 매핑 테이블 행 목록을 생성."""
    lines = []
    resolved = task.get("resolved", [])
    fallback = set(task.get("fallback_skills", []))
    if resolved:
        skill_parts = [f"{s} (추천)" if s in fallback else s for s in resolved]
        skill_str = ", ".join(skill_parts)
    else:
        skill_str = "(없음)"
    lines.append(f"| {task['taskId']} | {skill_str} |")
    return lines


def write_skill_map(work_dir, tasks):
    """skill-map.md를 생성.

    매핑 테이블만 포함한다. 스킬 지침은 Worker가 직접 Read한다.
    """
    output_dir = os.path.join(work_dir, "work")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "skill-map.md")

    lines = _build_skill_map_header(tasks)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


# =============================================================================
# mkdir 기반 POSIX 잠금 (로컬 헬퍼 - 순환 import 방지)
# =============================================================================

def _acquire_lock(lock_dir, max_wait=2):
    """mkdir 기반 POSIX 잠금 획득. stale lock 감지 포함."""
    waited = 0
    while True:
        try:
            os.makedirs(lock_dir)
            try:
                with open(os.path.join(lock_dir, "pid"), "w") as f:
                    f.write(f"{os.getpid()} {time.time()}")
            except OSError:
                pass
            return True
        except OSError:
            pid_file = os.path.join(lock_dir, "pid")
            if os.path.isfile(pid_file):
                try:
                    with open(pid_file, "r") as f:
                        pid_content = f.read().strip()
                    parts = pid_content.split()
                    lock_pid = int(parts[0])
                    lock_ts = float(parts[1]) if len(parts) > 1 else 0
                    os.kill(lock_pid, 0)
                    if lock_ts and (time.time() - lock_ts) > max_wait:
                        try:
                            with open(pid_file, "r") as f:
                                recheck = f.read().strip()
                            if recheck == pid_content:
                                shutil.rmtree(lock_dir)
                                waited += 1
                                continue
                        except OSError:
                            pass
                except (ValueError, ProcessLookupError, OSError):
                    try:
                        with open(pid_file, "r") as f:
                            recheck = f.read().strip()
                        if recheck == pid_content:
                            shutil.rmtree(lock_dir)
                    except OSError:
                        pass
                    waited += 1
                    continue
                except PermissionError:
                    pass
            waited += 1
            if waited >= max_wait:
                return False
            time.sleep(1)


def _release_lock(lock_dir):
    """잠금 해제."""
    try:
        pid_file = os.path.join(lock_dir, "pid")
        if os.path.exists(pid_file):
            os.unlink(pid_file)
    except OSError:
        pass
    try:
        os.rmdir(lock_dir)
    except OSError:
        pass


# =============================================================================
# .dashboard/.skills.md 갱신
# =============================================================================

def _update_skills_md(registry_key: str, command: str, tasks: list, all_resolved: list, token_budget: int) -> None:
    """skill_mapper.py 실행 결과를 .dashboard/.skills.md에 행으로 삽입한다.

    비차단: 모든 예외를 삼켜서 워크플로우 실행에 영향을 주지 않는다.
    """
    try:
        KST = timezone(timedelta(hours=9))
        skills_md = os.path.join(PROJECT_ROOT, ".dashboard", ".skills.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".dashboard", ".skills.md.lock")
        marker = "<!-- 새 항목은 이 줄 아래에 추가됩니다 -->"

        # registryKey에서 날짜 추출: YYYYMMDD-HHMMSS → MM-DD HH:MM
        try:
            date_part, time_part = registry_key.split("/")[0].split("-")
            date_str = f"{date_part[4:6]}-{date_part[6:8]} {time_part[0:2]}:{time_part[2:4]}"
        except Exception:
            date_str = datetime.now(KST).strftime("%m-%d %H:%M")

        # 작업ID: registryKey 전체 (경로 포함)
        work_id = registry_key

        # skill-map.md 링크: .dashboard/에서 ../.workflow/{timestamp}/{workName}/{command}/work/skill-map.md
        try:
            rel_work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
            rel_work_dir = os.path.relpath(rel_work_dir, PROJECT_ROOT)
            skill_map_link = f"[{work_id}](../{rel_work_dir}/work/skill-map.md)"
        except Exception:
            skill_map_link = work_id

        # 스킬 목록 (<br> 태그 개행 구분, 전체 표시)
        skills_joined = "<br>".join(all_resolved) if all_resolved else "(없음)"

        # fallback 여부
        has_fallback = any(task.get("fallback_skills") for task in tasks)
        fallback_str = "Y" if has_fallback else "N"

        # 토큰초과 여부
        over_budget = "Y" if token_budget > TOKEN_BUDGET_LIMIT else "N"

        # 행 생성
        row = (
            f"| {date_str} | {skill_map_link} | {command} "
            f"| {len(tasks)} | {len(all_resolved)} | {skills_joined} "
            f"| {fallback_str} | {over_budget} |"
        )

        # skills.md 읽기
        from data.constants import SKILLS_HEADER_LINE, SKILLS_SEPARATOR_LINE

        content = ""
        if os.path.exists(skills_md):
            with open(skills_md, "r", encoding="utf-8") as f:
                content = f.read()

        if marker not in content:
            content = f"# 스킬 매핑 추적\n\n{marker}\n\n{SKILLS_HEADER_LINE}\n{SKILLS_SEPARATOR_LINE}\n"

        separator_line = SKILLS_SEPARATOR_LINE

        if separator_line in content:
            marker_pos = content.find(marker)
            if marker_pos >= 0:
                sep_pos = content.find(separator_line, marker_pos)
                if sep_pos >= 0:
                    insert_pos = sep_pos + len(separator_line)
                    if insert_pos < len(content) and content[insert_pos] == "\n":
                        insert_pos += 1
                    content = content[:insert_pos] + row + "\n" + content[insert_pos:]
                else:
                    content = content.replace(
                        marker, f"{marker}\n\n{SKILLS_HEADER_LINE}\n{separator_line}\n{row}"
                    )
            else:
                content = content.replace(
                    marker, f"{marker}\n\n{SKILLS_HEADER_LINE}\n{separator_line}\n{row}"
                )
        else:
            content = content.replace(
                marker, f"{marker}\n\n{SKILLS_HEADER_LINE}\n{separator_line}\n{row}"
            )

        # 원자적 쓰기
        os.makedirs(os.path.dirname(skills_md), exist_ok=True)
        locked = _acquire_lock(lock_dir)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(skills_md), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            shutil.move(tmp, skills_md)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        finally:
            if locked:
                _release_lock(lock_dir)

    except Exception:
        pass


def _get_known_skills() -> set[str]:
    """skill-catalog.md에 등록된 스킬명 집합을 반환한다.

    CATALOG_FILE에서 Skill Descriptions 섹션을 파싱하여 등록된 스킬명 목록을 추출한다.
    파일이 없거나 파싱 실패 시 빈 집합을 반환하여 검증을 건너뛴다.

    Returns:
        등록된 스킬명 집합. 파싱 실패 시 빈 집합.
    """
    known: set[str] = set()

    if not os.path.isfile(CATALOG_FILE):
        return known

    try:
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return known

    lines = content.split("\n")
    in_skills = False
    for line in lines:
        if "## Skill Descriptions" in line:
            in_skills = True
            continue
        if in_skills and line.startswith("## "):
            break
        if in_skills and line.startswith("|") and not line.startswith("| 스킬명") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2 and parts[1]:
                known.add(parts[1].strip())

    return known


def validate_skill_mapping(tasks: list[dict]) -> tuple[bool, str]:
    """태스크 스킬 매핑의 유효성을 검증한다.

    각 태스크에 대해 다음을 검증한다:
    (a) resolved 스킬이 1개 이상 배정되었는지 확인
    (b) 배정된 스킬이 skill-catalog.md에 등록된 스킬인지 확인

    skill-catalog.md 파싱에 실패하면 (b) 검증을 건너뛰고
    (a)만 수행한다.

    Args:
        tasks: parse_plan_tasks()에서 반환된 태스크 목록.
               각 태스크는 'taskId'와 'resolved' 키를 포함해야 한다.

    Returns:
        (True, "") - 모든 검증 통과
        (False, "실패 사유 상세") - 검증 실패 시 실패한 태스크 ID와 사유 포함
    """
    known_skills = _get_known_skills()
    failures: list[str] = []

    for task in tasks:
        task_id = task.get("taskId", "(unknown)")
        resolved = task.get("resolved", [])

        # (a) 스킬 미배정 확인
        if not resolved:
            failures.append(f"  - {task_id}: 스킬 미배정 (resolved 스킬 없음)")
            continue

        # (b) 존재하지 않는 스킬명 확인 (catalog 파싱 성공 시에만)
        if known_skills:
            unknown = [s for s in resolved if s not in known_skills]
            if unknown:
                failures.append(
                    f"  - {task_id}: 존재하지 않는 스킬명 {unknown} "
                    f"(skill-catalog.md 미등록)"
                )

    if failures:
        reason = "스킬 매핑 검증 실패:\n" + "\n".join(failures)
        return False, reason

    return True, ""


def slice_plan_context(plan_path, tasks, output_dir):
    """plan.md에서 각 워커의 태스크 섹션만 추출하여 work/context/WXX-context.md로 저장.

    "### WXX:" H3 서브섹션을 태스크별로 분리하여 워커가 자신에게 필요한
    컨텍스트(1-2K 토큰)만 읽을 수 있도록 슬라이싱한다.
    plan.md 전체(5-10K)를 로드하는 대신 태스크별 컨텍스트만 제공하여
    워커 컨텍스트 예산을 절감한다.

    Args:
        plan_path: plan.md 절대 경로
        tasks: parse_plan_tasks()에서 반환된 태스크 목록 (taskId 필드 필요)
        output_dir: work/context/ 디렉터리 기준 (work_dir/work/context/)

    Returns:
        생성된 컨텍스트 파일 경로 목록 (생성 성공한 파일만)
    """
    if not os.path.isfile(plan_path):
        print(f"[WARN] slice_plan_context: plan.md를 찾을 수 없습니다: {plan_path}", file=sys.stderr)
        return []

    with open(plan_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    # 태스크 ID 집합 (W01, W02 등)
    task_ids = {task["taskId"] for task in tasks if task.get("taskId")}

    # plan.md에서 "### WXX:" 패턴의 H3 섹션 위치를 탐색
    # 섹션 시작: "### W01:" 또는 "### W01 " 형태
    section_starts = {}  # taskId -> line_index
    h3_pattern = re.compile(r"^###\s+(W\d+)[:\s]")

    for i, line in enumerate(lines):
        m = h3_pattern.match(line)
        if m:
            tid = m.group(1)
            if tid in task_ids:
                section_starts[tid] = i

    if not section_starts:
        # H3 섹션이 없으면 스킵
        return []

    # 각 태스크 섹션 끝 위치 결정: 다음 H3/H2/H1이 나오거나 파일 끝
    sorted_starts = sorted(section_starts.items(), key=lambda x: x[1])
    end_pattern = re.compile(r"^#{1,3}\s+")

    os.makedirs(output_dir, exist_ok=True)
    created = []

    for idx, (task_id, start_line) in enumerate(sorted_starts):
        # 섹션 끝 탐색: 다음 H1/H2/H3 라인 또는 파일 끝
        end_line = len(lines)
        for j in range(start_line + 1, len(lines)):
            if end_pattern.match(lines[j]):
                end_line = j
                break

        section_lines = lines[start_line:end_line]

        # 후미 빈 줄 제거
        while section_lines and not section_lines[-1].strip():
            section_lines.pop()

        if not section_lines:
            continue

        section_content = "\n".join(section_lines) + "\n"

        # 파일명: WXX-context.md
        out_path = os.path.join(output_dir, f"{task_id}-context.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(section_content)

        created.append(out_path)

    return created


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 skill_mapper.py <registryKey>", file=sys.stderr)
        sys.exit(1)

    registry_key = sys.argv[1]

    # registryKey → workDir, plan.md, command 자동 해석
    work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
    plan_path = os.path.join(work_dir, "plan.md")
    ctx = load_json_file(os.path.join(work_dir, ".context.json"))
    command = ctx.get("command", "") if isinstance(ctx, dict) else ""

    if not command:
        print(f"[ERROR] .context.json에서 command를 찾을 수 없습니다: {work_dir}", file=sys.stderr)
        sys.exit(1)

    # 1. 카탈로그 파싱
    defaults = parse_catalog()

    # 2. plan.md 태스크 파싱
    tasks = parse_plan_tasks(plan_path)
    if not tasks:
        print(f"[WARN] plan.md에서 태스크를 찾을 수 없습니다: {plan_path}", file=sys.stderr)
        # 빈 skill-map.md라도 생성
        os.makedirs(os.path.join(work_dir, "work"), exist_ok=True)
        with open(os.path.join(work_dir, "work", "skill-map.md"), "w", encoding="utf-8") as f:
            f.write("# Skill Map\n\n> 태스크 없음\n")
        sys.exit(0)

    # 3. 각 태스크별 스킬 결정
    for task in tasks:
        task["resolved"] = resolve_skills(task, command, defaults)

    # 3.5. 토큰 예산 검증 (write_skill_map 직전)
    all_resolved = []
    for task in tasks:
        for skill in task.get("resolved", []):
            if skill not in all_resolved:
                all_resolved.append(skill)
    token_budget = estimate_token_budget(all_resolved)

    # 4. skill-map.md 생성
    output_path = write_skill_map(work_dir, tasks)

    # 5. 태스크별 컨텍스트 슬라이싱 (plan.md → work/context/WXX-context.md)
    context_dir = os.path.join(work_dir, "work", "context")
    created_contexts = slice_plan_context(plan_path, tasks, context_dir)

    # 5.5. 스킬 매핑 대시보드 갱신 (비차단)
    _update_skills_md(registry_key, command, tasks, all_resolved, token_budget)

    # 5.6. 스킬 매핑 유효성 검증 (exit code 2 = 검증 실패)
    valid, reason = validate_skill_mapping(tasks)
    if not valid:
        print(reason, file=sys.stderr)
        sys.exit(2)

    # 배너 출력
    rel_path = os.path.relpath(output_path, PROJECT_ROOT)
    print(f"{C_CLAUDE}║ STATE:{C_RESET} {C_DIM}스킬 매핑{C_RESET}", flush=True)
    print(f"{C_CLAUDE}║{C_RESET} {C_CLAUDE}>>{C_RESET} {C_DIM}{rel_path}{C_RESET}", flush=True)
    if created_contexts:
        rel_ctx = os.path.relpath(context_dir, PROJECT_ROOT)
        print(f"{C_CLAUDE}║{C_RESET} {C_CLAUDE}>>{C_RESET} {C_DIM}{rel_ctx}/ ({len(created_contexts)}개 컨텍스트 슬라이스){C_RESET}", flush=True)


if __name__ == "__main__":
    main()
