"""검색어 트렌드 탭 (데이터랩 통합검색 상대 검색량)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from naver_insight.eda import charts
from naver_insight.insights import render_summary_box, trend_summary


def render() -> None:
    st.subheader("검색어 트렌드")
    st.caption(
        "네이버 데이터랩 통합검색 상대 검색량 추이. `ratio` 는 조회 기간 내 최대 검색량을 "
        "100 으로 환산한 값이며 절대 검색량이 아닙니다."
    )
    trend: pd.DataFrame = st.session_state.get("trend", pd.DataFrame())
    meta = st.session_state.get("meta", {})
    if trend is None or trend.empty:
        st.warning("검색어 트렌드 데이터가 없습니다. 사이드바에서 수집을 실행하거나 옵션을 확인하세요.")
        return

    render_summary_box(trend_summary(trend))
    if meta:
        st.caption(f"기간 {meta.get('start')} ~ {meta.get('end')}")

    view = st.radio(
        "그래프", ["추이 선그래프", "기간 평균 막대", "변동성(표준편차)", "검색어 × 월 히트맵"],
        horizontal=True, key="trend_view",
    )
    if view == "추이 선그래프":
        st.plotly_chart(charts.line(trend, "period", "ratio", "group", "검색어별 상대 검색량 추이",
                                    y_title="상대 검색량 (최대=100)"), width="stretch")
    elif view == "기간 평균 막대":
        avg = trend.groupby("group")["ratio"].mean().reset_index(name="평균 ratio")
        st.plotly_chart(charts.bar(avg, "group", "평균 ratio", "검색어별 기간 평균 상대 검색량",
                                   color="group"), width="stretch")
    elif view == "변동성(표준편차)":
        std = trend.groupby("group")["ratio"].std().reset_index(name="표준편차")
        st.plotly_chart(charts.bar(std, "group", "표준편차", "검색어별 검색량 변동성", color="group"),
                        width="stretch")
    else:
        t = trend.assign(월=trend["period"].dt.to_period("M").astype(str))
        piv = t.pivot_table(index="group", columns="월", values="ratio", aggfunc="mean").reset_index()
        st.plotly_chart(charts.heatmap(piv, "검색어 × 월 평균 상대 검색량", index_col="group"), width="stretch")

    st.divider()
    st.markdown("#### 기술통계")
    st.dataframe(trend.groupby("group")["ratio"].describe().round(2).reset_index(),
                width="stretch", hide_index=True)
    st.markdown("#### 피봇: 기간 × 검색어")
    st.dataframe(trend.pivot_table(index="period", columns="group", values="ratio").reset_index(),
                width="stretch", hide_index=True)
