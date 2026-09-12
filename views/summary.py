"""종합 요약 탭 (랜딩)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from naver_insight.client import SEARCH_SERVICES
from naver_insight.eda import charts, stats
from naver_insight.eda import text as textmod
from naver_insight.insights import render_summary_box


def _overall_lines(enriched: dict[str, pd.DataFrame], summary: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    live = {s: d for s, d in enriched.items() if d is not None and not d.empty}
    total = int(summary["수집건수"].sum())
    by_svc = summary.groupby("서비스")["수집건수"].sum().sort_values(ascending=False)
    lines.append(f"📦 **{len(live)}개 서비스 · 총 {total:,}건** 수집 — 최다 **{by_svc.index[0]}**({int(by_svc.iloc[0]):,}건)")

    plot = summary[summary["검색어"] != "-"]
    if not plot.empty:
        by_q = plot.groupby("검색어")["수집건수"].sum().sort_values(ascending=False)
        share = by_q.iloc[0] / by_q.sum() * 100
        lines.append(f"🔎 검색어별 총량 1위 **'{by_q.index[0]}'** — 전체의 {share:.0f}%")

    all_nouns = pd.concat([d["noun_str"] for d in live.values() if "noun_str" in d], ignore_index=True) \
        if live else pd.Series(dtype=object)
    if not all_nouns.empty:
        top = textmod.top_terms(all_nouns, 8)["term"].tolist()
        lines.append(f"🔑 전 서비스 공통 핵심어: **{', '.join(top)}**")
    return lines


def render() -> None:
    st.subheader("종합 요약")
    st.caption(
        "NAVER API HUB · 뉴스 / 블로그 / 웹문서 / 이미지 / 지식iN / 지역 / 카페글 / 백과사전 + 검색어 트렌드"
    )

    enriched: dict[str, pd.DataFrame] = st.session_state.get("enriched", {})
    meta = st.session_state.get("meta", {})
    if not enriched:
        st.info(
            "왼쪽 사이드바에서 **검색어(쉼표로 구분)** 와 **기간** 을 입력하고 **🚀 수집 실행** 을 눌러주세요.\n\n"
            "- 서비스별 분석은 위 탭에서 열립니다.\n"
            "- 수집 원자료는 `data/<서비스>/` 에 CSV 로 저장됩니다."
        )
        return

    summary = stats.summary_table(enriched, SEARCH_SERVICES)
    render_summary_box(_overall_lines(enriched, summary))

    total_docs = int(summary["수집건수"].sum())
    m = st.columns(4)
    m[0].metric("검색어 수", len(meta.get("queries", [])))
    m[1].metric("수집 서비스", len([s for s, d in enriched.items() if d is not None and not d.empty]))
    m[2].metric("총 수집 문서", f"{total_docs:,}")
    m[3].metric("기간", f"{meta.get('start')} ~ {meta.get('end')}")

    st.divider()
    plot = summary[summary["검색어"] != "-"]
    view = st.radio(
        "요약 그래프 유형",
        ["서비스 × 검색어 히트맵", "서비스별 수집량 (그룹 막대)", "검색어별 서비스 구성 (100% 누적 막대)", "서비스별 수집 비중 (트리맵)", "API 신고 총량 비교", "서비스별 평균 텍스트 길이"],
        horizontal=True, key="summary_view",
    )
    if view == "서비스 × 검색어 히트맵":
        st.plotly_chart(charts.heatmap(
            plot.pivot_table(index="서비스", columns="검색어", values="수집건수", fill_value=0).reset_index(),
            "서비스 × 검색어 수집 건수", index_col="서비스"), width="stretch")
    elif view == "서비스별 수집량 (그룹 막대)":
        st.plotly_chart(charts.grouped_bar(plot, "서비스", "수집건수", "검색어",
                                           "서비스 × 검색어별 수집 건수"), width="stretch")
    elif view == "검색어별 서비스 구성 (100% 누적 막대)":
        st.plotly_chart(charts.stacked_bar(plot, "검색어", "수집건수", "서비스",
                                           "검색어별 서비스 구성 비중 (100% 누적)", percent=True), width="stretch")
    elif view == "서비스별 수집 비중 (트리맵)":
        st.plotly_chart(charts.treemap(plot, ["서비스", "검색어"], "수집건수",
                                       "서비스 → 검색어별 수집 비중 (트리맵)"), width="stretch")
    elif view == "API 신고 총량 비교":
        st.plotly_chart(charts.bar(plot.dropna(subset=["API total"]), "서비스", "API total",
                                   "서비스별 API 신고 총량", color="검색어"), width="stretch")
    else:
        st.plotly_chart(charts.bar(plot.dropna(subset=["평균길이"]), "서비스", "평균길이",
                                   "서비스별 평균 텍스트 길이", color="검색어", orientation="h"), width="stretch")

    st.divider()
    st.markdown("#### 서비스 커버리지")
    st.dataframe(summary, width="stretch", hide_index=True)
