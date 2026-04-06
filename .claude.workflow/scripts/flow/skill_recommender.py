#!/usr/bin/env -S python3 -u
"""skill_recommender.py - TF-IDF 기반 스킬 자동 추천 스크립트.

skill-catalog.md의 Skill Descriptions 섹션에서 각 스킬의 Triggers 키워드를
파싱하여 인메모리 인덱스를 구축한 후, 입력 태스크 description과 TF-IDF 유사도를
계산하여 상위 3개 스킬을 추천한다.

사용법:
  python3 skill_recommender.py <task_description...>
  python3 skill_recommender.py --help

출력:
  추천 스킬 3개 (이름 + 유사도 점수)

외부 라이브러리 미사용 (순수 Python 구현)
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys

# 프로젝트 루트 결정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import resolve_project_root
from flow.cli_utils import build_common_epilog
from flow.flow_logger import append_log, resolve_work_dir_for_logging

PROJECT_ROOT = resolve_project_root()
CATALOG_FILE = os.path.join(PROJECT_ROOT, ".claude", "skills", "skill-catalog.md")

TOP_K = 3


def parse_skill_descriptions(catalog_path: str) -> dict[str, dict[str, list[str]]]:
    """skill-catalog.md의 Skill Descriptions 섹션에서 스킬별 Triggers 키워드를 파싱한다.

    Args:
        catalog_path: skill-catalog.md 파일의 절대 경로

    Returns:
        스킬 이름을 키로, 트리거/설명 단어 정보를 값으로 하는 딕셔너리.
        각 값은 다음 키를 포함한다:
        - triggers (list[str]): Triggers 키워드 목록 (소문자)
        - desc_words (list[str]): 설명 텍스트 토큰 목록
        - all_terms (list[str]): triggers + desc_words 합산 목록
    """
    if not os.path.isfile(catalog_path):
        print(f"[ERROR] skill-catalog.md를 찾을 수 없습니다: {catalog_path}", file=sys.stderr)
        return {}

    with open(catalog_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    skills: dict[str, dict[str, list[str]]] = {}
    in_section = False

    for line in lines:
        if "## Skill Descriptions" in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        if not line.startswith("|"):
            continue
        # 헤더/구분선 스킵
        if line.startswith("| 스킬명") or re.match(r"^\|\s*[-:]+", line):
            continue

        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p != ""]
        if len(parts) < 2:
            continue

        skill_name = parts[0].strip()
        description = parts[1].strip()

        if not skill_name:
            continue

        # Triggers 키워드 추출
        triggers: list[str] = []
        triggers_match = re.search(r"Triggers:\s*(.+?)\.?\s*$", description)
        if triggers_match:
            raw_triggers = triggers_match.group(1)
            # 따옴표로 감싸진 키워드들을 추출
            quoted = re.findall(r"'([^']+)'", raw_triggers)
            if quoted:
                triggers = [t.strip().lower() for t in quoted if t.strip()]

        # description 전체에서도 키워드 추출 (Triggers 이전 부분)
        desc_before_triggers = description
        if triggers_match:
            desc_before_triggers = description[:triggers_match.start()]

        # description 단어들도 인덱스에 포함
        desc_words = tokenize(desc_before_triggers)

        skills[skill_name] = {
            "triggers": triggers,
            "desc_words": desc_words,
            "all_terms": triggers + desc_words,
        }

    return skills


def tokenize(text: str) -> list[str]:
    """텍스트를 소문자 토큰 리스트로 분할한다. 한글/영문 혼합 지원.

    Args:
        text: 분할할 텍스트 문자열

    Returns:
        소문자 영문 단어와 2글자 이상 한글 단어를 합산한 토큰 목록.
    """
    text = text.lower()
    # 영문 단어 추출
    en_words = re.findall(r"[a-z][a-z0-9_-]*[a-z0-9]|[a-z]", text)
    # 한글 단어 추출 (2글자 이상)
    ko_words = re.findall(r"[가-힣]{2,}", text)
    return en_words + ko_words


def build_tfidf_index(
    skills: dict[str, dict[str, list[str]]],
) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    """스킬별 Triggers + description 단어를 기반으로 TF-IDF 인덱스를 구축한다.

    Args:
        skills: parse_skill_descriptions()의 반환값

    Returns:
        2-튜플 (tfidf_index, idf):
        - tfidf_index: {skill_name: {term: tfidf_score}}
        - idf: {term: idf_score}
    """
    num_docs = len(skills)
    if num_docs == 0:
        return {}, {}

    # Document Frequency 계산
    df: dict[str, int] = {}
    for skill_name, info in skills.items():
        unique_terms = set(info["all_terms"])
        for term in unique_terms:
            df[term] = df.get(term, 0) + 1

    # IDF 계산: log(N / df) + 1 (smoothing)
    idf: dict[str, float] = {}
    for term, freq in df.items():
        idf[term] = math.log(num_docs / freq) + 1.0

    # TF-IDF 계산
    tfidf_index: dict[str, dict[str, float]] = {}
    for skill_name, info in skills.items():
        terms = info["all_terms"]
        if not terms:
            tfidf_index[skill_name] = {}
            continue

        # TF 계산 (빈도수 / 총 단어 수)
        tf: dict[str, int] = {}
        for term in terms:
            tf[term] = tf.get(term, 0) + 1
        total = len(terms)

        # Trigger 키워드에 가중치 부여 (x2)
        trigger_set = set(info["triggers"])
        tfidf: dict[str, float] = {}
        for term, count in tf.items():
            base_tf = count / total
            # Trigger에 포함된 키워드는 가중치 2배
            weight = 2.0 if term in trigger_set else 1.0
            tfidf[term] = base_tf * idf.get(term, 1.0) * weight

        # 정규화 (L2 norm)
        norm = math.sqrt(sum(v * v for v in tfidf.values()))
        if norm > 0:
            tfidf = {k: v / norm for k, v in tfidf.items()}

        tfidf_index[skill_name] = tfidf

    return tfidf_index, idf


def compute_query_tfidf(query_text: str, idf: dict[str, float]) -> dict[str, float]:
    """쿼리 텍스트의 TF-IDF 벡터를 계산한다.

    Args:
        query_text: TF-IDF 벡터로 변환할 쿼리 문자열
        idf: build_tfidf_index()에서 생성된 IDF 점수 딕셔너리

    Returns:
        L2 정규화된 TF-IDF 벡터 {term: score}.
        토큰이 없으면 빈 딕셔너리.
    """
    tokens = tokenize(query_text)
    if not tokens:
        return {}

    # TF 계산
    tf: dict[str, int] = {}
    for token in tokens:
        tf[token] = tf.get(token, 0) + 1
    total = len(tokens)

    # TF-IDF 계산
    tfidf: dict[str, float] = {}
    for term, count in tf.items():
        tfidf[term] = (count / total) * idf.get(term, 1.0)

    # L2 정규화
    norm = math.sqrt(sum(v * v for v in tfidf.values()))
    if norm > 0:
        tfidf = {k: v / norm for k, v in tfidf.items()}

    return tfidf


def cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """두 TF-IDF 벡터의 코사인 유사도를 계산한다.

    Args:
        vec_a: 첫 번째 TF-IDF 벡터 {term: score}
        vec_b: 두 번째 TF-IDF 벡터 {term: score}

    Returns:
        0.0~1.0 범위의 코사인 유사도. 공통 term이 없으면 0.0.
    """
    common_terms = set(vec_a.keys()) & set(vec_b.keys())
    if not common_terms:
        return 0.0

    dot_product = sum(vec_a[t] * vec_b[t] for t in common_terms)
    return dot_product


def keyword_match_boost(query_text: str, skill_info: dict[str, list[str]]) -> float:
    """Trigger 키워드가 쿼리에 직접 포함된 경우 추가 점수를 부여한다.

    정확한 키워드 매칭은 TF-IDF보다 강력한 신호이므로 보너스를 준다.

    Args:
        query_text: 검사할 쿼리 텍스트
        skill_info: parse_skill_descriptions()의 스킬 정보 딕셔너리

    Returns:
        추가 점수 (0.0~0.9). 매칭된 trigger당 0.3, 최대 0.9.
    """
    query_lower = query_text.lower()
    boost = 0.0
    for trigger in skill_info["triggers"]:
        if trigger in query_lower:
            boost += 0.3  # 매칭된 trigger당 0.3 보너스
    # 부동소수점 누적 오차 해소
    return round(min(boost, 0.9), 10)  # 최대 0.9 (3개 trigger까지)


def recommend(query_text: str, catalog_path: str | None = None) -> list[tuple[str, float]]:
    """태스크 description을 받아 상위 K개 스킬을 추천한다.

    Args:
        query_text: 태스크 설명 문자열
        catalog_path: skill-catalog.md 경로 (None이면 기본값 CATALOG_FILE 사용)

    Returns:
        [(skill_name, score), ...] 형식의 상위 K개 추천 목록.
        점수가 0보다 큰 항목만 포함. 추천 불가능하면 빈 리스트.
    """
    if catalog_path is None:
        catalog_path = CATALOG_FILE

    skills = parse_skill_descriptions(catalog_path)
    if not skills:
        return []

    tfidf_index, idf = build_tfidf_index(skills)
    query_vec = compute_query_tfidf(query_text, idf)

    if not query_vec:
        return []

    scores: list[tuple[str, float]] = []
    for skill_name, skill_vec in tfidf_index.items():
        sim = cosine_similarity(query_vec, skill_vec)
        boost = keyword_match_boost(query_text, skills[skill_name])
        final_score = sim + boost
        scores.append((skill_name, final_score))

    # 점수 내림차순 정렬
    scores.sort(key=lambda x: x[1], reverse=True)

    # 상위 K개 (점수 > 0인 것만)
    return [(name, score) for name, score in scores[:TOP_K] if score > 0]


def build_parser() -> argparse.ArgumentParser:
    """argparse 파서를 생성하여 반환한다.

    Returns:
        설정된 ArgumentParser 인스턴스.
    """
    parser = argparse.ArgumentParser(
        prog="flow-recommend",
        description=(
            "TF-IDF 기반 스킬 자동 추천.\n"
            "skill-catalog.md의 Skill Descriptions 섹션에서 각 스킬의\n"
            "Triggers 키워드를 파싱하여 인메모리 인덱스를 구축한 후,\n"
            "입력 태스크 description과 TF-IDF 유사도를 계산하여\n"
            f"상위 {TOP_K}개 스킬을 추천합니다."
        ),
        epilog=(
            "예시:\n"
            '  flow-recommend 보안 리뷰 및 OWASP 취약점 분석\n'
            '  flow-recommend React 컴포넌트 성능 최적화\n'
            '  flow-recommend GitHub Actions CI 빌드 실패 디버깅\n'
            "\n"
            + build_common_epilog()
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "task_description",
        nargs="+",
        metavar="WORD",
        help="태스크 설명 (공백 구분 단어들을 하나의 쿼리로 합산)",
    )
    return parser


def main() -> None:
    """CLI 진입점. task_description을 받아 추천 스킬을 출력한다.

    Raises:
        SystemExit: 추천 결과 없음(0), 정상 완료(0), 인자 오류(2).
    """
    parser = build_parser()
    args = parser.parse_args()

    query = " ".join(args.task_description)

    _work_dir = resolve_work_dir_for_logging()
    if _work_dir:
        append_log(_work_dir, "INFO", f"skill_recommender: query={query[:50]}")

    results = recommend(query)

    if not results:
        print("║ STATE: RECOMMEND", flush=True)
        print("║ >> 추천 가능한 스킬이 없습니다.", flush=True)
        sys.exit(0)

    top_name, top_score = results[0]
    print("║ STATE: RECOMMEND", flush=True)
    print(f"║ >> {top_name} (유사도: {top_score:.4f})", flush=True)
    print(f"태스크: {query}")
    print(f"추천 스킬 (상위 {TOP_K}개):")
    print()
    for i, (name, score) in enumerate(results, 1):
        print(f"  {i}. {name} (유사도: {score:.4f})")


if __name__ == "__main__":
    main()
