"""검색어 비교 탭 — 한 검색어가 서비스(API)별로 얼마나 노출되는지 교차 비교."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from naver_insight.client import SEARCH_SERVICES
from naver_insight.eda import charts
from naver_insight.eda import text as textmod
from naver_insight.insights import compare_summary, render_summary_box


def _long_frame(enriched: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for service, df in enriched.items():
        if df is None or df.empty:
            continue
        label = SEARCH_SERVICES.get(service, service)
        for q, part in df.groupby("query"):
            tr = part["total_reported"].dropna() if "total_reported" in part else pd.Series(dtype=float)
            rows.append({
                "검색어": q, "서비스": label, "수집건수": len(part),
                "API_total": int(tr.iloc[0]) if not tr.empty else None,
                "평균길이": round(part["total_len"].mean(), 1) if "total_len" in part else None,
            })
    return pd.DataFrame(rows)


def render() -> None:
    st.subheader("검색어 비교")
    enriched: dict[str, pd.DataFrame] = st.session_state.get("enriched", {})
    if not enriched:
        st.info("먼저 사이드바에서 수집을 실행하세요.")
        return

    long = _long_frame(enriched)
    if long.empty:
        st.info("표시할 데이터가 없습니다.")
        return

    render_summary_box(compare_summary(long))

    metric = st.radio("비교 지표", ["수집건수", "API_total", "평균길이"], horizontal=True, key="cmp_metric")
    view = st.radio("그래프", ["검색어 × 서비스 히트맵", "그룹 막대", "서비스 구성(100% 누적)"],
                    horizontal=True, key="cmp_view")

    pivot = long.pivot_table(index="검색어", columns="서비스", values=metric, fill_value=0).reset_index()
    if view == "검색어 × 서비스 히트맵":
        st.plotly_chart(charts.heatmap(pivot, f"검색어 × 서비스 — {metric}", index_col="검색어"), width="stretch")
    elif view == "그룹 막대":
        st.plotly_chart(charts.grouped_bar(long, "검색어", metric, "서비스", f"검색어별 {metric}"), width="stretch")
    else:
        st.plotly_chart(charts.stacked_bar(long, "검색어", metric, "서비스",
                                           f"검색어별 서비스 구성 — {metric}", percent=True), width="stretch")

    st.divider()
    st.markdown("#### 교차표: 검색어 × 서비스")
    st.dataframe(pivot, width="stretch", hide_index=True)

    st.markdown("#### 검색어별 대표 키워드 (전 서비스 통합)")
    kw_rows = []
    for q in long["검색어"].unique():
        nouns = pd.concat(
            [d.loc[d["query"] == q, "noun_str"] for d in enriched.values()
             if d is not None and "noun_str" in d and (d["query"] == q).any()],
            ignore_index=True,
        )
        if nouns.empty:
            continue
        kw_rows.append({"검색어": q, "상위 키워드": ", ".join(textmod.top_terms(nouns, 10)["term"])})
    if kw_rows:
        st.dataframe(pd.DataFrame(kw_rows), width="stretch", hide_index=True)
