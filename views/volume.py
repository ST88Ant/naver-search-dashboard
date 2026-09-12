"""💬 채널별 언급량 — "얼마나 이야기될까?"

공급 쪽 화면. 검색 API 로 모은 문서 수와, 네이버가 신고하는 전체 문서 수
(`total`)를 다룬다. 검색량이 아니라 **콘텐츠가 얼마나 쌓였는지**를 본다.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from naver_insight.client import SEARCH_SERVICES
from naver_insight.eda import charts, stats
from naver_insight.insights import compare_summary, render_headline, render_summary_box

from . import _common as C

QUESTION = "얼마나 이야기될까?"


def long_frame(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """검색어 × 채널 롱 포맷 (수집건수 / 신고총량 / 평균길이)."""
    rows = []
    for service, df in data.items():
        label = C.label_of(service)
        for q, part in df.groupby("query"):
            tr = part["total_reported"].dropna() if "total_reported" in part else pd.Series(dtype=float)
            rows.append({
                "검색어": q,
                "채널": label,
                "수집건수": len(part),
                "신고총량": int(tr.iloc[0]) if not tr.empty else None,
                "평균길이": round(part["total_len"].mean(), 1) if "total_len" in part else None,
            })
    return pd.DataFrame(rows)


def _answer(long: pd.DataFrame) -> str:
    by_q = long.groupby("검색어")["수집건수"].sum().sort_values(ascending=False)
    top, top_v = by_q.index[0], int(by_q.iloc[0])
    share = top_v / by_q.sum() * 100
    by_c = long.groupby("채널")["수집건수"].sum().sort_values(ascending=False)

    msg = (f"가장 많이 이야기되는 검색어는 <b>{top}</b>입니다. "
           f"{top_v:,}건으로 전체의 {share:.0f}%를 차지합니다.")
    msg += f" 언급이 가장 많이 쌓이는 채널은 <b>{by_c.index[0]}</b>입니다({int(by_c.iloc[0]):,}건)."
    return msg


def render() -> None:
    st.subheader("💬 채널별 언급량")
    st.caption(
        "뉴스·블로그·카페 등 채널마다 그 검색어로 글이 얼마나 쌓였는지를 봅니다. "
        "사람들이 얼마나 **찾는지**가 아니라 얼마나 **쓰였는지**입니다."
    )

    data = C.need_search()
    if data is None:
        return

    long = long_frame(data)
    if long.empty:
        st.info("표시할 데이터가 없습니다.")
        return

    render_headline(QUESTION, _answer(long))
    C.caption_period()

    by_q = long.groupby("검색어")["수집건수"].sum().sort_values(ascending=False)
    piv = long.pivot_table(index="검색어", columns="채널", values="수집건수", fill_value=0)
    skew = (piv.max(axis=1) / piv.sum(axis=1).replace(0, 1) * 100).sort_values(ascending=False)

    k = st.columns(4)
    k[0].metric("총 수집 문서", f"{int(long['수집건수'].sum()):,}")
    k[1].metric("언급 1위 검색어", by_q.index[0], f"{int(by_q.iloc[0]):,}건", delta_color="off")
    k[2].metric("살아 있는 채널", f"{long['채널'].nunique()} / {len(SEARCH_SERVICES)}")
    k[3].metric("채널 쏠림 1위", skew.index[0], f"한 채널이 {skew.iloc[0]:.0f}%", delta_color="off")

    # ── 헤드라인 그래프: 히트맵 대신 단순 막대 ────────────────
    st.plotly_chart(
        charts.bar(by_q.reset_index(name="문서 수"), "검색어", "문서 수",
                   "검색어별 총 언급량", color="검색어"),
        width="stretch",
    )

    # ── 근거 ────────────────────────────────────────────────
    st.markdown("#### 근거")
    render_summary_box(compare_summary(
        long.rename(columns={"채널": "서비스", "신고총량": "API_total"})
    ))

    c1, c2 = st.columns(2)
    with c1:
        st.caption("각 검색어가 어느 채널에 몰려 있는지 (막대마다 100%)")
        st.plotly_chart(
            charts.stacked_bar(long, "검색어", "수집건수", "채널",
                               "검색어별 채널 구성", percent=True),
            width="stretch",
        )
    with c2:
        st.caption("색이 진할수록 그 칸의 문서가 많다는 뜻입니다")
        st.plotly_chart(
            charts.heatmap(piv.reset_index(), "채널 × 검색어 문서 수", index_col="검색어"),
            width="stretch",
        )

    reported = long.dropna(subset=["신고총량"])
    if not reported.empty:
        st.caption("네이버가 신고하는 전체 문서 수입니다. 수집한 건수보다 훨씬 큽니다.")
        st.plotly_chart(
            charts.bar(reported, "채널", "신고총량", "채널별 신고 총량", color="검색어"),
            width="stretch",
        )

    dated = {s: d for s, d in data.items() if "date" in d and d["date"].notna().any()}
    if dated:
        pick = st.selectbox("발행 추이를 볼 채널", list(dated), format_func=C.icon_label,
                            key="vol_ts_svc")
        st.plotly_chart(
            charts.line(stats.daily_counts(dated[pick], "D"), "date", "count", "query",
                        f"{C.label_of(pick)} 일자별 문서 수", y_title="문서 수"),
            width="stretch",
        )

    with C.evidence("표로 보기"):
        st.markdown("**채널 커버리지**")
        st.dataframe(stats.summary_table(data, SEARCH_SERVICES), width="stretch", hide_index=True)
        st.markdown("**교차표: 검색어 × 채널**")
        st.dataframe(piv.reset_index(), width="stretch", hide_index=True)
