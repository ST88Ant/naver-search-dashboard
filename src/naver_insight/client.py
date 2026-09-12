"""NAVER API HUB 클라이언트 (검색 API + 검색어 트렌드 API).

공식 문서: https://api.ncloud-docs.com/docs/naver-api-hub-overview
"""

from __future__ import annotations

import time
from typing import Any, Iterable

import requests

from .settings import DEFAULT_BASE_URL

# service 코드 -> 한글 라벨
SEARCH_SERVICES: dict[str, str] = {
    "news": "뉴스",
    "blog": "블로그",
    "webkr": "웹문서",
    "image": "이미지",
    "kin": "지식iN",
    "local": "지역",
    "cafearticle": "카페글",
    "encyc": "백과사전",
}

# 서비스별 허용 sort 값 (문서 기준). 목록에 없으면 sort 파라미터를 보내지 않음.
_SORT_SUPPORT: dict[str, set[str]] = {
    "news": {"sim", "date"},
    "blog": {"sim", "date"},
    "image": {"sim", "date"},
    "kin": {"sim", "date", "point"},
    "cafearticle": {"sim", "date"},
    "local": {"random", "comment"},
    "webkr": set(),
    "encyc": set(),
}

MAX_DISPLAY = 100
MAX_START = 1000

# 지역(local) 검색은 문서상 display 최대 5, start 최대 1 로 제한된다.
_PER_PAGE: dict[str, int] = {"local": 5}
_MAX_TOTAL: dict[str, int] = {"local": 5}
_START_CAP: dict[str, int] = {"local": 1}
AGE_LABELS = {
    "1": "0-12", "2": "13-18", "3": "19-24", "4": "25-29", "5": "30-34",
    "6": "35-39", "7": "40-44", "8": "45-49", "9": "50-54", "10": "55-59",
    "11": "60+",
}


class NaverApiError(RuntimeError):
    """API 호출 실패."""

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class NaverApiHubClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 10.0,
        max_retries: int = 2,
        retry_backoff: float = 1.5,
    ) -> None:
        if not client_id or not client_secret:
            raise NaverApiError("API Key ID / API Key 가 비어 있습니다. .env 를 확인하세요.")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-NCP-APIGW-API-KEY-ID": client_id,
                "X-NCP-APIGW-API-KEY": client_secret,
                "User-Agent": "naver-search-dashboard/0.1",
            }
        )

    # ── 내부 요청 유틸 ────────────────────────────────────────────
    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:  # 네트워크 오류
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff * (attempt + 1))
                    continue
                raise NaverApiError(f"네트워크 오류: {exc}") from exc

            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise NaverApiError("JSON 파싱 실패", resp.status_code, resp.text[:500]) from exc

            # 429 / 5xx 는 재시도
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                time.sleep(self.retry_backoff * (attempt + 1))
                continue

            raise NaverApiError(
                f"API 오류 {resp.status_code} ({method} {path})",
                resp.status_code,
                resp.text[:500],
            )

        raise NaverApiError(f"요청 실패: {last_exc}")

    # ── 검색 API ────────────────────────────────────────────────
    def search(
        self,
        service: str,
        query: str,
        display: int = MAX_DISPLAY,
        start: int = 1,
        sort: str = "sim",
        image_filter: str | None = None,
    ) -> dict[str, Any]:
        if service not in SEARCH_SERVICES:
            raise ValueError(f"알 수 없는 service: {service}")
        per_page = _PER_PAGE.get(service, MAX_DISPLAY)
        start_cap = _START_CAP.get(service, MAX_START)
        params: dict[str, Any] = {
            "query": query,
            "display": max(1, min(display, per_page)),
            "start": max(1, min(start, start_cap)),
            "format": "json",
        }
        if sort in _SORT_SUPPORT.get(service, set()):
            params["sort"] = sort
        if service == "image" and image_filter:
            params["filter"] = image_filter
        return self._request("GET", f"/search/v1/{service}", params=params)

    def search_paginated(
        self,
        service: str,
        query: str,
        max_results: int = 100,
        sort: str = "sim",
        image_filter: str | None = None,
        stop_when: "callable | None" = None,
        pause: float = 0.15,
    ) -> dict[str, Any]:
        """`start` 를 넘겨가며 최대 max_results(최대 1000)건 수집.

        stop_when(item) 이 True 를 반환하면 그 지점에서 페이지네이션 종료
        (기간 필터링 시 오래된 결과를 만나면 중단하는 용도).
        """
        max_results = max(1, min(max_results, _MAX_TOTAL.get(service, MAX_START)))
        per_page = _PER_PAGE.get(service, MAX_DISPLAY)
        start_cap = _START_CAP.get(service, MAX_START)
        items: list[dict[str, Any]] = []
        total: int | None = None
        last_build_date: str | None = None
        start = 1
        while len(items) < max_results and start <= start_cap:
            want = min(per_page, max_results - len(items))
            data = self.search(service, query, display=want, start=start, sort=sort,
                               image_filter=image_filter)
            total = data.get("total", total)
            last_build_date = data.get("lastBuildDate", last_build_date)
            batch = data.get("items", []) or []
            if not batch:
                break
            hit_stop = False
            for it in batch:
                if stop_when is not None and stop_when(it):
                    hit_stop = True
                    break
                items.append(it)
            if hit_stop or len(batch) < want:
                break
            start += len(batch)
            if pause:
                time.sleep(pause)
        return {"total": total, "lastBuildDate": last_build_date, "items": items[:max_results]}

    # ── 검색어 트렌드 API ────────────────────────────────────────
    def search_trend(
        self,
        start_date: str,
        end_date: str,
        keyword_groups: Iterable[dict[str, Any]],
        time_unit: str = "date",
        device: str | None = None,
        gender: str | None = None,
        ages: list[str] | None = None,
    ) -> dict[str, Any]:
        groups = [
            {"groupName": g["groupName"], "keywords": list(g["keywords"])[:20]}
            for g in keyword_groups
        ][:5]
        if not groups:
            raise ValueError("keyword_groups 가 비어 있습니다.")
        body: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": groups,
        }
        if device in ("pc", "mo"):
            body["device"] = device
        if gender in ("m", "f"):
            body["gender"] = gender
        if ages:
            body["ages"] = list(ages)
        return self._request(
            "POST",
            "/search-trend/v1/search",
            json=body,
            headers={"Content-Type": "application/json"},
        )
