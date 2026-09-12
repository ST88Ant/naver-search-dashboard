"""페이지 공통 유틸.

모든 페이지는 같은 3층 구조로 그린다.
  1) 헤드라인  — 이 페이지가 답하는 질문 하나와 그 답 한 문장
  2) 헤드라인 그래프 — 답을 뒷받침하는 그래프 하나
  3) 근거      — 보조 그래프와 표 (필요하면 접어둔다)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from naver_insight.client import SEARCH_SERVICES
from naver_insight.insights import render_empty

# 채널(서비스) 아이콘 — 탭 라벨과 셀렉트박스에서 함께 쓴다
ICONS = {
    "news": "📰", "blog": "✍️", "webkr": "🌐", "image": "🖼️",
    "kin": "❓", "local": "📍", "cafearticle": "☕", "encyc": "📚",
}

_NO_SEARCH = (
    "아직 수집한 데이터가 없습니다.<br>"
    "왼쪽 사이드바에서 <b>검색어</b>와 <b>기간</b>을 입력하고 "
    "<b>🚀 수집 실행</b>을 눌러주세요."
)
_NO_TREND = (
    "검색어 트렌드 데이터가 없습니다.<br>"
    "사이드바에서 수집을 실행하거나, 트렌드 API 오류 메시지를 확인해주세요."
)


def label_of(service: str) -> str:
    return SEARCH_SERVICES.get(service, service)


def icon_label(service: str) -> str:
    return f"{ICONS.get(service, '🔎')} {label_of(service)}"


def enriched() -> dict[str, pd.DataFrame]:
    """서비스코드 -> 파생피처가 붙은 DataFrame. 비어 있는 서비스는 제외."""
    raw = st.session_state.get("enriched", {}) or {}
    return {s: d for s, d in raw.items() if d is not None and not d.empty}


def meta() -> dict:
    return st.session_state.get("meta", {}) or {}


def trend() -> pd.DataFrame:
    t = st.session_state.get("trend")
    return t if isinstance(t, pd.DataFrame) else pd.DataFrame()


def need_search() -> dict[str, pd.DataFrame] | None:
    """검색 데이터가 있으면 반환, 없으면 안내를 그리고 None."""
    data = enriched()
    if not data:
        render_empty(_NO_SEARCH)
        return None
    return data


def need_trend() -> pd.DataFrame | None:
    t = trend()
    if t.empty:
        render_empty(_NO_TREND)
        return None
    return t


def text_services(data: dict[str, pd.DataFrame]) -> list[str]:
    """본문 텍스트가 있는 서비스(이미지·지역 제외)."""
    return [s for s in data if s not in ("image", "local")]


def concat_queries(data: dict[str, pd.DataFrame], services: list[str], col: str) -> pd.Series:
    """여러 서비스에서 같은 컬럼을 이어붙인 Series."""
    parts = [d[col] for s, d in data.items() if s in services and col in d]
    return pd.concat(parts, ignore_index=True) if parts else pd.Series(dtype=object)


def all_queries(data: dict[str, pd.DataFrame]) -> list[str]:
    out: list[str] = []
    for d in data.values():
        if "query" in d:
            out += [q for q in d["query"].unique() if q not in out]
    return out


def caption_period() -> None:
    m = meta()
    if m.get("start") and m.get("end"):
        st.caption(f"수집 기간 {m['start']} ~ {m['end']}")


def evidence(title: str = "근거 자세히 보기"):
    """근거 층을 여는 컨테이너."""
    return st.expander(title, expanded=False)
