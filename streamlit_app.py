"""네이버 검색 인사이트 대시보드 — 진입점.

실행:  uv run streamlit run streamlit_app.py

화면 구성
---------
페이지를 데이터 소스가 아니라 **질문 순서**로 배열한다. 앞에서 뒤로 읽으면
"얼마나 찾나 → 누가 찾나 → 얼마나 쓰였나 → 어디서 → 뭐라고 → 그래서 쓸 만한가"
가 하나의 이야기가 된다. 마지막 원자료 페이지는 그 서사에 안 들어가는 상세
분석을 담는 서랍이다.

st.tabs 가 아니라 st.navigation 을 쓰는 이유
-------------------------------------------
st.tabs 는 화면만 나눌 뿐 코드는 전부 실행된다. 탭이 11개면 위젯을 하나 누를
때마다 11개 탭의 표와 그래프가 모두 다시 그려진다(접힌 expander 안까지).
st.navigation 은 선택된 페이지 하나만 실행하므로, 페이지마다 결론과 근거를
넉넉히 펼쳐놓아도 매 실행 비용이 그 페이지 분량에 머문다.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from naver_insight import NaverApiError, NaverApiHubClient, load_settings  # noqa: E402
from naver_insight.client import AGE_LABELS, SEARCH_SERVICES  # noqa: E402
from naver_insight.collectors import collect_all  # noqa: E402
from naver_insight.eda import features, stats  # noqa: E402
from views import (  # noqa: E402
    demographics,
    interest,
    keywords,
    opportunity,
    rawdata,
    sources,
    volume,
)

st.set_page_config(
    page_title="네이버 검색 인사이트",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded",
)

MIN_DATE = date(2016, 1, 1)
TODAY = date.today()


# ─────────────────────────────────────────────────────────────
# 파이프라인 (수집 → 파생 피처) — 캐시
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=1800)
def run_pipeline(
    creds: tuple[str, str, str],
    queries: tuple[str, ...],
    services: tuple[str, ...],
    max_results: int,
    sort: str,
    image_filter: str,
    use_period: bool,
    start_date: date,
    end_date: date,
) -> dict[str, pd.DataFrame]:
    client = NaverApiHubClient(creds[0], creds[1], base_url=creds[2])
    raw = collect_all(
        client, list(queries), list(services),
        max_results=max_results, sort=sort,
        start_date=start_date if use_period else None,
        end_date=end_date if use_period else None,
        image_filter=image_filter,
    )
    return {svc: features.add_features(svc, df) for svc, df in raw.items()}


@st.cache_data(show_spinner=False, ttl=1800)
def run_trend(
    creds: tuple[str, str, str],
    queries: tuple[str, ...],
    start_date: date,
    end_date: date,
    time_unit: str,
    device: str,
    gender: str,
    ages: tuple[str, ...],
) -> pd.DataFrame:
    client = NaverApiHubClient(creds[0], creds[1], base_url=creds[2])
    groups = [{"groupName": q, "keywords": [q]} for q in queries[:5]]
    resp = client.search_trend(
        start_date.isoformat(), end_date.isoformat(), groups,
        time_unit=time_unit, device=device or None, gender=gender or None,
        ages=list(ages) or None,
    )
    return stats.trend_to_frame(resp)


# ─────────────────────────────────────────────────────────────
# 사이드바 — 입력 (모든 페이지에서 동일하게 뜬다)
# ─────────────────────────────────────────────────────────────
settings = load_settings()
st.sidebar.title("🌸 검색 조건")

with st.sidebar.expander("🔑 API 인증 설정", expanded=not settings.is_complete):
    if settings.is_complete:
        st.success("🔒 API 인증 완료 (서버 설정 사용)")
        st.caption("보안을 위해 실제 API 키는 화면 및 브라우저에 노출되지 않습니다.")
        override = st.checkbox("다른 API Key 직접 입력", value=False)
        if override:
            cid_input = st.text_input("API Key ID", value="", type="password", placeholder="새로운 API Key ID 입력")
            csec_input = st.text_input("API Key", value="", type="password", placeholder="새로운 API Key 입력")
            cid = cid_input.strip() if cid_input.strip() else settings.client_id
            csec = csec_input.strip() if csec_input.strip() else settings.client_secret
        else:
            cid = settings.client_id
            csec = settings.client_secret
    else:
        st.warning("⚠️ 등록된 API Key가 없습니다. .env 또는 Streamlit Secrets를 설정하거나 아래에 직접 입력하세요.")
        cid = st.text_input("API Key ID", value="", type="password", placeholder="API Key ID를 입력하세요")
        csec = st.text_input("API Key", value="", type="password", placeholder="API Key를 입력하세요")

creds = (cid.strip(), csec.strip(), settings.base_url)

raw_queries = st.sidebar.text_input("검색어 (쉼표로 구분)", value="챗GPT, 클로드, 제미나이",
                                    help="예: 챗GPT, 클로드, 제미나이")
queries = list(dict.fromkeys(q.strip() for q in raw_queries.split(",") if q.strip()))

st.sidebar.markdown("**기간**")
c1, c2 = st.sidebar.columns(2)
start_date = c1.date_input("시작일", value=TODAY - timedelta(days=90),
                           min_value=MIN_DATE, max_value=TODAY)
end_date = c2.date_input("종료일", value=TODAY, min_value=MIN_DATE, max_value=TODAY)
use_period = st.sidebar.checkbox(
    "기간 필터 적용 (뉴스·블로그 + 검색어 트렌드)", value=True,
    help="검색 API 에는 날짜 파라미터가 없어, 날짜 필드가 있는 뉴스·블로그에만 수집 후 "
         "기간 필터를 적용합니다. 트렌드 API 는 항상 이 기간을 사용합니다.",
)

selected_services = st.sidebar.multiselect(
    "수집할 채널", options=list(SEARCH_SERVICES.keys()),
    default=list(SEARCH_SERVICES.keys()), format_func=lambda s: SEARCH_SERVICES[s],
)
max_results = st.sidebar.slider("채널·검색어당 수집 건수", 20, 1000, 200, step=20,
                                help="값이 클수록 수집이 느립니다. 지역(local)은 최대 5건.")
sort = "date" if st.sidebar.selectbox(
    "정렬", ["정확도순 (sim)", "최신순 (date)"]).startswith("최신") else "sim"
image_filter = st.sidebar.selectbox("이미지 크기 필터", ["all", "large", "medium", "small"])

with st.sidebar.expander("📈 검색어 트렌드 옵션"):
    tu_label = st.selectbox("집계 단위", ["일간 (date)", "주간 (week)", "월간 (month)"])
    time_unit = {"일": "date", "주": "week", "월": "month"}[tu_label[0]]
    device = {"전체": "", "PC": "pc", "모바일": "mo"}[st.selectbox("기기", ["전체", "PC", "모바일"])]
    gender = {"전체": "", "남성": "m", "여성": "f"}[st.selectbox("성별", ["전체", "남성", "여성"])]
    ages = st.multiselect("연령대", options=list(AGE_LABELS.keys()),
                          format_func=lambda a: f"{a} ({AGE_LABELS[a]})")

# 성별·연령 페이지가 자기 힘으로 추가 호출을 할 수 있게 재료를 남겨둔다
st.session_state["creds"] = creds
st.session_state["trend_params"] = {
    "queries": queries,
    "start": start_date.isoformat(),
    "end": end_date.isoformat(),
}

if st.sidebar.button("🚀 수집 실행", type="primary", width="stretch"):
    if not (creds[0] and creds[1]):
        st.sidebar.error("API Key ID / API Key 를 입력하세요.")
    elif not queries:
        st.sidebar.error("검색어를 1개 이상 입력하세요.")
    elif start_date > end_date:
        st.sidebar.error("시작일이 종료일보다 뒤입니다.")
    else:
        st.session_state.pop("splits", None)  # 조건이 바뀌면 세그먼트 결과는 무효
        try:
            with st.spinner(
                f"수집·분석 중… ({len(selected_services)}개 채널 × {len(queries)}개 검색어)"
            ):
                st.session_state["enriched"] = run_pipeline(
                    creds, tuple(queries), tuple(selected_services),
                    max_results, sort, image_filter, use_period, start_date, end_date,
                )
                st.session_state["meta"] = {
                    "queries": queries, "start": start_date, "end": end_date,
                    "use_period": use_period,
                }
        except NaverApiError as exc:
            st.sidebar.error(f"검색 API 오류: {exc}")
        try:
            with st.spinner("검색어 트렌드 수집 중…"):
                st.session_state["trend"] = run_trend(
                    creds, tuple(queries), start_date, end_date,
                    time_unit, device, gender, tuple(ages),
                )
            if len(queries) > 5:
                st.sidebar.info("트렌드는 최대 5개 검색어만 조회했습니다.")
        except NaverApiError as exc:
            st.session_state["trend"] = pd.DataFrame()
            st.sidebar.warning(f"트렌드 API 오류: {exc}")

st.sidebar.caption("데이터는 세션에 캐시됩니다. 조건을 바꾸면 다시 **🚀 수집 실행**.")


# ─────────────────────────────────────────────────────────────
# 페이지 — 질문 순서
# ─────────────────────────────────────────────────────────────
PAGES = [
    st.Page(interest.render, title="검색 관심도", icon="📈",
            url_path="interest", default=True),
    st.Page(demographics.render, title="성별·연령 분석", icon="👥", url_path="who"),
    st.Page(volume.render, title="채널별 언급량", icon="💬", url_path="volume"),
    st.Page(sources.render, title="출처 분석", icon="🌐", url_path="sources"),
    st.Page(keywords.render, title="연관 키워드", icon="🔑", url_path="keywords"),
    st.Page(opportunity.render, title="키워드 기회", icon="💡", url_path="opportunity"),
    st.Page(rawdata.render, title="원자료", icon="🗂️", url_path="raw"),
]

st.navigation(PAGES, position="top").run()
