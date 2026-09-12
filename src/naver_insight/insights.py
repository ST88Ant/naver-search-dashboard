"""자동 요약 — 각 서비스 데이터에서 규모·경향·핵심어를 3줄로 뽑아낸다.

규칙 기반(형태소·집계 결과를 문장으로 조립). 캐시된다.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .eda import text as textmod

_cache = st.cache_data(show_spinner=False, ttl=1800)


def _share_phrase(df: pd.DataFrame, col: str = "query", n: int = 2) -> str:
    vc = df[col].value_counts()
    total = len(df)
    parts = [f"'{k}' {v / total * 100:.0f}%" for k, v in vc.head(n).items()]
    return " · ".join(parts)


def _top_terms_phrase(df: pd.DataFrame, n: int = 6) -> str:
    if "noun_str" not in df:
        return ""
    terms = textmod.top_terms(df["noun_str"], n)
    return ", ".join(terms["term"].tolist())


@_cache
def service_summary(service: str, df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return []
    total = len(df)
    n_q = df["query"].nunique() if "query" in df else 0
    lines: list[str] = []

    # 1) 규모
    lines.append(f"📦 총 **{total:,}건**({n_q}개 검색어) 수집 — {_share_phrase(df)}")

    # 2) 경향 (서비스별)
    if service == "image" and "img_megapixels" in df:
        mp = df["img_megapixels"].median()
        orient = df["img_orientation"].mode()
        o = orient.iloc[0] if not orient.empty else "-"
        o_pct = (df["img_orientation"] == o).mean() * 100
        lines.append(f"🖼️ 화소수 중앙값 **{mp:.1f}MP**, **{o}** 이미지가 {o_pct:.0f}%")
    elif service == "local" and "region" in df:
        reg = df["region"].mode()
        cat = df["category_top"].mode()
        r = reg.iloc[0] if not reg.empty else "-"
        c = cat.iloc[0] if not cat.empty else "-"
        lines.append(f"📍 최다 지역 **{r}**({(df['region'] == r).sum()}곳), 주요 업종 **{c}**")
    elif "date" in df and df["date"].notna().any():
        d = df.dropna(subset=["date"])
        recent = (d["days_ago"] <= 7).mean() * 100 if "days_ago" in d else 0
        wd = d["weekday"].mode()
        wday = wd.iloc[0] if not wd.empty else "-"
        lines.append(
            f"🗓️ 최근 7일 문서 비중 **{recent:.0f}%**, **{wday}요일** 발행 최다"
        )
    elif "domain" in df and df["domain"].ne("(없음)").any():
        vc = df[df["domain"] != "(없음)"]["domain"].value_counts()
        top3 = vc.head(3)
        share = top3.sum() / len(df) * 100
        lines.append(
            f"🌐 출처 상위 3곳(**{', '.join(top3.index[:3])}**)이 전체의 {share:.0f}% 집중"
        )
    else:
        avg_len = df["total_len"].mean() if "total_len" in df else 0
        lines.append(f"📝 문서당 평균 텍스트 길이 **{avg_len:.0f}자**")

    # 3) 핵심어
    kw = _top_terms_phrase(df)
    if kw:
        lines.append(f"🔑 핵심어: **{kw}**")

    return lines


@_cache
def compare_summary(long: pd.DataFrame) -> list[str]:
    if long is None or long.empty:
        return []
    lines = []
    by_q = long.groupby("검색어")["수집건수"].sum().sort_values(ascending=False)
    lines.append(f"📊 총 노출 {int(by_q.sum()):,}건 — 최다 검색어 **'{by_q.index[0]}'**({int(by_q.iloc[0]):,}건)")
    by_s = long.groupby("서비스")["수집건수"].sum().sort_values(ascending=False)
    lines.append(f"🧭 서비스별로는 **{by_s.index[0]}**({int(by_s.iloc[0]):,}건) → {by_s.index[1] if len(by_s) > 1 else ''} 순")
    piv = long.pivot_table(index="검색어", columns="서비스", values="수집건수", fill_value=0)
    skew = (piv.max(axis=1) / piv.sum(axis=1).replace(0, 1)).sort_values(ascending=False)
    lines.append(f"⚖️ **'{skew.index[0]}'** 은(는) 특정 서비스 편중이 가장 큼(최대 채널 {skew.iloc[0] * 100:.0f}%)")
    return lines


@_cache
def trend_summary(trend: pd.DataFrame) -> list[str]:
    if trend is None or trend.empty:
        return []
    lines = []
    mean_by = trend.groupby("group")["ratio"].mean().sort_values(ascending=False)
    lines.append(f"📈 기간 평균 상대 검색량 1위 **'{mean_by.index[0]}'**({mean_by.iloc[0]:.0f})")
    std_by = trend.groupby("group")["ratio"].std().sort_values(ascending=False)
    lines.append(f"🌊 변동이 가장 큰 검색어는 **'{std_by.index[0]}'**(표준편차 {std_by.iloc[0]:.0f})")
    last = trend.sort_values("period").groupby("group").tail(1).set_index("group")["ratio"]
    first = trend.sort_values("period").groupby("group").head(1).set_index("group")["ratio"]
    delta = (last - first).sort_values(ascending=False)
    up = delta.index[0]
    lines.append(f"↗️ 기간 초→말 상승폭 최대 **'{up}'**({delta.iloc[0]:+.0f})")
    return lines


def render_summary_box(lines: list[str]) -> None:
    """요약을 상단 박스로 출력 (근거 층)."""
    import streamlit as st  # noqa: PLC0415

    if not lines:
        return
    st.markdown(
        "<div style='background:#fbeaf1;border-left:4px solid #d3508e;"
        "padding:0.75rem 1rem;border-radius:12px;margin-bottom:0.6rem;"
        "line-height:1.7'>"
        + "<br>".join(lines) + "</div>",
        unsafe_allow_html=True,
    )


def render_headline(question: str, answer: str) -> None:
    """페이지 맨 위 '질문 -> 한 문장 답' 카드.

    각 페이지는 답 하나만 크게 말하고, 근거는 그 아래로 내린다.
    """
    import streamlit as st  # noqa: PLC0415

    st.markdown(
        "<div style='background:linear-gradient(135deg,#fbeaf1 0%,#fdf3f7 100%);"
        "border:1px solid #f3dbe5;border-radius:16px;padding:1rem 1.25rem;"
        "margin-bottom:0.9rem'>"
        f"<div style='color:#8f1357;font-size:0.82rem;font-weight:600;"
        f"letter-spacing:0.02em;margin-bottom:0.35rem'>{question}</div>"
        f"<div style='color:#2b2430;font-size:1.15rem;font-weight:600;"
        f"line-height:1.55'>{answer}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_empty(message: str) -> None:
    """수집 전/데이터 없음 안내 (모든 페이지 공통 톤)."""
    import streamlit as st  # noqa: PLC0415

    st.markdown(
        "<div style='background:#fdf3f7;border:1px dashed #edc3d7;border-radius:16px;"
        "padding:1.6rem 1.25rem;text-align:center;color:#6b6570;line-height:1.7'>"
        + message + "</div>",
        unsafe_allow_html=True,
    )
