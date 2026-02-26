"""
agent_permissions.py - 워크플로우 모드별 Phase-에이전트 권한 매핑

워크플로우 모드(full, strategy, noplan, noreport, noplan+noreport)별로
각 Phase에서 허용되는 에이전트 목록을 정의합니다.
workflow_agent_guard에서 현재 Phase와 에이전트 조합의 유효성을 검증하는 데 사용됩니다.
이 모듈은 순수 상수만 정의하며, 다른 모듈을 import하지 않는 leaf 모듈입니다.

카테고리:
    에이전트 권한 매핑  - AGENT_PERMISSIONS (5개 모드)

매핑 근거 (참조 문서):
    - SKILL.md "Agent-Phase Mapping" 테이블: Phase별 전담 에이전트 정의
    - step-work.md "WORK Phase Rules": WORK Phase 허용 에이전트
      → indexer, worker, explorer, validator, reporter (5종)
    - step-init.md "Mode Branching": 모드별 Phase 흐름 및 에이전트 호출 패턴

    모드별 Phase 흐름:
      full:             NONE→INIT→PLAN→WORK→REPORT→DONE
      strategy:         NONE→INIT→STRATEGY→DONE
      noplan:           NONE→INIT→WORK→REPORT→DONE
      noreport:         NONE→INIT→PLAN→WORK→DONE (REPORT 스킵)
      noplan+noreport:  NONE→INIT→WORK→DONE (PLAN+REPORT 스킵)

    에이전트-Phase 대응:
      init:      NONE Phase에서 호출 (workflow_agent_guard에서 항상 통과, Phase 검증 제외)
      planner:   INIT→PLAN 전이 후 PLAN Phase에서 호출 (full/noreport 모드)
      indexer:   WORK Phase 0에서 호출 (스킬 탐색/매핑 준비)
      worker:    WORK Phase 1+에서 호출 (계획서 태스크 실행)
      explorer:  WORK Phase 1+에서 호출 (탐색 전용 태스크)
      validator: WORK Phase N+1에서 호출 (린트/타입체크/빌드 검증)
      reporter:  REPORT Phase에서 호출 (최종 보고서 작성)
      strategy:  STRATEGY Phase에서 호출 (strategy 모드 전용)
      done:      DONE Phase에서 호출 (마무리 처리)
"""

# =============================================================================
# 워크플로우 모드별 Phase-에이전트 권한 매핑
# =============================================================================
AGENT_PERMISSIONS = {
    "full": {  # 전체 워크플로우 모드
        "NONE": ["init"],
        "INIT": ["planner"],
        "PLAN": ["planner", "worker"],
        "WORK": ["indexer", "worker", "explorer", "validator", "reporter"],
        "REPORT": ["reporter", "done"],
        "DONE": ["done"],
        "FAILED": [],
        "STALE": [],
        "CANCELLED": [],
    },
    "strategy": {  # 전략 전용 모드
        "NONE": ["init"],
        "INIT": ["init"],
        "STRATEGY": ["strategy", "done"],
        "DONE": ["done"],
        "FAILED": [],
        "STALE": [],
        "CANCELLED": [],
    },
    "noplan": {  # 계획 생략 모드
        "NONE": ["init"],
        "INIT": ["indexer", "worker", "explorer"],
        "WORK": ["indexer", "worker", "explorer", "validator", "reporter"],
        "REPORT": ["reporter", "done"],
        "DONE": ["done"],
        "FAILED": [],
        "STALE": [],
        "CANCELLED": [],
    },
    "noreport": {  # 보고서 생략 모드 (WORK→DONE, REPORT 스킵)
        "NONE": ["init"],
        "INIT": ["planner"],
        "PLAN": ["planner", "worker"],
        "WORK": ["indexer", "worker", "explorer", "validator", "reporter"],
        "DONE": ["done"],
        "FAILED": [],
        "STALE": [],
        "CANCELLED": [],
    },
    "noplan+noreport": {  # 계획+보고서 생략 모드 (INIT→WORK→DONE, PLAN+REPORT 스킵)
        "NONE": ["init"],
        "INIT": ["indexer", "worker", "explorer"],
        "WORK": ["indexer", "worker", "explorer", "validator", "reporter"],
        "DONE": ["done"],
        "FAILED": [],
        "STALE": [],
        "CANCELLED": [],
    },
}
