"""Workflow hook handlers.

PreToolUse/PostToolUse/SessionStart 이벤트에서 워크플로우 결정론 단계
(flow-update both, flow-step start, flow-phase, flow-skillmap, flow-update
task-start, flow-update task-status, flow-validate)를 자동 흡수한다.

오케스트레이터(메인 세션)는 Task(planner/worker-*/explorer-*/validator/
reporter) 호출 + INIT (cd "$(flow-init ... | tail -1)") + DONE
(flow-update status DONE + flow-finish + flow-claude end) 만 명시 호출하면
된다. 그 사이의 모든 결정론 wrapper 호출은 본 hook 군이 흡수한다.

활성 토글: .claude-organic/.settings 의 HOOK_WORKFLOW_ORCHESTRATION=true.
"""
