"""Memory GC 패키지 — 자동 메모리 갱신·정리.

3축 점수(recency·importance·access) + Hot/Warm/Cold 계층 + Reflection 합성.
모든 자동 작업은 reversible (archive 보관). 영구 삭제는 prune-archive 로 명시.
"""
