"""🗂️ 원자료 — "직접 확인하고 싶다"

앞의 여섯 페이지는 질문 하나에 답 하나를 말한다. 이 페이지는 그 서랍이다.
채널을 골라 기존 탐색기(영역 -> 그래프 -> 표)를 그대로 쓰고, 이미지·지역처럼
질문 서사에 안 들어가는 전용 분석도 여기 남는다.

내려받기는 CSV 하나만 둔다. 엑셀 내보내기와 지역 지도는 사용자가 예전에 빼기로
결정한 기능이라 되살리지 않는다.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from naver_insight.render import render_service_tab
from naver_insight.specs import build_specs

from . import _common as C

_LOCAL_BANNER = (
    "네이버 지역 검색 API 는 검색어당 최대 5건만 돌려줍니다(공식 제약). "
    "지역·업종 통계는 표본이 작은 참고치이며, 네이버 검색 API 에는 "
    "'검색어별 지역 검색량' 데이터가 없습니다."
)


def _download_csv(service: str, df: pd.DataFrame) -> None:
    """지금 보고 있는 채널을 CSV 로 내려받는다.

    `noun_str` 은 형태소 분석 중간 산출물이라 파일에서는 뺀다.
    엑셀로 열 때 한글이 깨지지 않도록 BOM 을 붙인 utf-8-sig 로 쓴다.
    """
    st.markdown("#### 내려받기")
    body = df.drop(columns=[c for c in ("noun_str",) if c in df.columns])
    st.download_button(
        f"📄 {C.label_of(service)} CSV 내려받기 ({len(df):,}행)",
        body.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{service}.csv",
        mime="text/csv",
        width="stretch",
    )


def render() -> None:
    st.subheader("🗂️ 원자료")
    st.caption(
        "채널을 골라 원래의 상세 분석과 원본 데이터를 봅니다. "
        "이미지 해상도나 지역 업종처럼 앞 페이지에 안 들어가는 분석도 여기 있습니다."
    )

    data = C.need_search()
    if data is None:
        return

    service = st.selectbox("채널", list(data), format_func=C.icon_label, key="raw_svc")
    df = data[service]

    chart_specs, table_specs = build_specs(service, df)
    render_service_tab(
        service, C.label_of(service), df, C.meta(), chart_specs, table_specs,
        banner=_LOCAL_BANNER if service == "local" else None,
    )

    st.divider()
    _download_csv(service, df)
