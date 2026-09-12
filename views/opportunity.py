"""💡 키워드 기회 — "그래서 쓸 만할까?"

이 대시보드의 결론 화면. 앞의 두 축을 처음으로 한 그래프에서 만나게 한다.

  · 수요 = 검색어 트렌드의 기간 평균 점수 (얼마나 찾나)
  · 공급 = 검색 API 가 신고하는 전체 문서 수 (얼마나 쓰였나)

찾는 사람은 많은데 쓰인 글은 적은 자리, 즉 **왼쪽 위**가 기회다.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import streamlit as st

from naver_insight.eda import charts
from naver_insight.insights import render_empty, render_headline

from . import _common as C
from .volume import long_frame

QUESTION = "그래서 쓸 만할까?"

_CAVEAT = (
    "수요 점수는 한 번의 트렌드 호출 안에서만 서로 비교됩니다. 수집을 다시 하면 "
    "기준이 새로 잡히므로 **다른 날 수집한 점수와 견주지 마세요.** 공급은 네이버가 "
    "신고하는 문서 수라 추정치이고, 실제 경쟁 강도와 정확히 같지는 않습니다. "
    "순위를 참고하는 용도로 보시는 게 맞습니다."
)


def build(data: dict[str, pd.DataFrame], trend: pd.DataFrame, channel: str) -> pd.DataFrame:
    """검색어별 수요·공급·기회 점수 표."""
    demand = trend.groupby("group")["ratio"].mean().rename("수요")

    long = long_frame(data)
    sub = long[long["채널"] == channel]
    supply = sub.set_index("검색어")["신고총량"]
    if supply.isna().all():
        supply = sub.set_index("검색어")["수집건수"]
    supply = supply.dropna().rename("공급")

    df = pd.concat([demand, supply], axis=1).dropna()
    if df.empty:
        return df
    df = df.reset_index(names="검색어")
    df["공급"] = df["공급"].astype(float).clip(lower=1)
    # log 를 쓰는 이유: 문서 수는 자릿수 단위로 벌어져서 선형으로 두면
    # 큰 값 하나가 그래프를 다 먹는다.
    df["경쟁강도"] = np.log10(df["공급"])
    df["기회점수"] = (df["수요"] / df["경쟁강도"].clip(lower=0.3)).round(1)
    return df.sort_values("기회점수", ascending=False).reset_index(drop=True)


def _answer(df: pd.DataFrame, channel: str) -> str:
    best = df.iloc[0]
    msg = (f"{channel} 기준으로 기회가 가장 큰 검색어는 <b>{best['검색어']}</b> 입니다. "
           f"수요 {best['수요']:.0f}점에 문서가 {int(best['공급']):,}건으로, "
           f"찾는 사람 대비 쌓인 글이 적습니다.")
    if len(df) > 1:
        worst = df.iloc[-1]
        msg += (f" 반대로 <b>{worst['검색어']}</b>은(는) 문서가 {int(worst['공급']):,}건 쌓여 있어 "
                f"경쟁이 가장 치열합니다.")
    return msg


def _scatter(df: pd.DataFrame, channel: str):
    fig = charts.scatter(df, "공급", "수요", f"{channel} 수요 · 공급 지도",
                         color="검색어", size="기회점수", hover_name="검색어")
    fig.update_xaxes(type="log", title="공급 · 이미 쌓인 문서 수 (로그 눈금)")
    fig.update_yaxes(title="수요 · 검색 관심도 평균")
    if len(df) >= 2:
        mx, my = float(df["공급"].median()), float(df["수요"].median())
        fig.add_vline(x=mx, line_dash="dot", line_color="#d3508e", opacity=0.5)
        fig.add_hline(y=my, line_dash="dot", line_color="#d3508e", opacity=0.5)
        fig.add_annotation(x=math.log10(max(df["공급"].min(), 1)), y=float(df["수요"].max()),
                           text="🍀 기회 · 찾는 사람 많고 글은 적음", showarrow=False,
                           xanchor="left", yanchor="top",
                           font=dict(size=12, color="#8f1357"))
        fig.add_annotation(x=math.log10(float(df["공급"].max())), y=float(df["수요"].min()),
                           text="🔥 레드오션 · 글은 많고 찾는 사람은 적음", showarrow=False,
                           xanchor="right", yanchor="bottom",
                           font=dict(size=12, color="#6b6570"))
    fig.update_traces(marker=dict(line=dict(width=2, color="#fffafc")))
    return fig


def render() -> None:
    st.subheader("💡 키워드 기회")
    st.caption("수요와 공급을 한 그래프에 겹쳐, 지금 쓸 만한 키워드를 가려냅니다.")

    data = C.enriched()
    trend = C.trend()
    if not data or trend.empty:
        missing = []
        if not data:
            missing.append("검색 데이터")
        if trend.empty:
            missing.append("트렌드 데이터")
        render_empty(
            f"이 화면은 <b>수요와 공급을 모두</b> 써서 그립니다.<br>"
            f"지금 {' 와 '.join(missing)}가 없습니다. 사이드바에서 수집을 실행해주세요."
        )
        return

    long = long_frame(data)
    channels = sorted(long["채널"].unique())
    default = "블로그" if "블로그" in channels else channels[0]
    channel = st.selectbox(
        "경쟁을 잴 채널", channels, index=channels.index(default), key="opp_channel",
        help="블로그나 카페글이 상위노출 경쟁을 가장 잘 대변합니다.",
    )

    df = build(data, trend, channel)
    if df.empty:
        st.info("수요와 공급이 모두 있는 검색어가 없습니다. 트렌드와 검색을 같은 검색어로 수집해주세요.")
        return

    render_headline(QUESTION, _answer(df, channel))
    st.info(_CAVEAT, icon="⚠️")
    C.caption_period()

    best = df.iloc[0]
    k = st.columns(4)
    k[0].metric("기회 1위", str(best["검색어"]), f"점수 {best['기회점수']}", delta_color="off")
    k[1].metric("그 검색어 수요", f"{best['수요']:.0f}")
    k[2].metric("그 검색어 공급", f"{int(best['공급']):,}건")
    k[3].metric("비교한 검색어", f"{len(df)}개")

    # ── 헤드라인 그래프 ──────────────────────────────────────
    st.plotly_chart(_scatter(df, channel), width="stretch")
    st.caption(
        "점이 왼쪽 위로 갈수록 좋습니다. 가로축은 이미 쌓인 글의 수라서 오른쪽일수록 "
        "경쟁이 세고, 세로축은 찾는 사람의 많고 적음이라 위쪽일수록 수요가 큽니다."
    )

    # ── 근거 ────────────────────────────────────────────────
    st.markdown("#### 근거")
    st.plotly_chart(
        charts.bar(df, "검색어", "기회점수", "검색어별 기회 점수", color="검색어"),
        width="stretch",
    )
    st.caption("기회 점수는 수요를 경쟁강도로 나눈 값입니다. 경쟁강도는 문서 수에 로그를 씌운 값입니다.")

    show = df.assign(
        공급=df["공급"].map(lambda v: f"{int(v):,}건"),
        수요=df["수요"].round(1),
        경쟁강도=df["경쟁강도"].round(2),
    )
    st.dataframe(show, width="stretch", hide_index=True)

    with C.evidence("채널을 바꿔가며 비교"):
        rows = []
        for ch in channels:
            part = build(data, trend, ch)
            if part.empty:
                continue
            part = part.assign(채널=ch)
            rows.append(part[["채널", "검색어", "수요", "공급", "기회점수"]])
        if rows:
            allch = pd.concat(rows, ignore_index=True)
            st.dataframe(allch.round(1), width="stretch", hide_index=True)
            st.plotly_chart(
                charts.heatmap(
                    allch.pivot_table(index="채널", columns="검색어", values="기회점수").reset_index(),
                    "채널 × 검색어 기회 점수", index_col="채널"),
                width="stretch",
            )
