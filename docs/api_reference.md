# NAVER API HUB — 참고 정리

> 출처: <https://api.ncloud-docs.com/docs/naver-api-hub-overview> 및 하위 문서
> (search-news / search-blog / search-webkr / search-image / search-kin /
> search-cafearticle / search-encyc / search-trend)

## 인증

모든 요청에 아래 HTTP 헤더가 필요합니다.

| 헤더 | 값 |
|------|-----|
| `X-NCP-APIGW-API-KEY-ID` | 콘솔에서 발급한 API Key ID |
| `X-NCP-APIGW-API-KEY` | 콘솔에서 발급한 API Key |

Base URL: `https://naverapihub.apigw.ntruss.com`
검색 API 일 호출 한도: 25,000 회.

## 검색 API (GET)

`GET /search/v1/{service}` — 응답은 JSON(`format=json` 기본).

| service | 설명 | 엔드포인트 | `sort` 허용값 | item 주요 필드 |
|---------|------|-----------|--------------|----------------|
| `news` | 뉴스 | `/search/v1/news` | `sim`, `date` | title, originallink, link, description, **pubDate** |
| `blog` | 블로그 | `/search/v1/blog` | `sim`, `date` | title, link, description, bloggername, bloggerlink, **postdate**(YYYYMMDD) |
| `webkr` | 웹문서 | `/search/v1/webkr` | (없음) | title, link, description |
| `image` | 이미지 | `/search/v1/image` | `sim`, `date` | title, link, thumbnail, sizeheight, sizewidth (+ `filter`=all/large/medium/small) |
| `kin` | 지식iN | `/search/v1/kin` | `sim`, `date`, `point` | title, link, description |
| `local` | 지역 | `/search/v1/local` | `random`, `comment` | title, link, category, description, telephone, address, roadAddress, mapx, mapy — **`display` 최대 5, `start` 최대 1** |
| `cafearticle` | 카페글 | `/search/v1/cafearticle` | `sim`, `date` | title, link, description, cafename, cafeurl |
| `encyc` | 백과사전 | `/search/v1/encyc` | (없음) | title, link, description, thumbnail |

공통 파라미터

| 파라미터 | 타입 | 기본 | 범위 |
|----------|------|------|------|
| `query` | string | (필수) | UTF-8 |
| `display` | int | 10 | 1–100 |
| `start` | int | 1 | 1–1000 |
| `format` | string | `json` | `json`, `xml` |

공통 응답 루트: `lastBuildDate`, `total`, `start`, `display`, `items[]`.

> **기간(날짜) 필터**: 검색 API 자체에는 날짜 범위 파라미터가 없습니다.
> 날짜 정보를 담은 서비스(`news`=pubDate, `blog`=postdate)만 클라이언트에서
> 기간 필터링이 가능하며, 이 대시보드는 해당 서비스에 대해 `sort=date` 로
> 페이지를 넘겨가며 수집 후 기간으로 잘라냅니다. 나머지 서비스는 기간과
> 무관하게 관련도(또는 지정 정렬) 상위 N건을 수집합니다.

## 검색어 트렌드 API (POST)

`POST /search-trend/v1/search` — `Content-Type: application/json`

요청 본문

```json
{
  "startDate": "yyyy-mm-dd",          // 필수, 2016-01-01 이후
  "endDate":   "yyyy-mm-dd",          // 필수
  "timeUnit":  "date | week | month", // 필수
  "keywordGroups": [                   // 필수, 최대 5개
    { "groupName": "그룹명", "keywords": ["키워드", ...] }  // keywords 최대 20개
  ],
  "device": "pc | mo",                // 선택, 미지정 시 전체
  "gender": "m | f",                  // 선택, 미지정 시 전체
  "ages":   ["1" ... "11"]            // 선택, 미지정 시 전체
}
```

연령 코드: 1(0–12), 2(13–18), 3(19–24), 4(25–29), 5(30–34), 6(35–39),
7(40–44), 8(45–49), 9(50–54), 10(55–59), 11(60+).

응답

```json
{
  "startDate": "...", "endDate": "...", "timeUnit": "...",
  "results": [
    { "title": "그룹명", "keywords": ["..."],
      "data": [ { "period": "yyyy-mm-dd", "ratio": 0.0 } ] }
  ]
}
```

`ratio` 는 기간 내 최대 검색량을 100 으로 한 상대값입니다(절대 검색량 아님).
