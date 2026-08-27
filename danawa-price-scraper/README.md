# Danawa Price Scraper — Korean Price Comparison

Scrape product listings and **lowest prices in KRW** from [Danawa (다나와)](https://www.danawa.com), Korea's largest price-comparison site — the Korean equivalent of PriceGrabber/Geizhals, covering electronics, appliances, PC parts, and general goods.

Search any keyword and get structured product data: names, lowest prices across Korean shops, full spec summaries, and product links.

## Why this Actor?

Product pricing is the single most scraped data type on the web, but Korean market prices are hard to reach from outside — Danawa has no public API and almost no working scrapers exist. This Actor is maintained by a developer based in Korea.

Use cases:

- **Market entry research** — check real Korean street prices for any product category
- **Price monitoring** — track lowest prices for specific products over time (schedule daily runs)
- **E-commerce intelligence** — compare your prices against the Korean market
- **Sourcing & arbitrage** — spot price gaps between Korea and other markets

## Input

```json
{
  "keyword": "노트북",
  "max_items": 40
}
```

| Field | Type | Description |
|---|---|---|
| `keyword` | string | Product keyword — Korean works best, e.g. `노트북`, `에어컨`, `아이폰` (required) |
| `max_items` | integer | 1–200 products (default 40, paginated automatically) |

## Output

One dataset item per product:

```json
{
  "product_id": "12345678",
  "name": "APPLE 에어팟 프로3 MFHP4KH/A",
  "lowest_price_krw": 309620,
  "specs": "커널형 / 블루투스 v5.3 / 노이즈컨트롤 / ...",
  "url": "https://prod.danawa.com/info/?pcode=12345678",
  "image": "https://img.danawa.com/prod_img/...",
  "scraped_at": "2026-08-28T12:34:56+00:00"
}
```

`lowest_price_krw` is the lowest listed price across Korean shops at scrape time (integer, Korean won).

## Notes & fair use

- Scrapes only public search result pages — no login, no personal data.
- Keep result counts reasonable and schedule runs at sensible intervals.
- Results follow Danawa's default ranking for the query.

## Roadmap

- Per-shop price breakdown from product detail pages
- Category browsing (not just keyword search)
- Price-drop alert-friendly output format

Need another Korean e-commerce site (Coupang, Naver Shopping, Gmarket)? Open an issue on this Actor.
