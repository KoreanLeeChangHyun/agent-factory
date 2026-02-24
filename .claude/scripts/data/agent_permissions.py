"""
agent_permissions.py - 워크플로우 모드별 Phase-에이전트 권한 매핑

워크플로우 모드(full, strategy, noplan)별로 각 Phase에서 허용되는 에이전트 목록을 정의합니다.
workflow_agent_guard에서 현재 Phase와 에이전트 조합의 유효성을 검증하는 데 사용됩니다.
이 모듈은 순수 상수만 정의하며, 다른 모듈을 import하지 않는 leaf 모듈입니다.

카테고리:
    에이전트 권한 매핑  - AGENT_PERMISSIONS (5개 모드)
"""

# =============================================================================
# 워크플로우 모드별 Phase-에이전트 권한 매핑
# =============================================================================
AGENT_PERMISSIONS = {
    "full": {  # 전체 워크플로우 모드
        "NONE": ["init"],
        "INIT": ["planner"],
        "PLAN": ["planner", "worker"],
        "WORK": ["worker", "explorer", "reporter"],
        "REPORT": ["reporter", "done"],
        "COMPLETED": ["done"],
        "FAILED": [],
        "STALE": [],
        "CANCELLED": [],
    },
    "strategy": {  # 전략 전용 모드
        "NONE": ["init"],
        "INIT": [],
        "STRATEGY": ["strategy", "done"],
        "COMPLETED": ["done"],
        "FAILED": [],
        "STALE": [],
        "CANCELLED": [],
    },
    "noplan": {  # 계획 생략 모드
        "NONE": ["init"],
        "INIT": ["worker", "explorer"],
        "WORK": ["worker", "explorer", "reporter"],
        "REPORT": ["reporter", "done"],
        "COMPLETED": ["done"],
        "FAILED": [],
        "STALE": [],
        "CANCELLED": [],
    },
    "noreport": {  # 보고서 생략 모드
        "NONE": ["init"],
        "INIT": ["planner"],
        "PLAN": ["planner", "worker"],
        "WORK": ["worker", "explorer", "done"],
        "COMPLETED": ["done"],
        "FAILED": [],
        "STALE": [],
        "CANCELLED": [],
    },
    "noplan+noreport": {  # 계획+보고서 생략 모드
        "NONE": ["init"],
        "INIT": ["worker", "explorer"],
        "WORK": ["worker", "explorer", "done"],
        "COMPLETED": ["done"],
        "FAILED": [],
        "STALE": [],
        "CANCELLED": [],
    },
}
