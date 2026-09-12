"""검색어 트렌드의 성별·연령·기기 분해 수집.

왜 '구성비'로만 비교하는가
--------------------------
트렌드 API 의 `ratio` 는 **한 번의 호출 안에서** 최댓값을 100 으로 맞춘 상대값이다.
성별·연령은 그룹 옵션이 아니라 요청 전체에 걸리는 필터라서, 세그먼트마다 호출을
따로 해야 하고 그때마다 정규화가 새로 일어난다. 따라서

  · "20대가 30대보다 많이 검색한다"  -> 호출이 다르므로 **말할 수 없다**
  · "30대 안에서 A 가 B 보다 우세하다" -> 같은 호출 안이므로 **말할 수 있다**

구성비(share)는 한 호출 안의 합으로 나눈 값이라 정규화 상수가 약분된다.
그래서 세그먼트끼리 비교해도 안전하다. 이 모듈은 구성비만 만든다.
"""

from __future__ import annotations

import pandas as pd

from .client import AGE_LABELS, NaverApiError, NaverApiHubClient
from .eda import stats

GENDERS: dict[str, str] = {"m": "남성", "f": "여성"}
DEVICES: dict[str, str] = {"pc": "PC", "mo": "모바일"}


def _one(client, start, end, groups, time_unit, **kw) -> pd.DataFrame:
    resp = client.search_trend(start, end, groups, time_unit=time_unit, **kw)
    return stats.trend_to_frame(resp)


def _shares(frame: pd.DataFrame, segment: str) -> pd.DataFrame:
    """한 세그먼트 호출 결과 -> 검색어별 구성비(%)."""
    if frame is None or frame.empty:
        return pd.DataFrame()
    mean = frame.groupby("group")["ratio"].mean()
    total = mean.sum()
    if total <= 0:
        return pd.DataFrame()
    out = (mean / total * 100).reset_index(name="구성비")
    out["세그먼트"] = segment
    out = out.rename(columns={"group": "검색어"})
    out["평균점수"] = mean.values.round(2)
    return out


def collect_splits(
    client: NaverApiHubClient,
    queries: list[str],
    start_date: str,
    end_date: str,
    time_unit: str = "month",
    *,
    include_age: bool = True,
    progress=None,
) -> dict[str, pd.DataFrame]:
    """성별 2회 + 기기 2회 (+ 연령 11회) 호출해 구성비 표를 만든다.

    Returns {"gender": df, "device": df, "age": df} — 각 df 컬럼은
    검색어 / 구성비 / 세그먼트 / 평균점수. 실패한 세그먼트는 조용히 빠진다.
    """
    groups = [{"groupName": q, "keywords": [q]} for q in queries[:5]]
    if not groups:
        return {}

    jobs: list[tuple[str, str, dict]] = []
    jobs += [("gender", label, {"gender": code}) for code, label in GENDERS.items()]
    jobs += [("device", label, {"device": code}) for code, label in DEVICES.items()]
    if include_age:
        jobs += [("age", f"{AGE_LABELS[c]}세", {"ages": [c]}) for c in AGE_LABELS]

    buckets: dict[str, list[pd.DataFrame]] = {"gender": [], "device": [], "age": []}
    for i, (kind, label, kw) in enumerate(jobs):
        if progress is not None:
            progress(i / len(jobs), f"{label} 조회 중… ({i + 1}/{len(jobs)})")
        try:
            part = _shares(_one(client, start_date, end_date, groups, time_unit, **kw), label)
        except NaverApiError:
            continue
        if not part.empty:
            buckets[kind].append(part)
    if progress is not None:
        progress(1.0, "완료")

    out: dict[str, pd.DataFrame] = {}
    for kind, parts in buckets.items():
        if parts:
            df = pd.concat(parts, ignore_index=True)
            if kind == "age":  # 연령대는 나이순 정렬을 고정
                order = [f"{v}세" for v in AGE_LABELS.values()]
                df["세그먼트"] = pd.Categorical(df["세그먼트"], categories=order, ordered=True)
                df = df.sort_values(["세그먼트", "검색어"])
            out[kind] = df
    return out


def skew_table(age_df: pd.DataFrame) -> pd.DataFrame:
    """검색어별로 구성비가 가장 높은 연령대(=상대적으로 치우친 층)."""
    if age_df is None or age_df.empty:
        return pd.DataFrame()
    rows = []
    for q, part in age_df.groupby("검색어", observed=True):
        p = part.dropna(subset=["세그먼트"]).sort_values("구성비", ascending=False)
        if p.empty:
            continue
        rows.append({
            "검색어": q,
            "가장 우세한 연령대": str(p.iloc[0]["세그먼트"]),
            "그 연령대에서의 구성비": f"{p.iloc[0]['구성비']:.1f}%",
            "가장 약한 연령대": str(p.iloc[-1]["세그먼트"]),
            "구성비 편차": round(p["구성비"].max() - p["구성비"].min(), 1),
        })
    return pd.DataFrame(rows).sort_values("구성비 편차", ascending=False)
