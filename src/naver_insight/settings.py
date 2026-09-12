"""`.env` 기반 설정 로딩.

우선순위: 실제 환경변수 > 프로젝트 루트의 `.env` 파일.
키 이름은 NAVER API HUB 표기(`NAVER_API_KEY_ID` / `NAVER_API_KEY`)를 기본으로 하되
구버전 오픈API 표기(`NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET`)도 함께 인식합니다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://naverapihub.apigw.ntruss.com"

# 프로젝트 루트(.../naver-search-dashboard)의 .env 를 명시적으로 로드
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()  # 현재 작업 디렉터리 기준 .env 도 시도(있으면 보완)


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    base_url: str = DEFAULT_BASE_URL

    @property
    def is_complete(self) -> bool:
        return bool(self.client_id) and bool(self.client_secret)


def load_settings() -> Settings:
    client_id = (
        os.getenv("NAVER_API_KEY_ID")
        or os.getenv("NAVER_CLIENT_ID")
        or ""
    ).strip()
    client_secret = (
        os.getenv("NAVER_API_KEY")
        or os.getenv("NAVER_CLIENT_SECRET")
        or ""
    ).strip()
    base_url = (os.getenv("NAVER_API_BASE_URL") or DEFAULT_BASE_URL).strip()
    return Settings(client_id=client_id, client_secret=client_secret, base_url=base_url)
