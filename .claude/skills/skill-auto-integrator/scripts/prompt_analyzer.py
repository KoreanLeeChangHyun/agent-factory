"""Prompt Analyzer Module.

Extracts search keywords, domain, and task type from natural language prompts.
Supports both Korean and English bilingual keyword extraction using pure Python
(no spaCy or external NLP dependencies).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SearchQuery:
    """Structured search query extracted from a natural language prompt."""

    keywords: list[str] = field(default_factory=list)
    domain: str = ""
    task_type: str = ""


# ---------------------------------------------------------------------------
# Stop-word lists (lightweight, curated for skill-search context)
# ---------------------------------------------------------------------------

_ENGLISH_STOPWORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could",
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing",
    "a", "an", "the", "and", "but", "if", "or", "because", "as",
    "until", "while", "of", "at", "by", "for", "with", "about",
    "against", "between", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "in", "out",
    "on", "off", "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "just", "don", "now",
    # Common verbs in skill-search context (less informative)
    "find", "get", "make", "use", "want", "need", "look", "like",
    "help", "please", "give", "tell", "show",
}

_KOREAN_STOPWORDS: set[str] = {
    "은", "는", "이", "가", "을", "를", "의", "에", "에서", "와", "과",
    "도", "로", "으로", "라", "이라", "고", "며", "면", "서", "지",
    "그", "저", "것", "등", "수", "때", "중", "좀", "잘", "더",
    "많이", "아주", "너무", "정말", "매우", "약간", "조금",
    "하다", "되다", "있다", "없다", "않다", "같다",
    "해주세요", "해줘", "주세요", "합니다", "입니다", "있는",
    "하는", "위한", "대한", "통한", "관한",
}

# ---------------------------------------------------------------------------
# Domain detection patterns
# ---------------------------------------------------------------------------

_DOMAIN_PATTERNS: list[tuple[str, list[str]]] = [
    ("web-frontend", [
        r"\b(?:react|vue|angular|svelte|next\.?js|nuxt|frontend|프론트엔드|UI|UX)\b",
    ]),
    ("web-backend", [
        r"\b(?:fastapi|django|flask|express|nest\.?js|spring|백엔드|backend|API|REST|GraphQL)\b",
    ]),
    ("devops", [
        r"\b(?:docker|kubernetes|k8s|CI/?CD|terraform|ansible|devops|배포|deploy|인프라)\b",
    ]),
    ("data", [
        r"\b(?:pandas|numpy|데이터|data\s*(?:science|analysis|pipeline)|ETL|ML|머신러닝|AI|딥러닝)\b",
    ]),
    ("mobile", [
        r"\b(?:react\s*native|flutter|swift|kotlin|iOS|android|모바일|앱\s*개발)\b",
    ]),
    ("security", [
        r"\b(?:보안|security|OWASP|취약점|vulnerability|인증|authentication|암호화|encryption)\b",
    ]),
    ("testing", [
        r"\b(?:테스트|test(?:ing)?|TDD|BDD|QA|품질|quality|커버리지|coverage)\b",
    ]),
    ("documentation", [
        r"\b(?:문서|document(?:ation)?|README|가이드|guide|튜토리얼|tutorial)\b",
    ]),
]

# ---------------------------------------------------------------------------
# Task-type detection patterns
# ---------------------------------------------------------------------------

_TASK_TYPE_PATTERNS: list[tuple[str, list[str]]] = [
    ("search", [
        r"\b(?:찾|검색|search|find|discover|look\s*for|탐색)\b",
    ]),
    ("install", [
        r"\b(?:설치|install|setup|셋업|세팅|통합|integrate|추가|add)\b",
    ]),
    ("create", [
        r"\b(?:만들|생성|create|build|구현|implement|개발|develop)\b",
    ]),
    ("convert", [
        r"\b(?:변환|convert|transform|마이그레이션|migration|포맷)\b",
    ]),
    ("analyze", [
        r"\b(?:분석|analyze|review|검토|평가|evaluate|비교|compare)\b",
    ]),
    ("optimize", [
        r"\b(?:최적화|optimize|개선|improve|리팩토링|refactor|성능|performance)\b",
    ]),
]


class PromptAnalyzer:
    """Analyzes natural language prompts to extract structured search queries.

    Extracts keywords (Korean and English), detects the domain context,
    and identifies the task type from a free-form user prompt.  All processing
    uses pure Python regex -- no external NLP libraries required.
    """

    def __init__(self) -> None:
        self._en_stopwords = _ENGLISH_STOPWORDS
        self._ko_stopwords = _KOREAN_STOPWORDS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, prompt: str) -> SearchQuery:
        """Analyze *prompt* and return a :class:`SearchQuery`.

        Parameters
        ----------
        prompt:
            Free-form natural language text (Korean, English, or mixed).

        Returns
        -------
        SearchQuery
            Extracted keywords, detected domain, and task type.
        """
        if not prompt or not prompt.strip():
            return SearchQuery()

        keywords = self._extract_keywords(prompt)
        domain = self._detect_domain(prompt)
        task_type = self._detect_task_type(prompt)

        return SearchQuery(
            keywords=keywords,
            domain=domain,
            task_type=task_type,
        )

    # ------------------------------------------------------------------
    # Keyword extraction (bilingual)
    # ------------------------------------------------------------------

    def _extract_keywords(self, prompt: str) -> list[str]:
        """Extract meaningful keywords from *prompt*.

        Combines English noun-phrase extraction and Korean noun-pattern
        extraction, then filters through stop-word lists and deduplicates.
        """
        en_keywords = self._extract_english_keywords(prompt)
        ko_keywords = self._extract_korean_keywords(prompt)

        # Merge, deduplicate (case-insensitive for English), preserve order
        seen: set[str] = set()
        merged: list[str] = []
        for kw in en_keywords + ko_keywords:
            key = kw.lower()
            if key not in seen:
                seen.add(key)
                merged.append(kw)

        return merged

    def _extract_english_keywords(self, prompt: str) -> list[str]:
        """Extract English noun phrases and technical terms."""
        keywords: list[str] = []

        # 1. Quoted phrases (highest priority -- user explicitly marked them)
        for match in re.finditer(r'["\']([^"\']+)["\']', prompt):
            phrase = match.group(1).strip()
            if phrase:
                keywords.append(phrase)

        # 2. Compound technical terms (e.g. "code-quality", "skill-auto")
        for match in re.finditer(r"\b[a-zA-Z]+(?:-[a-zA-Z]+)+\b", prompt):
            term = match.group(0)
            if term.lower() not in self._en_stopwords:
                keywords.append(term)

        # 3. CamelCase / PascalCase identifiers
        for match in re.finditer(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", prompt):
            keywords.append(match.group(0))

        # 4. Uppercase acronyms (API, REST, TDD, ...)
        for match in re.finditer(r"\b[A-Z]{2,}\b", prompt):
            term = match.group(0)
            if term not in self._en_stopwords:
                keywords.append(term)

        # 5. General English words (lowercased, stop-word filtered)
        for match in re.finditer(r"\b[a-zA-Z]{2,}\b", prompt):
            word = match.group(0)
            if word.lower() not in self._en_stopwords and word not in keywords:
                keywords.append(word)

        return keywords

    def _extract_korean_keywords(self, prompt: str) -> list[str]:
        """Extract Korean noun-like tokens using suffix patterns.

        Korean nouns often end with characteristic suffixes.  We use these
        patterns to identify likely noun tokens without a morphological
        analyzer.
        """
        keywords: list[str] = []

        # Korean noun-suffix patterns (e.g. -기, -화, -성, -스킬, -도구, ...)
        ko_noun_suffixes = (
            r"[\uAC00-\uD7A3]*(?:스킬|도구|모듈|시스템|서버|서비스|패키지|"
            r"프레임워크|라이브러리|플러그인|컴포넌트|엔진|매니저|"
            r"분석기|생성기|변환기|검증기|탐색기|"
            r"자동화|최적화|시각화|정규화|직렬화|"
            r"관리|설치|검색|통합|변환|검증|분석|생성|배포|"
            r"테스트|리뷰|빌드|디버깅|리팩토링|"
            r"기능|품질|보안|성능|접근성)"
        )
        for match in re.finditer(ko_noun_suffixes, prompt):
            token = match.group(0).strip()
            if token and token not in self._ko_stopwords and len(token) >= 2:
                keywords.append(token)

        # Longer Korean noun phrases (2+ syllable blocks separated by spaces
        # are often meaningful compound nouns)
        ko_compound = r"([\uAC00-\uD7A3]{2,})\s+([\uAC00-\uD7A3]{2,})"
        for match in re.finditer(ko_compound, prompt):
            part1 = self._strip_korean_particles(match.group(1))
            part2 = self._strip_korean_particles(match.group(2))
            if (
                part1 not in self._ko_stopwords
                and part2 not in self._ko_stopwords
                and len(part1) >= 2
                and len(part2) >= 2
            ):
                compound = f"{part1} {part2}"
                if compound not in keywords:
                    keywords.append(compound)

        return keywords

    @staticmethod
    def _strip_korean_particles(word: str) -> str:
        """Strip common Korean particles/suffixes from the end of *word*.

        Korean particles like 을/를/이/가/은/는/에/에서/으로 are commonly
        attached to the end of nouns.  Removing them yields cleaner keywords.
        """
        # Ordered longest-first to avoid partial stripping
        particles = (
            "에서", "으로", "이라", "에게",
            "을", "를", "이", "가", "은", "는", "의",
            "에", "로", "와", "과", "도", "고",
        )
        for p in particles:
            if word.endswith(p) and len(word) > len(p) + 1:
                return word[: -len(p)]
        return word

    # ------------------------------------------------------------------
    # Domain detection
    # ------------------------------------------------------------------

    def _detect_domain(self, prompt: str) -> str:
        """Detect the primary domain from *prompt*.

        Returns the first matching domain or ``"general"`` if none match.
        """
        prompt_lower = prompt.lower()
        best_domain = "general"
        best_count = 0

        for domain, patterns in _DOMAIN_PATTERNS:
            count = 0
            for pat in patterns:
                count += len(re.findall(pat, prompt_lower, re.IGNORECASE))
            if count > best_count:
                best_count = count
                best_domain = domain

        return best_domain

    def _detect_task_type(self, prompt: str) -> str:
        """Detect the intended task type from *prompt*.

        Returns the first matching task type or ``"search"`` as the default
        (since the primary use case is skill discovery).
        """
        prompt_lower = prompt.lower()
        best_type = "search"
        best_count = 0

        for task_type, patterns in _TASK_TYPE_PATTERNS:
            count = 0
            for pat in patterns:
                count += len(re.findall(pat, prompt_lower, re.IGNORECASE))
            if count > best_count:
                best_count = count
                best_type = task_type

        return best_type
