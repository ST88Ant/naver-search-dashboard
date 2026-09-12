"""서비스 상세(탭) 공용 렌더러.

각 탭은 '차트 스펙'과 '표 스펙' 목록만 정의하고, UI(요약 박스, 그래프 셀렉터,
표 셀렉터, 기술통계, 원자료)는 여기서 그린다.

성능: 탭 UI 는 매 rerun 마다 모든 탭을 다시 실행하므로
  · 선택된 그래프/표 1개씩만 렌더 (모아보기 없음)
  · 집계는 stats/insights 의 캐시에 의존
  · 위젯 key 는 서비스별 prefix 로 분리
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd
import streamlit as st

from .eda import features, stats
from .insights import render_summary_box, service_summary

Frame = pd.DataFrame


@dataclass(frozen=True)
class ChartSpec:
    key: str
    label: str
    section: str
    build: Callable[[Frame], object]
    help: str = ""


@dataclass(frozen=True)
class TableSpec:
    key: str
    label: str
    build: Callable[[Frame], Frame]
    help: str = ""


def page_header(service: str, label: str, df: Frame, meta: dict, *, banner: str | None = None) -> bool:
    st.subheader(f"{label} 상세 분석")
    if banner:
        st.caption("⚠️ " + banner)
    if df is None or df.empty:
        st.info("사이드바에서 검색어·기간을 입력하고 **🚀 수집 실행** 을 누르면 채워집니다.")
        return False

    render_summary_box(service_summary(service, df))

    c = st.columns(4)
    c[0].metric("수집 건수", f"{len(df):,}")
    c[1].metric("검색어 수", df["query"].nunique() if "query" in df else 0)
    if "total_len" in df:
        c[2].metric("평균 텍스트 길이", f"{df['total_len'].mean():.0f}자")
    if "domain" in df and df["domain"].ne("(없음)").any():
        c[3].metric("고유 출처(도메인)", df["domain"].nunique())
    elif "date" in df and df["date"].notna().any():
        c[3].metric("문서 기간", f"{df['date'].min():%y-%m-%d} ~ {df['date'].max():%y-%m-%d}")
    return True


def describe_block(service: str, df: Frame, prefix: str) -> None:
    cols = features.numeric_features(service, df)
    if not cols:
        return
    with st.expander("📐 기술통계", expanded=False):
        mode = st.radio("보기", ["전체", "검색어별 평균"], horizontal=True, key=f"{prefix}_desc_mode")
        by = "query" if mode == "검색어별 평균" else None
        st.dataframe(stats.describe(df, cols, by), width="stretch", hide_index=True)


def chart_explorer(df: Frame, specs: list[ChartSpec], prefix: str) -> None:
    if not specs:
        return
    st.markdown("#### 그래프")
    sections = list(dict.fromkeys(s.section for s in specs))
    col_a, col_b = st.columns([1, 2])
    with col_a:
        section = st.radio("분석 영역", sections, key=f"{prefix}_sec")
    in_section = [s for s in specs if s.section == section]
    with col_b:
        chosen = st.selectbox("그래프 선택", [s.label for s in in_section], key=f"{prefix}_chart")
    spec = next(s for s in in_section if s.label == chosen)
    if spec.help:
        st.caption(spec.help)
    try:
        st.plotly_chart(spec.build(df), width="stretch", key=f"{prefix}_fig")
    except Exception as exc:  # noqa: BLE001
        st.error(f"그래프 오류: {exc}")


def table_explorer(df: Frame, specs: list[TableSpec], prefix: str) -> None:
    if not specs:
        return
    st.markdown("#### 통계표")
    st.caption("검색어별 요약")
    st.dataframe(stats.value_summary(df), width="stretch", hide_index=True)

    chosen = st.selectbox("표 선택", [s.label for s in specs], key=f"{prefix}_table")
    spec = next(s for s in specs if s.label == chosen)
    if spec.help:
        st.caption(spec.help)
    try:
        out = spec.build(df)
    except Exception as exc:  # noqa: BLE001
        st.error(f"표 오류: {exc}")
        return
    if out is None or len(out) == 0:
        st.info("이 조건에서는 표에 담을 데이터가 없습니다.")
        return
    st.dataframe(out, width="stretch", hide_index=True)


def raw_block(df: Frame, prefix: str) -> None:
    with st.expander("🗂️ 원자료 보기", expanded=False):
        prefer = ["query", "date", "title_clean", "desc_clean", "category", "address",
                  "roadAddress", "telephone", "domain", "bloggername", "cafename",
                  "img_w", "img_h", "img_orientation", "link"]
        cols = [c for c in prefer if c in df.columns]
        cols += [c for c in df.columns if c not in cols and c != "noun_str"]
        st.dataframe(
            df[cols].head(500), width="stretch", hide_index=True,
            column_config={"link": st.column_config.LinkColumn("link")},
        )


def render_service_tab(
    service: str,
    label: str,
    df: Frame,
    meta: dict,
    chart_specs: list[ChartSpec],
    table_specs: list[TableSpec],
    *,
    banner: str | None = None,
    pre_charts: Callable[[Frame], None] | None = None,
) -> None:
    prefix = f"svc_{service}"
    if not page_header(service, label, df, meta, banner=banner):
        return
    if pre_charts is not None:
        pre_charts(df)
    chart_explorer(df, chart_specs, prefix)
    describe_block(service, df, prefix)
    st.divider()
    table_explorer(df, table_specs, prefix)
    raw_block(df, prefix)
