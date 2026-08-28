# Musinsa Search Scraper — Korean Fashion Platform

Scrape product listings from [Musinsa (무신사)](https://www.musinsa.com), Korea's largest online fashion platform. Search any keyword and get structured product data: names, brands, **prices in KRW with sale rates**, stock status, gender category, and product links.

## Why this Actor?

Musinsa is the #1 destination for Korean fashion — the place where K-fashion trends, brand pricing, and demand signals appear first. It has no public API, and few working scrapers exist. Maintained by a developer based in Korea.

Use cases:

- **K-fashion market research** — what brands and products rank for any keyword
- **Price & discount monitoring** — track sale rates over time (schedule runs)
- **Brand intelligence** — see how a brand's catalog is priced and positioned
- **Sourcing & cross-border resale** — spot Korean street prices before importing

## Input

```json
{
  "keyword": "청바지",
  "max_items": 40
}
```

| Field | Type | Description |
|---|---|---|
| `keyword` | string | Product keyword — Korean works best, e.g. `반팔`, `청바지`, `nike` (required) |
| `max_items` | integer | 1–200 products (default 40, paginated automatically) |

## Output

Real row from an actual run:

```json
{
  "goods_no": "4818790",
  "name": "[10주년기획] 모두의 에센셜 데님 팬츠",
  "brand": "디미트리블랙",
  "final_price_krw": 34900,
  "normal_price_krw": 49900,
  "sale_rate": 30,
  "is_sold_out": false,
  "gender": "여성",
  "url": "https://www.musinsa.com/products/4818790",
  "image": "https://image.msscdn.net/images/goods_img/...",
  "scraped_at": "2026-08-29T13:00:00+00:00"
}
```

`final_price_krw` is the current selling price; `sale_rate` is the discount percentage against `normal_price_krw`.

## Notes & fair use

- Scrapes only public search result pages — no login, no personal data.
- Keep result counts reasonable and schedule runs at sensible intervals.
- Results follow Musinsa's default ranking for the query.

## Roadmap

- Category/ranking pages (not just keyword search)
- Review counts and ratings from product pages
- Brand-page catalog mode

**More Korean data Actors by the same developer:** [Korean Jobs Scraper](https://apify.com/ai94_jin/apify-actors) · [Danawa Price Scraper](https://apify.com/ai94_jin/apify-actors-1)

---

*Keywords: Musinsa scraper, Korean fashion data, K-fashion market research, 무신사 크롤링, 무신사 가격, Korean e-commerce scraper, Korea fashion prices, 패션 데이터 수집, Korean brand monitoring*
