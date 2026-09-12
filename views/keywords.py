"""🔑 연관 키워드 — "뭐라고 이야기할까?"

전 채널의 제목·본문에서 명사를 뽑아, 사람들이 이 주제를 어떤 말로 이야기하는지 본다.
지식iN 질문은 따로 떼어 보여준다. 홍보 글이 섞이는 다른 채널과 달리 구매·결정
직전의 실제 궁금증이 그대로 남아 있어서, 같은 텍스트라도 성격이 다르다.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from naver_insight.eda import charts
from naver_insight.eda import text as textmod
from naver_insight.insights import render_headline
from naver_insight.specs import terms_by_query

from . import _common as C

QUESTION = "뭐라고 이야기할까?"


def _nouns(data: dict[str, pd.DataFrame], services: list[str], query: str | None = None) -> pd.Series:
    parts = []
    for s in services:
        d = data.get(s)
        if d is None or "noun_str" not in d:
            continue
        sub = d if query is None else d[d["query"] == query]
        if not sub.empty:
            parts.append(sub["noun_str"])
    return pd.concat(parts, ignore_index=True) if parts else pd.Series(dtype=object)


def overlap_table(data: dict[str, pd.DataFrame], services: list[str],
                  queries: list[str], top_n: int = 30) -> tuple[list[str], pd.DataFrame]:
    """검색어별 상위 명사에서 공통 키워드와 고유 키워드를 갈라낸다."""
    sets: dict[str, list[str]] = {}
    for q in queries:
        terms = textmod.top_terms(_nouns(data, services, q), top_n)
        if not terms.empty:
            sets[q] = terms["term"].tolist()
    if len(sets) < 2:
        return [], pd.DataFrame()

    common = set.intersection(*(set(v) for v in sets.values()))
    ordered_common = [t for t in next(iter(sets.values())) if t in common]

    rows = {}
    for q, terms in sets.items():
        only = [t for t in terms if t not in common]
        rows[q] = pd.Series(only, dtype=object)
    uniq = pd.DataFrame(rows)
    uniq.insert(0, "순위", range(1, len(uniq) + 1))
    return ordered_common, uniq


def _answer(data: dict[str, pd.DataFrame], services: list[str], queries: list[str]) -> str:
    top = textmod.top_terms(_nouns(data, services), 8)
    if top.empty:
        return "명사를 뽑지 못했습니다."
    words = ", ".join(top["term"].tolist()[:6])
    msg = f"전 채널에서 가장 자주 나오는 말은 <b>{words}</b> 입니다."
    if len(queries) >= 2:
        common, _ = overlap_table(data, services, queries)
        if common:
            msg += f" 검색어들이 공유하는 말은 {len(common)}개이고, 대표적으로 {', '.join(common[:4])} 입니다."
        else:
            msg += " 검색어들이 공유하는 상위 키워드는 없습니다. 서로 다른 맥락에서 쓰입니다."
    return msg


def render() -> None:
    st.subheader("🔑 연관 키워드")
    st.caption("제목과 본문에서 명사만 뽑아 셉니다. 사람들이 실제로 쓰는 말을 봅니다.")

    data = C.need_search()
    if data is None:
        return

    services = C.text_services(data)
    if not services:
        st.info("텍스트가 있는 채널(뉴스·블로그·웹문서·지식iN·카페글·백과사전)을 수집해주세요.")
        return

    queries = C.all_queries({s: data[s] for s in services})
    render_headline(QUESTION, _answer(data, services, queries))
    C.caption_period()

    pick = st.multiselect("포함할 채널", services, default=services,
                          format_func=C.icon_label, key="kw_svcs")
    if not pick:
        st.info("채널을 하나 이상 골라주세요.")
        return

    nouns = _nouns(data, pick)
    if nouns.empty:
        st.info("선택한 채널에 명사 데이터가 없습니다.")
        return

    top20 = textmod.top_terms(nouns, 20)
    k = st.columns(3)
    k[0].metric("분석한 문서", f"{sum(len(data[s]) for s in pick):,}")
    k[1].metric("고유 명사 수", f"{textmod.top_terms(nouns, 100000).shape[0]:,}")
    k[2].metric("가장 많이 쓰인 말", str(top20.iloc[0]["term"]),
                f"{int(top20.iloc[0]['count']):,}회", delta_color="off")

    # ── 헤드라인 그래프 ──────────────────────────────────────
    kw_view = st.radio("키워드 시각화", ["가로 막대 차트", "키워드 트리맵 (비중 시각화)"],
                       horizontal=True, key="kw_chart_type")
    if kw_view == "가로 막대 차트":
        st.plotly_chart(
            charts.bar(top20.iloc[::-1], "count", "term", "가장 많이 쓰인 말 20개",
                       orientation="h"),
            width="stretch",
        )
    else:
        st.plotly_chart(
            charts.treemap(top20, path=["term"], values="count",
                           title="가장 많이 쓰인 핵심 키워드 트리맵"),
            width="stretch",
        )

    # ── 근거 ────────────────────────────────────────────────
    st.markdown("#### 근거")

    st.caption("두 단어가 나란히 붙어 나온 조합입니다. 한 단어보다 맥락이 잘 보입니다.")
    st.plotly_chart(
        charts.bar(textmod.top_ngrams(nouns, 2, 20).iloc[::-1], "count", "bigram",
                   "자주 붙어 나오는 두 단어 20개", orientation="h"),
        width="stretch",
    )

    if len(queries) >= 2:
        common, uniq = overlap_table(data, pick, queries)
        st.markdown("**검색어끼리 겹치는 말과 갈리는 말**")
        if common:
            st.success("공통 키워드 · " + ", ".join(common), icon="🤝")
        else:
            st.warning("상위 30개 안에서 겹치는 말이 없습니다.", icon="↔️")
        if not uniq.empty:
            st.caption("아래는 그 검색어에서만 나오는 말입니다. 검색어의 성격 차이가 여기서 드러납니다.")
            st.dataframe(uniq, width="stretch", hide_index=True)

    # ── 지식iN: 사람들의 실제 질문 ──────────────────────────
    kin = data.get("kin")
    if kin is not None and not kin.empty:
        st.markdown("**❓ 사람들이 실제로 던진 질문 (지식iN)**")
        st.caption(
            "지식iN 제목은 홍보 글이 아니라 결정 직전의 궁금증입니다. "
            "다른 채널에서는 안 보이는 정보라 따로 뽑았습니다."
        )
        q_pick = st.selectbox("검색어", ["전체"] + list(kin["query"].unique()), key="kw_kin_q")
        sub = kin if q_pick == "전체" else kin[kin["query"] == q_pick]
        cols = [c for c in ("query", "title_clean", "desc_clean", "link") if c in sub.columns]
        st.dataframe(
            sub[cols].head(200).rename(columns={
                "query": "검색어", "title_clean": "질문", "desc_clean": "내용", "link": "링크",
            }),
            width="stretch", hide_index=True,
            column_config={"링크": st.column_config.LinkColumn("링크", display_text="열기")},
        )

    with C.evidence("표로 보기"):
        st.markdown("**검색어별 상위 명사 20**")
        st.dataframe(terms_by_query(pd.concat([data[s] for s in pick], ignore_index=True), 20, 1),
                     width="stretch", hide_index=True)
        st.markdown("**함께 등장한 명사쌍 25**")
        st.dataframe(textmod.cooccurrence(nouns, 25), width="stretch", hide_index=True)
