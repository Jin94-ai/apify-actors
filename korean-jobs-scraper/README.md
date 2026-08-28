# Korean Jobs Scraper — Saramin, JobKorea, Wanted

Scrape job postings from **Korea's three major job boards** in one run:

- **Saramin (사람인)** — Korea's largest job board
- **JobKorea (잡코리아)** — the long-standing #2 board
- **Wanted (원티드)** — the leading tech/startup job platform

Search by any keyword (Korean or English) and get structured job data ready for analysis, alerts, or lead generation.

## Why this Actor?

Korean job boards' official APIs are approval-gated, limited, or nonexistent, and few working scrapers exist. This Actor covers all three major boards with a single input, maintained by a developer based in Korea who uses these sites daily.

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

One dataset item per job posting, with structured fields:

Real row from an actual run (public posting):

```json
{
  "source": "saramin",
  "title": "㈜새한마이크로텍 재무회계담당자 채용",
  "company": "㈜새한마이크로텍",
  "region": "경기남양주시",
  "experience": "경력무관",
  "education": "초대졸↑",
  "employment_type": "정규직",
  "salary": null,
  "conditions": ["경기남양주시", "경력무관", "초대졸↑", "정규직"],
  "deadline": "~ 10/26(월)",
  "url": "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=54865562",
  "job_id": "54865562",
  "scraped_at": "2026-08-28T17:45:09+00:00"
}
```

(`salary` is null for most postings — boards only expose it when the employer chooses to publish it.)

Field coverage per board (honest — a field is `null` when the board does not expose it on list pages):

| Field | Saramin | JobKorea | Wanted |
|---|---|---|---|
| title, company, url, job_id | ✅ | ✅ | ✅ |
| deadline | ✅ | ✅ (ISO date) | ✅ when set (null = rolling) |
| region | ✅ | — | ✅ |
| experience / education / employment_type | ✅ | experience only ("신입 가능" flag) | — |
| salary | when posted | — | — |

## Notes & fair use

- Scrapes only publicly accessible listing pages / endpoints — no login, no personal data.
- Respect the target sites: keep result counts reasonable and schedule runs at sensible intervals.
- Postings are returned in each board's default relevance/latest order.

## Roadmap

- Detail-page enrichment (salary, full description)
- Region and experience-level filters
- Albamon (알바몬) part-time board support

Found an issue or need a Korean site scraped? Open an issue on this Actor — responses usually within a day.

---

*Keywords: Korean job board scraper, Korea jobs API, 사람인 크롤링, 잡코리아 크롤링, 원티드 채용공고 수집, Saramin scraper, JobKorea scraper, Wanted Korea jobs, Korean recruitment data, 채용공고 스크래핑, South Korea hiring data, Korean job postings dataset*
