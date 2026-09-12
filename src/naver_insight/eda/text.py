"""한국어 텍스트 처리 — 형태소 기반 명사 추출, n-gram, 동시출현.

`kiwipiepy` 가 설치돼 있으면 형태소 분석기로 명사를 뽑고(배치 처리),
없으면 정규식 토크나이저로 폴백한다.

성능: 명사 추출은 수집 파이프라인에서 1회만 수행하고, 결과를 공백으로 join 한
`noun_str` 컬럼으로 저장한다. 이후 집계 함수들은 문자열을 split 해서 쓴다
(리스트 컬럼을 두면 DataFrame 해싱/캐시가 느려지므로).
"""

from __future__ import annotations

import html
import re
from collections import Counter
from functools import lru_cache
from itertools import combinations

import pandas as pd

_TOKEN_RE = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9]{1,}")
_TAG_RE = re.compile(r"<[^>]+>")

STOPWORDS: set[str] = {
    "그리고", "하지만", "그러나", "그래서", "때문", "위해", "관련", "대한", "이번",
    "우리", "제가", "정말", "너무", "많이", "하는", "있는", "없는", "되는", "이다",
    "합니다", "했다", "한다", "그것", "저것", "여기", "저기", "지금", "오늘", "경우",
    "사람", "생각", "정도", "부분", "때문에", "통해", "다양", "여러", "모든", "각각",
    "the", "and", "for", "you", "with", "this", "that", "was", "are", "http", "https",
    "com", "www", "net", "blog", "kr", "co",
}


def clean(value) -> str:
    """HTML 태그 제거 + 공백 정리."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return html.unescape(_TAG_RE.sub(" ", str(value))).strip()


def _keep(word: str) -> bool:
    w = word.lower()
    return not (w in STOPWORDS or w.isdigit())


class _RegexTagger:
    backend = "regex"

    def nouns(self, text: str) -> list[str]:
        return [t for t in _TOKEN_RE.findall(clean(text)) if _keep(t)]

    def nouns_batch(self, texts: list[str]) -> list[list[str]]:
        return [self.nouns(t) for t in texts]


class _KiwiTagger:
    backend = "kiwi"
    _KEEP_TAGS = ("NNG", "NNP", "SL")

    def __init__(self) -> None:
        from kiwipiepy import Kiwi  # noqa: PLC0415

        self._kiwi = Kiwi()

    def _from_tokens(self, tokens) -> list[str]:
        return [
            t.form for t in tokens
            if t.tag in self._KEEP_TAGS and len(t.form) >= 2 and _keep(t.form)
        ]

    def nouns(self, text: str) -> list[str]:
        return self._from_tokens(self._kiwi.tokenize(clean(text)))

    def nouns_batch(self, texts: list[str]) -> list[list[str]]:
        cleaned = [clean(t) for t in texts]
        # kiwipiepy 는 iterable 입력 시 배치(멀티스레드)로 처리한다.
        return [self._from_tokens(toks) for toks in self._kiwi.tokenize(cleaned)]


@lru_cache(maxsize=1)
def get_tagger():
    try:
        return _KiwiTagger()
    except Exception:  # noqa: BLE001
        return _RegexTagger()


def noun_str_series(texts: pd.Series) -> pd.Series:
    """문자열 Series -> 각 행의 명사를 공백으로 join 한 문자열 Series."""
    tagger = get_tagger()
    lists = tagger.nouns_batch(list(texts.fillna("").astype(str)))
    return pd.Series([" ".join(ws) for ws in lists], index=texts.index)


def _as_lists(noun_col: pd.Series) -> list[list[str]]:
    return [s.split() if isinstance(s, str) else [] for s in noun_col]


def top_terms(noun_col: pd.Series, top_n: int = 30) -> pd.DataFrame:
    counter: Counter[str] = Counter()
    for words in _as_lists(noun_col):
        counter.update(words)
    return pd.DataFrame(counter.most_common(top_n), columns=["term", "count"])


def top_ngrams(noun_col: pd.Series, n: int = 2, top_n: int = 25) -> pd.DataFrame:
    counter: Counter[str] = Counter()
    for words in _as_lists(noun_col):
        for i in range(len(words) - n + 1):
            counter.update([" ".join(words[i : i + n])])
    label = {2: "bigram", 3: "trigram"}.get(n, f"{n}-gram")
    return pd.DataFrame(counter.most_common(top_n), columns=[label, "count"])


def cooccurrence(noun_col: pd.Series, top_n: int = 25, min_count: int = 2) -> pd.DataFrame:
    counter: Counter[tuple[str, str]] = Counter()
    for words in _as_lists(noun_col):
        for a, b in combinations(sorted(set(words)), 2):
            counter.update([(a, b)])
    rows = [
        {"term_a": a, "term_b": b, "count": c}
        for (a, b), c in counter.most_common(top_n)
        if c >= min_count
    ]
    return pd.DataFrame(rows, columns=["term_a", "term_b", "count"])


def jaccard_str(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
