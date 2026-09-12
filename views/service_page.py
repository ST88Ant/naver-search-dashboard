"""서비스별 상세 분석 탭 (뉴스·블로그·웹문서·지식iN·카페글·백과사전·이미지·지역)."""

from __future__ import annotations

import streamlit as st

from naver_insight.client import SEARCH_SERVICES
from naver_insight.render import render_service_tab
from naver_insight.specs import build_specs

_LOCAL_BANNER = (
    "네이버 지역 검색 API는 검색어당 최대 5건만 반환합니다(공식 제약). "
    "지역·업종 통계는 표본이 작은 참고치이며, 네이버 검색 API에는 "
    "'검색어별 지역 검색량' 데이터가 없습니다."
)


def render(service: str) -> None:
    label = SEARCH_SERVICES.get(service, service)
    enriched = st.session_state.get("enriched", {})
    meta = st.session_state.get("meta", {})
    df = enriched.get(service)

    if df is None or df.empty:
        render_service_tab(service, label, df, meta, [], [])
        return

    chart_specs, table_specs = build_specs(service, df)
    render_service_tab(
        service, label, df, meta, chart_specs, table_specs,
        banner=_LOCAL_BANNER if service == "local" else None,
    )
