"""검색 결과 수집 + 정규화 + 기간 필터 + 파일 저장.

수집 결과는 `data/<service>/` 아래에 검색어별 CSV 로 저장된다.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .client import NaverApiHubClient, SEARCH_SERVICES

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = _PROJECT_ROOT / "data"

_TAG_RE = re.compile(r"<[^>]+>")

# 기간 필터를 적용할 수 있는(날짜 필드가 있는) 서비스
DATED_SERVICES = {"news", "blog"}


def clean_text(value: Any) -> str:
    """HTML 태그 제거 + 엔티티 unescape."""
    if not value:
        return ""
    return html.unescape(_TAG_RE.sub("", str(value))).strip()


def _parse_pubdate(value: str) -> pd.Timestamp | None:
    if not value:
        return None
    try:  # 예: "Mon, 08 Sep 2026 09:00:00 +0900"
        return pd.Timestamp(datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %z")).tz_convert(None)
    except (ValueError, TypeError):
        try:
            return pd.to_datetime(value, errors="coerce")
        except Exception:
            return None


def _parse_postdate(value: str) -> pd.Timestamp | None:
    if not value:
        return None
    try:  # 예: "20260908"
        return pd.Timestamp(datetime.strptime(str(value), "%Y%m%d"))
    except (ValueError, TypeError):
        return None


def _domain(url: str) -> str:
    m = re.match(r"https?://([^/]+)/?", str(url or ""))
    return m.group(1).lower().lstrip("www.") if m else ""


def normalize_items(service: str, items: list[dict[str, Any]]) -> pd.DataFrame:
    """서비스별 raw item 리스트 -> 공통 스키마 DataFrame.

    공통 컬럼: title, link, description, date(datetime|NaT), 그리고 서비스별 부가 컬럼.
    """
    rows: list[dict[str, Any]] = []
    for it in items:
        row: dict[str, Any] = {
            "title": clean_text(it.get("title")),
            "link": it.get("link", ""),
            "description": clean_text(it.get("description")),
            "date": pd.NaT,
        }
        if service == "news":
            row["date"] = _parse_pubdate(it.get("pubDate", ""))
            row["originallink"] = it.get("originallink", "")
            row["domain"] = _domain(it.get("originallink") or it.get("link"))
        elif service == "blog":
            row["date"] = _parse_postdate(it.get("postdate", ""))
            row["bloggername"] = clean_text(it.get("bloggername"))
            row["bloggerlink"] = it.get("bloggerlink", "")
            row["domain"] = _domain(it.get("bloggerlink") or it.get("link"))
        elif service == "cafearticle":
            row["cafename"] = clean_text(it.get("cafename"))
            row["cafeurl"] = it.get("cafeurl", "")
            row["domain"] = _domain(it.get("cafeurl") or it.get("link"))
        elif service == "image":
            row["thumbnail"] = it.get("thumbnail", "")
            row["sizewidth"] = pd.to_numeric(it.get("sizewidth"), errors="coerce")
            row["sizeheight"] = pd.to_numeric(it.get("sizeheight"), errors="coerce")
            row["domain"] = _domain(it.get("link"))
        elif service == "encyc":
            row["thumbnail"] = it.get("thumbnail", "")
            row["domain"] = _domain(it.get("link"))
        elif service == "local":
            row["category"] = clean_text(it.get("category"))
            row["telephone"] = clean_text(it.get("telephone"))
            row["address"] = clean_text(it.get("address"))
            row["roadAddress"] = clean_text(it.get("roadAddress"))
            row["mapx"] = pd.to_numeric(it.get("mapx"), errors="coerce")
            row["mapy"] = pd.to_numeric(it.get("mapy"), errors="coerce")
            row["region"] = " ".join(clean_text(it.get("address")).split()[:2])
            row["domain"] = _domain(it.get("link"))
        else:  # webkr, kin
            row["domain"] = _domain(it.get("link"))
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty and "date" in df:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def _apply_period(df: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
    if df.empty or "date" not in df or start is None or end is None:
        return df
    if df["date"].isna().all():
        return df
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1)  # 종료일 포함
    mask = df["date"].between(start_ts, end_ts) | df["date"].isna()
    return df.loc[mask].reset_index(drop=True)


def collect_service(
    client: NaverApiHubClient,
    service: str,
    queries: list[str],
    *,
    max_results: int = 100,
    sort: str = "sim",
    start_date: date | None = None,
    end_date: date | None = None,
    image_filter: str | None = None,
    save: bool = True,
) -> pd.DataFrame:
    """하나의 서비스에 대해 여러 검색어를 수집해 하나의 DataFrame 으로 반환."""
    frames: list[pd.DataFrame] = []
    apply_period = service in DATED_SERVICES and start_date and end_date
    effective_sort = "date" if apply_period else sort

    stop_when: Callable[[dict[str, Any]], bool] | None = None
    if apply_period:
        cutoff = pd.Timestamp(start_date)

        def stop_when(item: dict[str, Any]) -> bool:  # noqa: E306
            raw = item.get("pubDate") if service == "news" else item.get("postdate")
            ts = _parse_pubdate(raw) if service == "news" else _parse_postdate(raw)
            return ts is not None and ts < cutoff

    for q in queries:
        result = client.search_paginated(
            service, q,
            max_results=max_results,
            sort=effective_sort,
            image_filter=image_filter,
            stop_when=stop_when,
        )
        df = normalize_items(service, result["items"])
        df.insert(0, "query", q)
        df["total_reported"] = result.get("total")
        if apply_period:
            df = _apply_period(df, start_date, end_date)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    if save and not combined.empty:
        out_dir = DATA_DIR / service
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d")
        for q, part in combined.groupby("query"):
            safe = re.sub(r"[^\w가-힣]+", "_", str(q)).strip("_") or "query"
            part.to_csv(out_dir / f"{safe}_{stamp}.csv", index=False, encoding="utf-8-sig")

    return combined


def collect_all(
    client: NaverApiHubClient,
    queries: list[str],
    services: list[str],
    *,
    max_results: int = 100,
    sort: str = "sim",
    start_date: date | None = None,
    end_date: date | None = None,
    image_filter: str | None = None,
    progress: Callable[[str, str], None] | None = None,
) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for service in services:
        if service not in SEARCH_SERVICES:
            continue
        if progress:
            progress(service, SEARCH_SERVICES[service])
        out[service] = collect_service(
            client, service, queries,
            max_results=max_results, sort=sort,
            start_date=start_date, end_date=end_date,
            image_filter=image_filter,
        )
    return out
