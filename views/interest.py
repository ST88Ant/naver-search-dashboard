"""📈 검색 관심도 — "얼마나 찾을까?"

수요 쪽 화면. 데이터랩 통합검색의 상대 검색량 추이를 다룬다.
`ratio` 는 조회 기간 내 최댓값을 100 으로 환산한 상대값이라 절대 검색량이 아니다.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from naver_insight.eda import charts
from naver_insight.insights import render_headline, render_summary_box, trend_summary

from . import _common as C

QUESTION = "얼마나 찾을까?"


def _answer(t: pd.DataFrame) -> str:
    mean_by = t.groupby("group")["ratio"].mean().sort_values(ascending=False)
    top, top_v = mean_by.index[0], mean_by.iloc[0]
    ordered = t.sort_values("period")
    first = ordered.groupby("group").head(1).set_index("group")["ratio"]
    last = ordered.groupby("group").tail(1).set_index("group")["ratio"]
    delta = (last - first).sort_values(ascending=False)
    rise, rise_v = delta.index[0], delta.iloc[0]

    msg = f"관심도가 가장 높은 검색어는 <b>{top}</b>입니다. 기간 평균 {top_v:.0f}점."
    if len(mean_by) > 1:
        second = mean_by.index[1]
        gap = top_v / max(mean_by.iloc[1], 0.01)
        msg += f" 2위 {second}보다 {gap:.1f}배 높습니다."
    if rise_v > 0:
        msg += f" 기간 동안 가장 많이 오른 검색어는 <b>{rise}</b>입니다({rise_v:+.0f}점)."
    else:
        msg += " 기간 동안 오른 검색어는 없습니다."
    return msg


def render() -> None:
    st.subheader("📈 검색 관심도")
    st.caption(
        "네이버 데이터랩 통합검색 기준입니다. 점수는 조회 기간 내 최댓값을 100으로 "
        "맞춘 **상대값**이라, 실제 검색 횟수가 아니라 서로 간의 크기 비교로 읽어야 합니다."
    )

    t = C.need_trend()
    if t is None:
        return

    render_headline(QUESTION, _answer(t))
    C.caption_period()

    mean_by = t.groupby("group")["ratio"].mean().sort_values(ascending=False)
    std_by = t.groupby("group")["ratio"].std()
    ordered = t.sort_values("period")
    first = ordered.groupby("group").head(1).set_index("group")["ratio"]
    last = ordered.groupby("group").tail(1).set_index("group")["ratio"]
    delta = (last - first).sort_values(ascending=False)

    k = st.columns(4)
    k[0].metric("관심도 1위", mean_by.index[0], f"평균 {mean_by.iloc[0]:.0f}점", delta_color="off")
    k[1].metric("가장 많이 오른 검색어", delta.index[0], f"{delta.iloc[0]:+.0f}점")
    k[2].metric("기복이 가장 큰 검색어", std_by.idxmax(), f"표준편차 {std_by.max():.0f}", delta_color="off")
    k[3].metric("관측 구간 수", f"{t['period'].nunique():,}", delta_color="off")

    # ── 헤드라인 그래프 ──────────────────────────────────────
    st.plotly_chart(
        charts.line(t, "period", "ratio", "group", "검색어별 관심도 추이",
                    y_title="상대 검색량 (기간 내 최대 = 100)"),
        width="stretch",
    )

    # ── 근거 ────────────────────────────────────────────────
    st.markdown("#### 근거")
    render_summary_box(trend_summary(t))

    c1, c2 = st.columns(2)
    with c1:
        avg = mean_by.reset_index(name="평균 점수")
        st.plotly_chart(charts.bar(avg, "group", "평균 점수", "기간 평균 관심도",
                                   color="group"), width="stretch")
    with c2:
        sd = std_by.reset_index(name="표준편차")
        st.plotly_chart(charts.bar(sd, "group", "표준편차", "관심도 기복(클수록 들쭉날쭉)",
                                   color="group"), width="stretch")

    month = t.assign(월=t["period"].dt.to_period("M").astype(str))
    piv = month.pivot_table(index="group", columns="월", values="ratio", aggfunc="mean").reset_index()
    if piv.shape[1] > 2:
        st.plotly_chart(
            charts.heatmap(piv, "검색어 × 월 평균 관심도 (색이 진할수록 높음)", index_col="group"),
            width="stretch",
        )

    with C.evidence("표로 보기"):
        st.markdown("**기술통계**")
        st.dataframe(t.groupby("group")["ratio"].describe().round(2).reset_index(),
                     width="stretch", hide_index=True)
        st.markdown("**기간 × 검색어 원본 점수**")
        st.dataframe(t.pivot_table(index="period", columns="group", values="ratio").reset_index(),
                     width="stretch", hide_index=True)
