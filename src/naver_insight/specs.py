"""서비스별 차트·표 스펙 정의.

`render.render_service_tab` 에 넘길 ChartSpec / TableSpec 목록을 만든다.
"""

from __future__ import annotations

import pandas as pd

from .eda import charts, stats
from .eda import text as textmod
from .render import ChartSpec, TableSpec

WEEKDAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]


# ── 공용 집계 헬퍼 ──────────────────────────────────────────


def _noun_lists(df: pd.DataFrame) -> pd.Series:
    """명사 문자열(noun_str) Series. text 헬퍼들이 split 해서 사용."""
    if "noun_str" in df:
        return df["noun_str"]
    combined = (df.get("title_clean", "") + " " + df.get("desc_clean", "")).astype(str)
    return textmod.noun_str_series(combined)


def terms_by_query(df: pd.DataFrame, n: int = 20, ngram: int = 1) -> pd.DataFrame:
    """검색어별 상위 (n-gram) 용어를 'rank | 검색어A | 검색어B ...' 표로."""
    out = {}
    for q, part in df.groupby("query"):
        nl = _noun_lists(part)
        tbl = (
            textmod.top_terms(nl, n) if ngram == 1
            else textmod.top_ngrams(nl, ngram, n)
        )
        col = tbl.iloc[:, 0].astype(str) + " (" + tbl["count"].astype(str) + ")"
        out[str(q)] = col.reset_index(drop=True)
    res = pd.DataFrame(out)
    res.insert(0, "순위", range(1, len(res) + 1))
    return res


def title_feature_rates(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("query")
    return pd.DataFrame({
        "검색어": g.size().index,
        "건수": g.size().values,
        "숫자포함%": (g["title_has_num"].mean() * 100).round(1).values,
        "영문포함%": (g["title_has_eng"].mean() * 100).round(1).values,
        "괄호·기호%": (g["title_has_bracket"].mean() * 100).round(1).values,
        "평균제목길이": g["title_len"].mean().round(1).values,
    })


def domain_agg(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if "domain" not in df:
        return pd.DataFrame()
    keep = df["domain"].value_counts().head(top_n).index
    sub = df[df["domain"].isin(keep)]
    g = sub.groupby("domain")
    res = pd.DataFrame({
        "도메인": g.size().index,
        "건수": g.size().values,
        "검색어수": g["query"].nunique().values,
        "평균길이": g["total_len"].mean().round(1).values if "total_len" in df else None,
    }).sort_values("건수", ascending=False)
    return res


def _weekday_counts(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=["weekday"])
    g = d.groupby(["weekday", "query"]).size().reset_index(name="count")
    g["weekday"] = pd.Categorical(g["weekday"], categories=WEEKDAY_ORDER, ordered=True)
    return g.sort_values("weekday")


def _hour_counts(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=["hour"])
    return d.groupby(["hour", "query"]).size().reset_index(name="count")


# ── 텍스트형 서비스 (뉴스·블로그·웹문서·지식iN·카페글·백과사전) ──


def text_charts(service: str, df: pd.DataFrame) -> list[ChartSpec]:
    has_date = "date" in df and df["date"].notna().any()
    specs: list[ChartSpec] = [
        ChartSpec("cnt", "검색어별 수집 건수", "텍스트",
                  lambda d: charts.bar(d.groupby("query").size().reset_index(name="건수"),
                                       "query", "건수", "검색어별 수집 건수", color="query")),
        ChartSpec("len_hist", "텍스트 길이 분포(히스토그램)", "텍스트",
                  lambda d: charts.histogram(d, "total_len", "제목+본문 길이 분포", color="query")),
        ChartSpec("len_box", "검색어별 텍스트 길이(박스플롯)", "텍스트",
                  lambda d: charts.box(d, "query", "total_len", "검색어별 텍스트 길이 분포")),
        ChartSpec("scatter_len", "제목 길이 vs 본문 길이", "텍스트",
                  lambda d: charts.scatter(d, "title_len", "desc_len", "제목·본문 길이 관계",
                                           color="query")),
        ChartSpec("nouns", "상위 명사 빈도", "텍스트",
                  lambda d: charts.bar(textmod.top_terms(_noun_lists(d), 20).iloc[::-1],
                                       "count", "term", "상위 명사 20", orientation="h")),
        ChartSpec("bigram", "상위 2-gram(연속 명사쌍)", "텍스트",
                  lambda d: charts.bar(textmod.top_ngrams(_noun_lists(d), 2, 20).iloc[::-1],
                                       "count", "bigram", "상위 bigram 20", orientation="h")),
        ChartSpec("noun_ecdf", "문서당 명사 수 누적분포(ECDF)", "텍스트",
                  lambda d: charts.ecdf(d, "noun_cnt", "문서당 명사 수 ECDF", color="query")),
        ChartSpec("title_feat", "제목 특성 비율(숫자·영문·기호)", "텍스트",
                  lambda d: charts.stacked_bar(
                      title_feature_rates(d).melt("검색어", ["숫자포함%", "영문포함%", "괄호·기호%"],
                                                  var_name="특성", value_name="비율"),
                      "검색어", "비율", "특성", "제목 특성 구성", percent=False)),
        # 출처
        ChartSpec("dom_bar", "상위 출처 도메인", "출처",
                  lambda d: charts.bar(stats.category_counts(d, "domain", 20).iloc[::-1],
                                       "count", "domain", "상위 출처 도메인 20", orientation="h")),
        ChartSpec("dom_heat", "검색어 × 도메인 히트맵", "출처",
                  lambda d: charts.heatmap(stats.crosstab(d, "query", "domain", top_col=12, margins=False),
                                           "검색어 × 도메인 문서 수", index_col="query")),
        ChartSpec("dom_div", "검색어별 고유 도메인 수", "출처",
                  lambda d: charts.bar(stats.domain_diversity(d), "query", "고유도메인",
                                       "검색어별 출처 다양성", color="query")),
        ChartSpec("tld", "상위 TLD 분포", "출처",
                  lambda d: charts.bar(stats.category_counts(d, "tld", 12), "tld", "count",
                                       "최상위도메인(TLD) 분포")),
        ChartSpec("dom_tree", "출처 구성 트리맵", "출처",
                  lambda d: charts.treemap(
                      stats.category_counts(d, "domain", 30, group="query"),
                      ["query", "domain"], "count", "검색어 → 도메인 구성")),
        # 교차
        ChartSpec("len_cross", "길이 구간 × 검색어 히트맵", "교차",
                  lambda d: charts.heatmap(stats.pivot(d, "len_bucket", "query"),
                                           "텍스트 길이 구간 × 검색어", index_col="len_bucket")),
    ]
    if has_date:
        specs += [
            ChartSpec("ts_day", "일자별 문서 수", "시간",
                      lambda d: charts.line(stats.daily_counts(d, "D"), "date", "count", "query",
                                            "일자별 문서 수", y_title="문서 수")),
            ChartSpec("ts_week", "주간 문서 수", "시간",
                      lambda d: charts.area(stats.daily_counts(d, "W"), "date", "count", "query",
                                            "주간 문서 수", y_title="문서 수")),
            ChartSpec("wday", "요일별 문서 수", "시간",
                      lambda d: charts.bar(_weekday_counts(d), "weekday", "count",
                                           "요일별 문서 수", color="query")),
            ChartSpec("hour", "시간대별 문서 수", "시간",
                      lambda d: charts.bar(_hour_counts(d), "hour", "count",
                                           "시간대(0–23시)별 문서 수", color="query", sort=False)),
            ChartSpec("wday_heat", "검색어 × 요일 히트맵", "시간",
                      lambda d: charts.heatmap(
                          stats.pivot(d.assign(weekday=pd.Categorical(d["weekday"], WEEKDAY_ORDER, ordered=True)),
                                      "query", "weekday"),
                          "검색어 × 요일 문서 수", index_col="query")),
            ChartSpec("daysago", "발행 경과일 분포", "시간",
                      lambda d: charts.histogram(d, "days_ago", "발행 후 경과일 분포", color="query",
                                                 marginal="box")),
            ChartSpec("weekend", "주말/평일 × 검색어", "교차",
                      lambda d: charts.stacked_bar(
                          d.assign(구분=d["is_weekend"].map({True: "주말", False: "평일"}))
                           .groupby(["query", "구분"]).size().reset_index(name="count"),
                          "query", "count", "구분", "주말·평일 문서 비중", percent=True)),
        ]
    return specs


def text_tables(service: str, df: pd.DataFrame) -> list[TableSpec]:
    has_date = "date" in df and df["date"].notna().any()
    specs = [
        TableSpec("cross_domain", "교차표: 검색어 × 출처 도메인",
                  lambda d: stats.crosstab(d, "query", "domain", top_col=12),
                  help="값은 문서 수. '기타'는 상위 12개 외 도메인 합계."),
        TableSpec("cross_domain_pct", "교차표(%): 검색어 × 출처 도메인",
                  lambda d: stats.crosstab(d, "query", "domain", top_col=12, normalize="index")),
        TableSpec("pivot_len", "피봇: 길이 구간 × 검색어 (문서 수)",
                  lambda d: stats.pivot(d, "len_bucket", "query")),
        TableSpec("terms", "상위 명사 TOP 20 (검색어별)",
                  lambda d: terms_by_query(d, 20, 1)),
        TableSpec("bigrams", "상위 2-gram TOP 15 (검색어별)",
                  lambda d: terms_by_query(d, 15, 2)),
        TableSpec("cooc", "동시출현 명사쌍 TOP 25",
                  lambda d: textmod.cooccurrence(_noun_lists(d), 25)),
        TableSpec("domain_agg", "도메인별 집계 (건수·검색어수·평균길이)",
                  lambda d: domain_agg(d, 25)),
        TableSpec("title_feat", "검색어별 제목 특성 비율(%)",
                  lambda d: title_feature_rates(d)),
    ]
    if has_date:
        specs += [
            TableSpec("pivot_wday", "피봇: 요일 × 검색어 (문서 수)",
                      lambda d: stats.pivot(
                          d.assign(weekday=pd.Categorical(d["weekday"], WEEKDAY_ORDER, ordered=True)),
                          "weekday", "query")),
            TableSpec("pivot_month", "피봇: 월(year_month) × 검색어 (문서 수)",
                      lambda d: stats.pivot(d.dropna(subset=["year_month"]), "year_month", "query")),
            TableSpec("pivot_hour_mean", "피봇: 검색어 × 요일 평균 텍스트 길이",
                      lambda d: stats.pivot(d.dropna(subset=["weekday"]), "query", "weekday",
                                            values="total_len", aggfunc="mean")),
        ]
    return specs


# ── 이미지 ──────────────────────────────────────────────────


def image_charts(df: pd.DataFrame) -> list[ChartSpec]:
    return [
        ChartSpec("cnt", "검색어별 수집 건수", "크기",
                  lambda d: charts.bar(d.groupby("query").size().reset_index(name="건수"),
                                       "query", "건수", "검색어별 수집 건수", color="query")),
        ChartSpec("wh_hist", "가로·세로 픽셀 분포", "크기",
                  lambda d: charts.histogram(
                      d.melt("query", ["img_w", "img_h"], var_name="축", value_name="픽셀"),
                      "픽셀", "가로(img_w)·세로(img_h) 픽셀 분포", color="축", marginal="violin")),
        ChartSpec("res_scatter", "해상도 산점도 (가로×세로)", "크기",
                  lambda d: charts.scatter(d, "img_w", "img_h", "이미지 해상도 분포",
                                           color="query", size="img_megapixels", log_xy=True)),
        ChartSpec("aspect_hist", "종횡비 분포", "크기",
                  lambda d: charts.histogram(d[d["img_aspect"] < 5], "img_aspect",
                                             "가로/세로 비율 분포", color="query")),
        ChartSpec("mp_box", "검색어별 메가픽셀(박스플롯)", "크기",
                  lambda d: charts.box(d, "query", "img_megapixels", "검색어별 이미지 화소수(MP)")),
        ChartSpec("mp_ecdf", "메가픽셀 누적분포(ECDF)", "크기",
                  lambda d: charts.ecdf(d, "img_megapixels", "이미지 화소수 ECDF", color="query")),
        ChartSpec("orient", "방향 구성(가로/세로/정사각)", "구성",
                  lambda d: charts.stacked_bar(
                      d.groupby(["query", "img_orientation"]).size().reset_index(name="count"),
                      "query", "count", "img_orientation", "검색어별 이미지 방향 구성", percent=True)),
        ChartSpec("size_bucket", "크기 구간 분포", "구성",
                  lambda d: charts.bar(stats.category_counts(d, "img_size_bucket", 10),
                                       "img_size_bucket", "count", "이미지 크기 구간 분포", sort=False)),
        ChartSpec("size_heat", "크기 구간 × 검색어 히트맵", "구성",
                  lambda d: charts.heatmap(stats.pivot(d, "img_size_bucket", "query"),
                                           "크기 구간 × 검색어", index_col="img_size_bucket")),
        ChartSpec("dom_bar", "상위 출처 도메인", "출처",
                  lambda d: charts.bar(stats.category_counts(d, "domain", 20).iloc[::-1],
                                       "count", "domain", "이미지 출처 도메인 20", orientation="h")),
        ChartSpec("dom_heat", "검색어 × 도메인 히트맵", "출처",
                  lambda d: charts.heatmap(stats.crosstab(d, "query", "domain", top_col=12, margins=False),
                                           "검색어 × 도메인", index_col="query")),
    ]


def image_tables(df: pd.DataFrame) -> list[TableSpec]:
    return [
        TableSpec("size_desc", "검색어별 크기 기술통계",
                  lambda d: stats.describe(d, ["img_w", "img_h", "img_megapixels", "img_aspect"], by="query")),
        TableSpec("orient_cross", "교차표: 검색어 × 방향",
                  lambda d: stats.crosstab(d, "query", "img_orientation", top_col=5)),
        TableSpec("orient_pct", "교차표(%): 검색어 × 방향",
                  lambda d: stats.crosstab(d, "query", "img_orientation", top_col=5, normalize="index")),
        TableSpec("bucket_pivot", "피봇: 크기 구간 × 검색어",
                  lambda d: stats.pivot(d, "img_size_bucket", "query")),
        TableSpec("dom_agg", "도메인별 집계",
                  lambda d: domain_agg(d, 25)),
        TableSpec("aspect_pivot", "피봇: 검색어 × 방향 평균 종횡비",
                  lambda d: stats.pivot(d, "query", "img_orientation", values="img_aspect", aggfunc="mean")),
    ]


# ── 지역 ────────────────────────────────────────────────────


def _top_region(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for q, part in df.groupby("query"):
        sido = part["sido"].mode()
        sgg = part["region"].mode()
        rows.append({
            "검색어": q,
            "건수": len(part),
            "최다 시/도": sido.iloc[0] if not sido.empty else "-",
            "최다 지역(시군구)": sgg.iloc[0] if not sgg.empty else "-",
            "지역 수": part["region"].nunique(),
            "업종 대분류 최다": part["category_top"].mode().iloc[0] if not part["category_top"].mode().empty else "-",
        })
    return pd.DataFrame(rows)


def local_charts(df: pd.DataFrame) -> list[ChartSpec]:
    return [
        ChartSpec("sido", "시/도별 건수", "지역",
                  lambda d: charts.bar(stats.category_counts(d, "sido", 17), "sido", "count",
                                       "시/도별 업체 수", color="sido", sort=True)),
        ChartSpec("sgg", "지역(시군구)별 건수", "지역",
                  lambda d: charts.bar(stats.category_counts(d, "region", 20).iloc[::-1],
                                       "count", "region", "지역(시군구)별 업체 수", orientation="h")),
        ChartSpec("sido_heat", "검색어 × 시/도 히트맵", "지역",
                  lambda d: charts.heatmap(stats.crosstab(d, "query", "sido", top_col=17, margins=False),
                                           "검색어 × 시/도", index_col="query")),
        ChartSpec("region_tree", "지역 구성 트리맵", "지역",
                  lambda d: charts.treemap(
                      d.groupby(["sido", "sigungu"]).size().reset_index(name="count"),
                      ["sido", "sigungu"], "count", "시/도 → 시군구 구성")),
        ChartSpec("cat_top", "업종 대분류 빈도", "업종",
                  lambda d: charts.bar(stats.category_counts(d, "category_top", 15).iloc[::-1],
                                       "count", "category_top", "업종 대분류 분포", orientation="h")),
        ChartSpec("cat_heat", "업종 대분류 × 검색어 히트맵", "업종",
                  lambda d: charts.heatmap(stats.crosstab(d, "category_top", "query", top_col=12, margins=False),
                                           "업종 대분류 × 검색어", index_col="category_top")),
        ChartSpec("cat_leaf", "세부 업종 TOP 15", "업종",
                  lambda d: charts.bar(stats.category_counts(d, "category_leaf", 15).iloc[::-1],
                                       "count", "category_leaf", "세부 업종 분포", orientation="h")),
        ChartSpec("cnt", "검색어별 수집 건수", "기타",
                  lambda d: charts.bar(d.groupby("query").size().reset_index(name="건수"),
                                       "query", "건수", "검색어별 수집 건수", color="query")),
        ChartSpec("phone", "전화번호 등록 비율", "기타",
                  lambda d: charts.stacked_bar(
                      d.assign(전화=d["has_phone"].map({True: "있음", False: "없음"}))
                       .groupby(["query", "전화"]).size().reset_index(name="count"),
                      "query", "count", "전화", "검색어별 전화번호 등록 비율", percent=True)),
    ]


def local_tables(df: pd.DataFrame) -> list[TableSpec]:
    return [
        TableSpec("top_region", "검색어별 최다 지역·업종",
                  _top_region, help="지역 검색 결과(검색어당 최대 5건) 기준 최빈값."),
        TableSpec("pivot_region", "피봇: 지역(시군구) × 검색어",
                  lambda d: stats.pivot(d, "region", "query")),
        TableSpec("cross_cat", "교차표: 업종 대분류 × 검색어",
                  lambda d: stats.crosstab(d, "category_top", "query", top_col=12)),
        TableSpec("coords", "업체 좌표 목록",
                  lambda d: d[["query", "title_clean", "region", "category_leaf", "lat", "lon"]]
                            .rename(columns={"title_clean": "상호", "category_leaf": "업종"})),
        TableSpec("region_desc", "기술통계: 좌표 범위",
                  lambda d: stats.describe(d, ["lat", "lon", "title_len", "noun_cnt"])),
    ]


def build_specs(service: str, df: pd.DataFrame):
    if service == "image":
        return image_charts(df), image_tables(df)
    if service == "local":
        return local_charts(df), local_tables(df)
    return text_charts(service, df), text_tables(service, df)
