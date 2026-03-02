#!/usr/bin/env -S python3 -u
"""
catalog_sync.py - 스킬 카탈로그 생성/갱신 CLI (단일 소스)

.claude/skills/*/SKILL.md를 전수 스캔하여 frontmatter를 파싱하고,
내장된 Command Default Mapping / Keyword Index 데이터와 결합하여
skill-catalog.md를 생성합니다.

매핑 데이터는 이 파일이 단일 소스(Single Source of Truth)입니다.
기존 command-skill-map.md는 폐기되었으며, 매핑 변경 시 이 파일의
COMMAND_DEFAULTS / KEYWORD_INDEX 상수를 수정하세요.

사용법:
  python3 .claude/scripts/sync/catalog_sync.py              # 카탈로그 생성/갱신
  python3 .claude/scripts/sync/catalog_sync.py --dry-run     # 미리보기 (파일 쓰기 없음)

종료 코드: 0 성공, 1 실패
"""

import os
import re
import sys

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import (
    C_BOLD,
    C_CYAN,
    C_DIM,
    C_GREEN,
    C_RED,
    C_RESET,
    C_YELLOW,
    resolve_project_root,
)

PROJECT_ROOT = resolve_project_root()
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".claude", "skills")
CATALOG_FILE = os.path.join(SKILLS_DIR, "skill-catalog.md")

# 제외 접두사: 워크플로우 전용 스킬
EXCLUDE_PREFIXES = ("workflow-agent-", "workflow-cc-")

# =============================================================================
# Command Default Mapping (단일 소스 — 기존 command-skill-map.md에서 통합)
# 매핑 변경 시 이 상수를 수정하세요.
# =============================================================================
COMMAND_DEFAULTS = [
    ("implement", "review-code-quality, workflow-system-verification", "코드 품질 검사(Generator-Critic 루프 포함), 완료 전 검증(점진적 검증 포함). 에셋 관리 키워드 감지 시 매니저 스킬 조건부 로드"),
    ("review", "review-requesting, review-code-quality", "리뷰 체크리스트 적용 + 정량적 품질 검사. 보안/아키텍처/프론트엔드/성능 키워드 감지 시 전문 리뷰 스킬 조건부 로드"),
    ("research", "research-general, research-integrated", "웹 조사(research-general) + 통합 조사(research-integrated). references/ 가이드로 교차 검증 및 출처 평가 지원. 키워드별 병렬/검증 스킬 자동 로드. 분석 키워드 감지 시 analyze-* 스킬 조건부 로드. 코드 탐색(research-deep)은 키워드 매핑으로 조건부 로드"),
    ("strategy", "design-strategy", "다중 워크플로우 전략 수립, 로드맵 생성"),
]

KEYWORD_INDEX = [
    ("구현, implement, 기능 추가, feature", "workflow-system-verification"),
    ("리팩토링, refactor, 리팩터, 코드 개선", "review-code-quality"),
    ("마이그레이션, migration, 스키마 변경, DB 변경", "review-code-quality, workflow-system-verification"),
    ("품질, quality, 코드 품질, code quality", "review-code-quality"),
    ("API, REST, GraphQL, 엔드포인트, endpoint", "review-code-quality"),
    ("PR, pull request", "workflow-system-report-output, devops-github"),
    ("다이어그램, diagram, UML", "design-mermaid-diagrams"),
    ("아키텍처, architecture, 설계, architect, 시스템 구조, 컴포넌트", "design-architect, design-mermaid-diagrams"),
    ("프론트엔드, frontend, UI", "design-frontend"),
    ("웹앱, webapp", "devops-webapp-testing"),
    ("docx, 문서, document, 워드", "document-office/docx"),
    ("pptx, 프레젠테이션, presentation, 슬라이드", "document-office/pptx"),
    ("xlsx, 스프레드시트, spreadsheet, 엑셀", "document-office/xlsx"),
    ("pdf, PDF", "document-office/pdf"),
    ("MCP, Model Context Protocol", "management-mcp"),
    ("3P, newsletter, status report, 뉴스레터", "document-internal-comms"),
    ("changelog, release notes, 릴리스 노트, 변경 이력", "workflow-system-report-output"),
    ("LWC, Lightning Web Component, Salesforce, 세일즈포스", "salesforce-lwc"),
    ("Apple, HIG, 애플, apple design", "design-apple"),
    ("GHA, GitHub Actions, CI, CI/CD, pipeline, 빌드 실패, workflow run", "debug-gha-analysis"),
    ("교차 검증, cross-validation, 출처 평가, source evaluation", "research-general, research-grounding"),
    ("심층 조사, deep research, 코드 탐색, 대규모 분석", "research-deep"),
    ("웹+코드 통합, integrated research, 통합 조사, 복합 조사", "research-integrated"),
    ("병렬 조사, parallel research, 종합 조사, 다중 에이전트", "research-parallel"),
    ("신뢰도 검증, 출처 검증, source verification, grounding", "research-grounding"),
    ("보안 리뷰, security review, OWASP 리뷰, 취약점 리뷰, 보안 감사", "review-security"),
    ("아키텍처 리뷰, architecture review, 설계 리뷰, 구조 리뷰, 계층 검증", "review-architecture"),
    ("프론트엔드 리뷰, frontend review, React 리뷰, UI 리뷰, 컴포넌트 리뷰", "review-frontend"),
    ("성능 리뷰, performance review, 쿼리 리뷰, DB 리뷰, N+1", "review-performance"),
    ("종합 리뷰, comprehensive review, 전체 리뷰, full review", "review-comprehensive"),
    ("리뷰 반영, review feedback, 피드백 구현, 리뷰 수정, 리뷰 대응", "review-feedback-handler"),
    ("PR 리뷰, pull request review, PR 검증, PR 체크", "review-pr-integration"),
    ("보안, security, OWASP, 취약점, 정적 분석, static analysis, CodeQL, Semgrep", "debug-static-analysis"),
    ("접근성, a11y, accessibility, WCAG", "design-web-guidelines"),
    ("디버깅, debugging, 버그, bug, 에러 추적, error tracking, 근본 원인", "debug-systematic"),
    ("React, Next.js, 리액트, react 성능, react performance", "framework-react-best-practices, framework-react"),
    ("FastAPI, fastapi, Python API, 파이썬 API", "framework-fastapi"),
    ("전략, strategy, 로드맵, roadmap, 마일스톤, milestone, 다중 워크플로우", "design-strategy"),
    ("디자인 패턴, design pattern, GoF, SOLID 패턴", "design-patterns"),
    ("RICE, 우선순위, 작업 분해, task decomposition, scope", "management-scope-decomposer"),
    ("명령어 관리, command manager, 명령어 등록", "management-command"),
    ("스킬 생성, skill create, 스킬 관리, skill manage", "management-skill"),
    ("스킬 검색, skill search, find skill, 스킬 설치, 스킬 통합, auto integrate", "management-skill-integrator"),
    ("에이전트 관리, agent manager, 에이전트 목록", "management-agent"),
    ("요구사항 분석, SRS, 코드베이스 분석, 코드 구조, 데이터베이스 분석, DB 분석, 데이터 분석, EDA", "analyze-* (키워드 판단)"),
    ("커버리지, coverage, diff coverage, 코드 커버리지, 테스트 커버리지", "testing-coverage"),
    ("PBT, property-based, 속성 기반 테스트, Hypothesis, fast-check", "testing-property-based"),
    ("런타임 검증, runtime validation, Zod, beartype, 스키마 검증, 계약 검증", "devops-runtime-contract"),
    ("뮤테이션, mutation testing, Stryker, mutmut, 테스트 품질", "testing-mutation"),
    ("테스트 설계, test design, 동치 분할, 경계값, 결정 테이블", "testing-design"),
]


def parse_frontmatter(filepath):
    """SKILL.md의 YAML frontmatter에서 name, description, disable-model-invocation을 파싱."""
    result = {"name": None, "description": None, "disable-model-invocation": False}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return None

    # frontmatter 추출 (--- ... ---)
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    fm_text = match.group(1)

    # name 파싱
    name_match = re.search(r'^name:\s*"?([^"\n]+)"?\s*$', fm_text, re.MULTILINE)
    if name_match:
        result["name"] = name_match.group(1).strip()

    # description 파싱 (따옴표 내 문자열)
    desc_match = re.search(r'^description:\s*"((?:[^"\\]|\\.)*)"', fm_text, re.MULTILINE)
    if desc_match:
        result["description"] = desc_match.group(1).strip()
    else:
        # 따옴표 없는 description
        desc_match2 = re.search(r'^description:\s*(.+)$', fm_text, re.MULTILINE)
        if desc_match2:
            result["description"] = desc_match2.group(1).strip()

    # disable-model-invocation 파싱
    dmi_match = re.search(r'^disable-model-invocation:\s*(true|false)', fm_text, re.MULTILINE)
    if dmi_match:
        result["disable-model-invocation"] = dmi_match.group(1).lower() == "true"

    # scope 파싱 (global 기본값)
    scope_match = re.search(r'^scope:\s*(\S+)', fm_text, re.MULTILINE)
    if scope_match:
        result["scope"] = scope_match.group(1).strip().lower()
    else:
        result["scope"] = "global"

    return result


def scan_skills():
    """모든 SKILL.md를 스캔하여 활성 스킬 목록을 전문화/프로젝트로 분류하여 반환."""
    global_skills = []
    project_skills = []
    excluded_count = 0

    if not os.path.isdir(SKILLS_DIR):
        print(f"{C_RED}[ERROR] skills 디렉터리가 존재하지 않습니다: {SKILLS_DIR}{C_RESET}", file=sys.stderr)
        sys.exit(1)

    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if not os.path.isdir(skill_dir):
            continue

        skill_file = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isfile(skill_file):
            continue

        fm = parse_frontmatter(skill_file)
        if fm is None:
            continue

        name = fm["name"] or entry

        # 제외 조건: disable-model-invocation: true 또는 워크플로우 접두사
        if fm["disable-model-invocation"]:
            excluded_count += 1
            continue

        if any(name.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            excluded_count += 1
            continue

        skill_entry = {
            "name": name,
            "description": fm["description"] or "(설명 없음)",
        }

        # scope에 따라 분류
        if fm.get("scope") == "project":
            project_skills.append(skill_entry)
        else:
            global_skills.append(skill_entry)

    return global_skills, project_skills, excluded_count


def build_command_default_mapping():
    """내장 COMMAND_DEFAULTS 상수에서 명령어별 기본 스킬 매핑 테이블을 생성."""
    lines = []
    lines.append("| 명령어 | 자동 로드 스킬 | 용도 |")
    lines.append("|--------|---------------|------|")
    for cmd, skills, desc in COMMAND_DEFAULTS:
        lines.append(f"| {cmd} | {skills} | {desc} |")
    return "\n".join(lines) + "\n"


def build_keyword_index():
    """내장 KEYWORD_INDEX 상수에서 키워드 기반 추가 스킬 로드 테이블을 생성."""
    lines = []
    lines.append("| 키워드 | 추가 로드 스킬 |")
    lines.append("|--------|---------------|")
    for keywords, skills in KEYWORD_INDEX:
        lines.append(f"| {keywords} | {skills} |")
    return "\n".join(lines) + "\n"


def generate_catalog(global_skills, project_skills, command_mapping, keyword_index):
    """skill-catalog.md 내용을 생성."""
    total = len(global_skills) + len(project_skills)
    lines = []

    lines.append("# Skill Catalog")
    lines.append("")
    lines.append("> 이 파일은 `catalog_sync.py`에 의해 자동 생성됩니다. 직접 편집하지 마세요.")
    lines.append(f"> 활성 스킬: {total}개 (전문화: {len(global_skills)}, 프로젝트: {len(project_skills)})")
    lines.append("")

    # Section 1: Command Default Mapping
    lines.append("## Command Default Mapping")
    lines.append("")
    lines.append(command_mapping.rstrip())
    lines.append("")

    # Section 2: Keyword Index
    lines.append("## Keyword Index")
    lines.append("")
    lines.append(keyword_index.rstrip())
    lines.append("")

    # Section 3: Skill Descriptions (전문화 스킬)
    lines.append("## Skill Descriptions")
    lines.append("")
    lines.append("| 스킬명 | description |")
    lines.append("|--------|-------------|")
    for skill in global_skills:
        # description 내 파이프 문자 이스케이프
        desc = skill["description"].replace("|", "\\|")
        lines.append(f"| {skill['name']} | {desc} |")
    lines.append("")

    # Section 4: Project Skills (프로젝트 스킬)
    lines.append("## Project Skills")
    lines.append("")
    if project_skills:
        lines.append("| 스킬명 | description |")
        lines.append("|--------|-------------|")
        for skill in project_skills:
            desc = skill["description"].replace("|", "\\|")
            lines.append(f"| {skill['name']} | {desc} |")
    else:
        lines.append("(프로젝트 스킬 없음)")
    lines.append("")

    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv

    # 스킬 스캔
    global_skills, project_skills, excluded_count = scan_skills()
    total = len(global_skills) + len(project_skills)

    # 매핑 테이블 생성 (내장 데이터에서)
    command_mapping = build_command_default_mapping()
    keyword_index = build_keyword_index()

    # 카탈로그 생성
    catalog_content = generate_catalog(global_skills, project_skills, command_mapping, keyword_index)
    catalog_size = len(catalog_content.encode("utf-8"))

    if dry_run:
        print(f"{C_CYAN}[DRY-RUN]{C_RESET} 스킬 카탈로그 미리보기")
        print(f"  활성 스킬: {C_BOLD}{total}{C_RESET}개 (전문화: {len(global_skills)}, 프로젝트: {len(project_skills)})")
        print(f"  제외 스킬: {C_DIM}{excluded_count}{C_RESET}개")
        print(f"  예상 크기: {C_BOLD}{catalog_size:,}{C_RESET} bytes")
        print(f"  대상 파일: {C_DIM}{CATALOG_FILE}{C_RESET}")
        print()
        print(f"  {C_DIM}실제 생성하려면: python3 .claude/scripts/sync/catalog_sync.py{C_RESET}")
        print(flush=True)
        sys.exit(0)

    # 파일 쓰기
    try:
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            f.write(catalog_content)

        actual_size = os.path.getsize(CATALOG_FILE)
        print(f"{C_GREEN}[OK]{C_RESET} 스킬 카탈로그 생성 완료")
        print(f"  활성 스킬: {C_BOLD}{total}{C_RESET}개 (전문화: {len(global_skills)}, 프로젝트: {len(project_skills)})")
        print(f"  제외 스킬: {C_DIM}{excluded_count}{C_RESET}개")
        print(f"  파일 크기: {C_BOLD}{actual_size:,}{C_RESET} bytes")
        print(f"  저장 위치: {C_DIM}{CATALOG_FILE}{C_RESET}")
        print(flush=True)
    except (IOError, OSError) as e:
        print(f"{C_RED}[ERROR] 카탈로그 파일 쓰기 실패: {e}{C_RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
