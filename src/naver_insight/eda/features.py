"""파생 피처 생성 — 원본 검색 결과에 분석용 컬럼을 추가한다.

네이버 검색 API 응답 필드가 빈약하기 때문에(웹문서·지식iN은 제목/요약뿐),
길이·형태소·시간·도메인 등을 계산해 EDA 재료를 만든다.
형태소 분석(kiwi)은 여기서 배치로 1회만 수행한다.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import text as textmod

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]

_NUM_RE = re.compile(r"\d")
_ENG_RE = re.compile(r"[A-Za-z]")
_BRACKET_RE = re.compile(r"[\[\]()<>{}“”\"']")


def _tld(domain: str) -> str:
    if not domain or "." not in domain:
        return domain or ""
    return domain.rsplit(".", 1)[-1]


def _len_bucket(n: float) -> str:
    if pd.isna(n):
        return "미상"
    n = int(n)
    if n == 0:
        return "0"
    if n <= 20:
        return "1–20"
    if n <= 50:
        return "21–50"
    if n <= 100:
        return "51–100"
    if n <= 200:
        return "101–200"
    return "200+"


def add_common_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()

    df["title_clean"] = df.get("title", "").map(textmod.clean)
    df["desc_clean"] = df.get("description", "").map(textmod.clean) if "description" in df else ""

    df["title_len"] = df["title_clean"].str.len()
    df["desc_len"] = df["desc_clean"].str.len() if "desc_clean" in df else 0
    df["total_len"] = df["title_len"].fillna(0) + df["desc_len"].fillna(0)
    df["title_word_cnt"] = df["title_clean"].str.split().map(len)
    df["desc_word_cnt"] = df["desc_clean"].str.split().map(len)

    df["title_has_num"] = df["title_clean"].str.contains(_NUM_RE, na=False)
    df["title_has_eng"] = df["title_clean"].str.contains(_ENG_RE, na=False)
    df["title_has_bracket"] = df["title_clean"].str.contains(_BRACKET_RE, na=False, regex=True)

    if "domain" in df:
        df["domain"] = df["domain"].fillna("").replace("", "(없음)")
        df["tld"] = df["domain"].map(_tld)

    # 형태소 명사 — 제목/본문 각각 1회 배치 토큰화
    title_nouns = textmod.noun_str_series(df["title_clean"])
    desc_nouns = textmod.noun_str_series(df["desc_clean"]) if "desc_clean" in df else pd.Series("", index=df.index)
    df["noun_str"] = (title_nouns + " " + desc_nouns).str.strip()
    df["noun_cnt"] = df["noun_str"].str.split().map(len)
    df["uniq_noun_cnt"] = df["noun_str"].str.split().map(lambda ws: len(set(ws)))
    if "desc_clean" in df:
        df["title_desc_jaccard"] = [
            textmod.jaccard_str(a, b) for a, b in zip(title_nouns, desc_nouns, strict=False)
        ]

    df["len_bucket"] = df["desc_len"].where(df["desc_len"] > 0, df["title_len"]).map(_len_bucket)

    if "date" in df and df["date"].notna().any():
        d = pd.to_datetime(df["date"], errors="coerce")
        # 정규화한 값을 원본 컬럼에 되쓴다. 수집 직후에는 이미 Timestamp 지만,
        # 저장해 둔 CSV 를 다시 읽으면 문자열로 돌아온다. 되쓰지 않으면
        # stats.value_summary / daily_counts 처럼 .dt 를 쓰는 쪽이 깨진다.
        df["date"] = d
        df["date_only"] = d.dt.date
        df["year"] = d.dt.year
        df["month"] = d.dt.month
        df["year_month"] = d.dt.to_period("M").astype(str).replace("NaT", np.nan)
        df["iso_week"] = d.dt.isocalendar().week.astype("Int64")
        df["weekday_num"] = d.dt.weekday
        df["weekday"] = df["weekday_num"].map(lambda i: WEEKDAY_KO[int(i)] if pd.notna(i) else np.nan)
        df["hour"] = d.dt.hour
        df["is_weekend"] = df["weekday_num"] >= 5
        df["days_ago"] = (pd.Timestamp.now().normalize() - d.dt.normalize()).dt.days

    return df


def add_image_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = add_common_features(df)
    w = pd.to_numeric(df.get("sizewidth"), errors="coerce")
    h = pd.to_numeric(df.get("sizeheight"), errors="coerce")
    df["img_w"] = w
    df["img_h"] = h
    df["img_area"] = w * h
    df["img_megapixels"] = (w * h) / 1_000_000
    df["img_aspect"] = w / h.replace(0, np.nan)
    df["img_orientation"] = np.select(
        [df["img_aspect"] > 1.15, df["img_aspect"] < 0.87],
        ["가로형", "세로형"], default="정사각형",
    )
    df.loc[df["img_aspect"].isna(), "img_orientation"] = "미상"
    df["img_size_bucket"] = pd.cut(
        df["img_megapixels"], bins=[-0.01, 0.1, 0.5, 2, 8, np.inf],
        labels=["≤0.1MP", "0.1–0.5MP", "0.5–2MP", "2–8MP", "8MP+"],
    ).astype(str)
    return df


def _coord(value) -> float:
    v = pd.to_numeric(value, errors="coerce")
    if pd.isna(v):
        return np.nan
    return v / 1e7 if abs(v) > 1000 else float(v)


def add_local_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = add_common_features(df)

    parts = df.get("address", "").fillna("").map(textmod.clean).str.split()
    df["sido"] = parts.map(lambda p: p[0] if len(p) else "미상")
    df["sigungu"] = parts.map(lambda p: " ".join(p[1:2]) if len(p) > 1 else "미상")
    df["region"] = parts.map(lambda p: " ".join(p[:2]) if len(p) >= 2 else (p[0] if p else "미상"))

    cat = df.get("category", "").fillna("").map(textmod.clean)
    df["category_top"] = cat.str.split(">").map(lambda p: p[0].strip() if p and p[0] else "미상")
    df["category_leaf"] = cat.str.split(">").map(lambda p: p[-1].strip() if p and p[-1] else "미상")

    df["has_phone"] = df.get("telephone", "").fillna("").str.strip().ne("")
    df["lon"] = df.get("mapx").map(_coord) if "mapx" in df else np.nan
    df["lat"] = df.get("mapy").map(_coord) if "mapy" in df else np.nan
    bad = ~(df["lat"].between(33, 39) & df["lon"].between(124, 132))
    df.loc[bad, ["lat", "lon"]] = np.nan
    return df


def add_features(service: str, df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    if service == "image":
        return add_image_features(df)
    if service == "local":
        return add_local_features(df)
    return add_common_features(df)


NUMERIC_FEATURES: dict[str, list[str]] = {
    "_text": ["title_len", "desc_len", "total_len", "title_word_cnt", "desc_word_cnt",
              "noun_cnt", "uniq_noun_cnt", "title_desc_jaccard"],
    "image": ["title_len", "img_w", "img_h", "img_area", "img_megapixels", "img_aspect", "noun_cnt"],
    "local": ["title_len", "noun_cnt", "lat", "lon"],
}


def numeric_features(service: str, df: pd.DataFrame) -> list[str]:
    cols = NUMERIC_FEATURES.get(service, NUMERIC_FEATURES["_text"])
    return [c for c in cols if c in df.columns]
