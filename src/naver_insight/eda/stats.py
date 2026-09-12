"""기술통계 · 교차표 · 피봇테이블 · 연관성 지표.

무거운 집계 함수는 `st.cache_data` 로 캐시한다(탭 UI 에서 매 rerun 마다
모든 탭이 다시 그려지므로 캐시가 없으면 느리다).
scipy 없이 카이제곱 통계량과 Cramér's V(효과크기)를 직접 계산한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

_cache = st.cache_data(show_spinner=False, ttl=1800)


# ── 기술통계 ────────────────────────────────────────────────


@_cache
def describe(df: pd.DataFrame, columns: list[str], by: str | None = None) -> pd.DataFrame:
    cols = [c for c in columns if c in df.columns]
    if not cols:
        return pd.DataFrame()
    if by and by in df.columns:
        out = df.groupby(by)[cols].agg(["count", "mean", "std", "min", "median", "max"])
        out.columns = [f"{c}·{stat}" for c, stat in out.columns]
        return out.round(2).reset_index()
    desc = df[cols].describe(percentiles=[0.25, 0.5, 0.75]).T
    desc["skew"] = df[cols].skew(numeric_only=True)
    desc["missing"] = df[cols].isna().sum()
    return desc.round(2).reset_index(names="지표")


@_cache
def value_summary(df: pd.DataFrame, group: str = "query") -> pd.DataFrame:
    if df.empty or group not in df.columns:
        return pd.DataFrame()
    rows = []
    for key, part in df.groupby(group):
        row = {group: key, "수집건수": len(part)}
        if "total_len" in part:
            row["평균길이"] = round(part["total_len"].mean(), 1)
            row["길이중앙값"] = round(part["total_len"].median(), 1)
        if "noun_cnt" in part:
            row["평균명사수"] = round(part["noun_cnt"].mean(), 1)
        if "domain" in part:
            row["고유도메인"] = part["domain"].nunique()
        if "date" in part and part["date"].notna().any():
            row["최초"] = part["date"].min().date()
            row["최신"] = part["date"].max().date()
        if "total_reported" in part:
            tr = part["total_reported"].dropna()
            row["API_total"] = int(tr.iloc[0]) if not tr.empty else None
        rows.append(row)
    return pd.DataFrame(rows)


# ── 교차표 / 연관성 ─────────────────────────────────────────


def cramers_v(confusion: pd.DataFrame) -> float:
    arr = confusion.to_numpy(dtype=float)
    n = arr.sum()
    if n == 0:
        return float("nan")
    row = arr.sum(axis=1, keepdims=True)
    col = arr.sum(axis=0, keepdims=True)
    expected = row @ col / n
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = np.nansum((arr - expected) ** 2 / expected)
    k = min(arr.shape) - 1
    if k <= 0:
        return float("nan")
    return float(np.sqrt(chi2 / (n * k)))


@_cache
def crosstab(df: pd.DataFrame, row: str, col: str, *, top_col: int = 12,
             normalize: str | None = None, margins: bool = True) -> pd.DataFrame:
    if df.empty or row not in df.columns or col not in df.columns:
        return pd.DataFrame()
    work = df[[row, col]].copy()
    keep = work[col].value_counts().head(top_col).index
    work[col] = work[col].where(work[col].isin(keep), other="기타")
    ct = pd.crosstab(
        work[row], work[col],
        normalize=normalize if normalize else False,
        margins=margins and not normalize, margins_name="합계",
    )
    if normalize:
        ct = (ct * 100).round(1)
    return ct.reset_index()


@_cache
def pivot(df: pd.DataFrame, index: str, columns: str, values: str | None = None,
          aggfunc: str = "size", *, fill_value=0) -> pd.DataFrame:
    if df.empty or index not in df.columns or columns not in df.columns:
        return pd.DataFrame()
    if aggfunc == "size" or values is None:
        pt = pd.pivot_table(df, index=index, columns=columns, aggfunc="size", fill_value=fill_value)
    else:
        if values not in df.columns:
            return pd.DataFrame()
        pt = pd.pivot_table(df, index=index, columns=columns, values=values,
                            aggfunc=aggfunc, fill_value=fill_value).round(2)
    return pt.reset_index()


# ── 집계 ────────────────────────────────────────────────────


@_cache
def daily_counts(df: pd.DataFrame, freq: str = "D", group: str = "query") -> pd.DataFrame:
    if df.empty or "date" not in df or df["date"].isna().all():
        return pd.DataFrame(columns=["date", group, "count"])
    work = df.dropna(subset=["date"]).copy()
    work["bucket"] = (
        work["date"].dt.floor("D") if freq == "D"
        else work["date"].dt.to_period(freq).dt.start_time
    )
    return (
        work.groupby(["bucket", group]).size()
        .reset_index(name="count").rename(columns={"bucket": "date"})
        .sort_values("date")
    )


@_cache
def category_counts(df: pd.DataFrame, col: str, top_n: int = 15, group: str | None = None) -> pd.DataFrame:
    if df.empty or col not in df:
        return pd.DataFrame(columns=[col, "count"])
    work = df[df[col].astype(str).str.len() > 0]
    if group and group in df.columns:
        keep = work[col].value_counts().head(top_n).index
        sub = work[work[col].isin(keep)]
        return sub.groupby([col, group]).size().reset_index(name="count")
    return work[col].value_counts().head(top_n).rename_axis(col).reset_index(name="count")


@_cache
def domain_diversity(df: pd.DataFrame, group: str = "query") -> pd.DataFrame:
    if df.empty or "domain" not in df or group not in df:
        return pd.DataFrame()
    return (
        df.groupby(group)["domain"]
        .agg(고유도메인="nunique", 건수="size")
        .assign(집중도=lambda x: (x["건수"] / x["고유도메인"]).round(2))
        .reset_index()
    )


def summary_table(collected: dict[str, pd.DataFrame], service_labels: dict[str, str]) -> pd.DataFrame:
    rows: list[dict] = []
    for service, df in collected.items():
        label = service_labels.get(service, service)
        if df is None or df.empty:
            rows.append({"서비스": label, "검색어": "-", "수집건수": 0, "API total": None})
            continue
        for q, part in df.groupby("query"):
            tr = part["total_reported"].dropna() if "total_reported" in part else pd.Series(dtype=float)
            rows.append({
                "서비스": label, "검색어": q, "수집건수": len(part),
                "API total": int(tr.iloc[0]) if not tr.empty else None,
                "평균길이": round(part["total_len"].mean(), 1) if "total_len" in part else None,
            })
    return pd.DataFrame(rows)


def trend_to_frame(trend_response: dict) -> pd.DataFrame:
    rows: list[dict] = []
    for result in trend_response.get("results", []):
        group = result.get("title", "")
        for point in result.get("data", []):
            rows.append({
                "period": pd.to_datetime(point.get("period"), errors="coerce"),
                "group": group,
                "ratio": pd.to_numeric(point.get("ratio"), errors="coerce"),
            })
    df = pd.DataFrame(rows)
    return df.sort_values(["group", "period"]).reset_index(drop=True) if not df.empty else df
