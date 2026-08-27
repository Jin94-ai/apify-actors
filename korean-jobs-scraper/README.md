# Korean Jobs Scraper — Saramin, JobKorea, Wanted

Scrape job postings from **Korea's three major job boards** in one run:

- **Saramin (사람인)** — Korea's largest job board
- **JobKorea (잡코리아)** — the long-standing #2 board
- **Wanted (원티드)** — the leading tech/startup job platform

Search by any keyword (Korean or English) and get structured job data ready for analysis, alerts, or lead generation.

## Why this Actor?

Korean job boards have no official public APIs and few working scrapers exist. This Actor covers all three major boards with a single input, maintained by a developer based in Korea who uses these sites daily.

Use cases:

- **Recruiting & sourcing** — monitor postings for specific roles or companies
- **Market research** — track hiring trends, salaries, and demand by keyword
- **Job search automation** — collect fresh postings for a given role every day
- **Lead generation** — companies that are hiring are companies that are buying

## Input

```json
{
  "keyword": "마케팅",
  "sources": ["saramin", "jobkorea", "wanted"],
  "max_items_per_source": 20
}
```

| Field | Type | Description |
|---|---|---|
| `keyword` | string | Search keyword — Korean or English (required) |
| `sources` | array | Any of `saramin`, `jobkorea`, `wanted` (default: all three) |
| `max_items_per_source` | integer | 1–100 postings per board (default 20) |

## Output

One dataset item per job posting:

```json
{
  "source": "saramin",
  "title": "AI 업무자동화 담당자 채용",
  "company": "(주)예시컴퍼니",
  "conditions": ["서울 강남구", "신입·경력", "학력무관", "정규직"],
  "deadline": "~ 09/30(수)",
  "url": "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=12345678",
  "job_id": "12345678",
  "scraped_at": "2026-08-28T12:34:56+00:00"
}
```

Field coverage varies slightly per board (Wanted provides location and due date via its JSON API; JobKorea list pages expose title and link, with company name when available).

## Notes & fair use

- Scrapes only publicly accessible listing pages / endpoints — no login, no personal data.
- Respect the target sites: keep result counts reasonable and schedule runs at sensible intervals.
- Postings are returned in each board's default relevance/latest order.

## Roadmap

- Detail-page enrichment (salary, full description)
- Region and experience-level filters
- Albamon (알바몬) part-time board support

Found an issue or need a Korean site scraped? Open an issue on this Actor — responses usually within a day.
