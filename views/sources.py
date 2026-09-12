"""🌐 출처 분석 — "어디서 이야기될까?"

언급이 어느 매체·블로그·카페에서 나오는지를 본다. 상위 몇 곳이 언급의 대부분을
차지하면 자연스러운 확산이 아니라 한쪽에서 밀어낸 물량일 가능성이 있다.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from naver_insight.eda import charts, stats
from naver_insight.insights import render_empty, render_headline
from naver_insight.specs import domain_agg

from . import _common as C

QUESTION = "어디서 이야기될까?"


def _with_domain(data: dict[str, pd.DataFrame]) -> list[str]:
    return [s for s, d in data.items()
            if "domain" in d and d["domain"].ne("(없음)").any()]


def _concentration(df: pd.DataFrame, n: int = 3) -> tuple[float, list[str]]:
    """상위 n개 출처가 차지하는 비중(%)과 그 이름."""
    vc = df[df["domain"] != "(없음)"]["domain"].value_counts()
    if vc.empty:
        return 0.0, []
    top = vc.head(n)
    return float(top.sum() / len(df) * 100), list(top.index)


def _answer(df: pd.DataFrame, label: str) -> str:
    share, names = _concentration(df)
    uniq = df["domain"].nunique()
    msg = (f"{label}에서 언급은 <b>{uniq:,}개</b> 출처에서 나왔습니다. "
           f"상위 3곳({', '.join(names)})이 전체의 <b>{share:.0f}%</b>를 차지합니다.")
    if share >= 60:
        msg += " 소수 출처에 크게 쏠려 있어 자연 확산으로 보기 어렵습니다."
    elif share <= 25:
        msg += " 특정 출처 쏠림 없이 고르게 퍼져 있습니다."
    return msg


def render() -> None:
    st.subheader("🌐 출처 분석")
    st.caption("언급이 어느 사이트에서 나오는지, 몇 곳에 몰려 있는지를 봅니다.")

    data = C.need_search()
    if data is None:
        return

    services = _with_domain(data)
    if not services:
        render_empty(
            "출처(도메인) 정보를 가진 채널이 없습니다.<br>"
            "뉴스·블로그·웹문서·카페글 중 하나 이상을 수집해주세요."
        )
        return

    service = st.selectbox("채널", services, format_func=C.icon_label, key="src_svc")
    df = data[service]
    label = C.label_of(service)

    render_headline(QUESTION, _answer(df, label))
    C.caption_period()

    share, _ = _concentration(df)
    div = stats.domain_diversity(df)
    k = st.columns(4)
    k[0].metric("고유 출처 수", f"{df['domain'].nunique():,}")
    k[1].metric("상위 3곳 점유율", f"{share:.0f}%")
    k[2].metric("문서 수", f"{len(df):,}")
    if not div.empty:
        best = div.sort_values("고유도메인", ascending=False).iloc[0]
        k[3].metric("출처가 가장 다양한 검색어", str(best["query"]),
                    f"{int(best['고유도메인'])}곳", delta_color="off")

    # ── 헤드라인 그래프 ──────────────────────────────────────
    st.plotly_chart(
        charts.bar(stats.category_counts(df, "domain", 20).iloc[::-1], "count", "domain",
                   f"{label} 상위 출처 20곳", orientation="h"),
        width="stretch",
    )

    # ── 근거 ────────────────────────────────────────────────
    st.markdown("#### 근거")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("검색어마다 출처가 몇 곳으로 퍼져 있는지")
        st.plotly_chart(
            charts.bar(div, "query", "고유도메인", "검색어별 출처 다양성", color="query"),
            width="stretch",
        )
    with c2:
        st.caption("주소 끝자리(.com, .kr 등) 분포")
        st.plotly_chart(
            charts.bar(stats.category_counts(df, "tld", 12), "tld", "count", "최상위도메인 분포"),
            width="stretch",
        )

    st.caption("색이 진할수록 그 검색어가 그 출처에서 많이 나왔다는 뜻입니다")
    st.plotly_chart(
        charts.heatmap(stats.crosstab(df, "query", "domain", top_col=12, margins=False),
                       "검색어 × 출처 문서 수", index_col="query"),
        width="stretch",
    )

    st.plotly_chart(
        charts.treemap(stats.category_counts(df, "domain", 30, group="query"),
                       ["query", "domain"], "count", "검색어에서 출처로 이어지는 구성"),
        width="stretch",
    )

    with C.evidence("표로 보기"):
        st.markdown("**출처별 집계**")
        st.dataframe(domain_agg(df, 25), width="stretch", hide_index=True)
        st.markdown("**교차표: 검색어 × 출처 (문서 수)**")
        st.dataframe(stats.crosstab(df, "query", "domain", top_col=12),
                     width="stretch", hide_index=True)
        st.markdown("**교차표: 검색어 × 출처 (%)**")
        st.dataframe(stats.crosstab(df, "query", "domain", top_col=12, normalize="index"),
                     width="stretch", hide_index=True)
