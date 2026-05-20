"""사용자 가시성 정책 단일 헬퍼.

SSE 라이브 broadcast 와 REST history replay 양쪽에서 동일하게 적용해야 하는
사용자 가시성 규칙을 한 곳에서 관리한다. 이벤트가 사용자 UI 채널로 노출되는
모든 지점은 반드시 이 헬퍼를 호출해야 한다.

신규 데이터 경로 추가 시 이 헬퍼 미호출은 코드리뷰 단계에서 식별하여 회귀를
구조적으로 차단한다.
"""

from __future__ import annotations


def is_user_visible(data: dict) -> bool:
    """사용자 UI 에 노출 가능한 이벤트인지 판정한다.

    isMeta=True 는 Claude Code 하네스가 주입하는 Skill/command 래퍼 user 메시지로,
    실제 사용자 입력/tool_result 에는 없는 필드이다. 사용자 채널 노출에서 제외한다.

    Args:
        data: 원본 NDJSON 이벤트 dict

    Returns:
        True 면 사용자 UI 노출 허용, False 면 제외해야 한다.
    """
    if data.get('isMeta') is True:
        return False
    return True
