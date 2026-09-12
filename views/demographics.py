"""👥 성별·연령 분석 — "누가 찾을까?"

트렌드 API 는 성별·연령을 요청 전체에 걸리는 필터로 받으므로 세그먼트마다
호출을 따로 해야 한다. 호출이 갈리면 `ratio` 정규화도 갈리기 때문에, 이 화면은
세그먼트 안에서의 **구성비**만 비교한다. 자세한 이유는 `naver_insight.segments`.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from naver_insight import segments
from naver_insight.client import NaverApiHubClient
from naver_insight.eda import charts
from naver_insight.insights import render_empty, render_headline

from . import _common as C

QUESTION = "누가 찾을까?"

_CAVEAT = (
    "세그먼트마다 API 를 따로 호출하고, 호출마다 점수가 새로 100점 만점으로 "
    "환산됩니다. 그래서 **연령대끼리 검색량의 많고 적음은 비교할 수 없습니다.** "
    "대신 한 연령대 안에서 검색어들이 나눠 갖는 **비중**은 환산 배율이 약분되어 "
    "안전하게 비교됩니다. 아래 그래프는 모두 그 비중입니다."
)


def _collect() -> None:
    creds = st.session_state.get("creds")
    params = st.session_state.get("trend_params")
    if not creds or not params:
        st.error("먼저 사이드바에서 수집을 실행해주세요.")
        return
    client = NaverApiHubClient(creds[0], creds[1], base_url=creds[2])
    bar = st.progress(0.0, "준비 중…")
    try:
        splits = segments.collect_splits(
            client, params["queries"], params["start"], params["end"],
            time_unit="month",
            progress=lambda p, msg: bar.progress(min(p, 1.0), msg),
        )
    finally:
        bar.empty()
    st.session_state["splits"] = splits


def _answer(splits: dict[str, pd.DataFrame]) -> str:
    parts: list[str] = []
    gender = splits.get("gender")
    if gender is not None and not gender.empty:
        piv = gender.pivot_table(index="검색어", columns="세그먼트", values="구성비")
        if {"남성", "여성"} <= set(piv.columns):
            piv["차이"] = piv["여성"] - piv["남성"]
            top = piv["차이"].abs().idxmax()
            d = piv.loc[top, "차이"]
            lean = "여성" if d > 0 else "남성"
            parts.append(f"<b>{top}</b>은(는) {lean} 쪽에 가장 치우쳐 있습니다"
                         f"(비중 차이 {abs(d):.1f}%p).")
    age = splits.get("age")
    if age is not None and not age.empty:
        sk = segments.skew_table(age)
        if not sk.empty:
            r = sk.iloc[0]
            parts.append(f"연령대별 쏠림이 가장 큰 검색어는 <b>{r['검색어']}</b>이고, "
                         f"{r['가장 우세한 연령대']}에서 비중이 가장 높습니다"
                         f"({r['그 연령대에서의 구성비']}).")
    return " ".join(parts) if parts else "세그먼트 데이터를 읽지 못했습니다."


def render() -> None:
    st.subheader("👥 성별·연령 분석")
    st.caption("검색어를 찾는 사람이 어느 층에 몰려 있는지 봅니다.")

    if C.trend().empty and "splits" not in st.session_state:
        render_empty(
            "먼저 사이드바에서 <b>🚀 수집 실행</b>을 눌러 트렌드 데이터를 받아주세요.<br>"
            "그다음 이 페이지에서 성별·연령을 따로 조회할 수 있습니다."
        )
        return

    splits: dict[str, pd.DataFrame] = st.session_state.get("splits", {})

    if not splits:
        render_empty(
            "성별·연령 데이터는 별도 조회가 필요합니다.<br>"
            "성별 2회, 기기 2회, 연령 11회로 <b>총 15회</b> API 를 호출합니다. "
            "10초 안팎 걸립니다."
        )
        st.button("👥 성별·연령 조회하기", type="primary", on_click=_collect)
        return

    render_headline(QUESTION, _answer(splits))
    st.info(_CAVEAT, icon="ℹ️")
    C.caption_period()

    age = splits.get("age", pd.DataFrame())
    gender = splits.get("gender", pd.DataFrame())
    device = splits.get("device", pd.DataFrame())

    # ── 헤드라인 그래프: 연령대별 검색어 비중 ────────────────
    if not age.empty:
        st.plotly_chart(
            charts.stacked_bar(
                age.assign(세그먼트=age["세그먼트"].astype(str)),
                "세그먼트", "구성비", "검색어",
                "연령대별 검색어 비중 (각 막대 100%)", percent=True,
            ),
            width="stretch",
        )
    else:
        st.warning("연령 데이터를 받지 못했습니다.")

    # ── 근거 ────────────────────────────────────────────────
    st.markdown("#### 근거")
    c1, c2 = st.columns(2)
    with c1:
        if not gender.empty:
            st.plotly_chart(
                charts.grouped_bar(gender, "검색어", "구성비", "세그먼트",
                                   "성별 검색어 비중 (%)"),
                width="stretch",
            )
    with c2:
        if not device.empty:
            st.plotly_chart(
                charts.grouped_bar(device, "검색어", "구성비", "세그먼트",
                                   "기기별 검색어 비중 (%)"),
                width="stretch",
            )

    if not age.empty:
        piv = age.assign(세그먼트=age["세그먼트"].astype(str)).pivot_table(
            index="검색어", columns="세그먼트", values="구성비", observed=True
        ).reset_index()
        st.plotly_chart(
            charts.heatmap(piv, "검색어 × 연령대 비중 (색이 진할수록 그 연령대 비중이 큼)",
                           index_col="검색어"),
            width="stretch",
        )

        st.markdown("**검색어별 연령 쏠림 요약**")
        st.dataframe(segments.skew_table(age), width="stretch", hide_index=True)

    with C.evidence("원본 구성비 표"):
        for name, df in (("연령", age), ("성별", gender), ("기기", device)):
            if df is not None and not df.empty:
                st.markdown(f"**{name}**")
                st.dataframe(df.assign(세그먼트=df["세그먼트"].astype(str)).round(2),
                             width="stretch", hide_index=True)

    st.button("🔄 다시 조회", on_click=_collect)
