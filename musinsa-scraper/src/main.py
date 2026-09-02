# -*- coding: utf-8 -*-
"""Musinsa Search Scraper — products from Korea's largest fashion platform."""
from __future__ import annotations

import json
import re
import urllib.parse
from datetime import datetime, timezone

import httpx

from apify import Actor

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(v) -> int | None:
    digits = re.sub(r"\D", "", str(v or ""))
    return int(digits) if digits else None


def _search_goods_query(data: dict):
    """The one query that holds the search result list.

    Scoped on purpose: a whole-tree walk for `goodsNo` would also pick up
    recommendation / banner buckets that Musinsa ships alongside the results,
    which is how a "no results" page can be served back as if it were a result set.
    """
    queries = (data.get("props", {}).get("pageProps", {})
               .get("dehydratedState", {}).get("queries") or [])
    for q in queries:
        key = q.get("queryKey")
        if (isinstance(key, list) and len(key) >= 3
                and key[0] == "search" and key[1] == "goods"
                and isinstance(key[2], dict) and "keyword" in key[2]):
            return q
    return None


def parse_page(html: str) -> tuple[list[dict], str, str]:
    """Return (rows, state, reason).

    state: ok | empty_confirmed | layout_unknown
    `layout_unknown` means we could not locate the result container — the page is
    refused rather than reported as an empty result set.
    """
    m = re.search(r'__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return [], "layout_unknown", "__NEXT_DATA__ block not found"
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        return [], "layout_unknown", f"__NEXT_DATA__ not valid JSON: {e}"

    query = _search_goods_query(data)
    if query is None:
        return [], "layout_unknown", "search/goods query absent from __NEXT_DATA__"

    pages = (query.get("state", {}).get("data", {}) or {}).get("pages")
    if not isinstance(pages, list):
        return [], "layout_unknown", "search/goods query carries no pages array"

    rows: list[dict] = []
    total_count = None
    for p in pages:
        if not isinstance(p, dict):
            continue
        items = p.get("items")
        if isinstance(items, list):
            rows.extend(x for x in items if isinstance(x, dict) and x.get("goodsNo"))
        pg = p.get("pagination")
        if isinstance(pg, dict) and total_count is None:
            total_count = pg.get("totalCount")

    if not rows:
        return [], "empty_confirmed", (
            f"Musinsa returned an empty item list (totalCount={total_count})")

    out = []
    for g in rows:
        out.append({
            "goods_no": str(g.get("goodsNo")),
            "name": g.get("goodsName"),
            "brand": g.get("brandName") or g.get("brand"),
            "final_price_krw": _to_int(g.get("finalPrice") or g.get("price")),
            "normal_price_krw": _to_int(g.get("normalPrice")),
            "sale_rate": _to_int(g.get("finalDiscount") or g.get("saleRate")),
            "is_sold_out": str(g.get("isSoldOut")).lower() == "true",
            "gender": g.get("displayGenderText") or None,
            "url": g.get("goodsLinkUrl")
                   or f"https://www.musinsa.com/products/{g.get('goodsNo')}",
            "image": g.get("thumbnail") or None,
            "scraped_at": _now(),
        })
    return out, "ok", f"{len(out)} items (totalCount={total_count})"


async def _make_client(proxy_url: str | None) -> httpx.AsyncClient:
    return httpx.AsyncClient(headers=HEADERS, timeout=25, follow_redirects=True,
                             proxy=proxy_url)


async def _client_chain():
    """Escalate on datacenter IP blocks: direct → Apify proxy → KR residential."""
    yield "direct", None
    try:
        cfg = await Actor.create_proxy_configuration()
        if cfg:
            yield "apify-proxy", await cfg.new_url()
    except Exception as e:
        Actor.log.warning(f"apify proxy unavailable: {e}")
    try:
        cfg = await Actor.create_proxy_configuration(groups=["RESIDENTIAL"],
                                                     country_code="KR")
        if cfg:
            yield "residential-kr", await cfg.new_url()
    except Exception as e:
        Actor.log.warning(f"residential proxy unavailable: {e}")


def _search_url(keyword: str, page: int) -> str:
    return ("https://www.musinsa.com/search/goods?"
            f"keyword={urllib.parse.quote(keyword)}&page={page}")


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        keyword = (inp.get("keyword") or "").strip()
        if not keyword:
            raise ValueError('Input "keyword" is required.')
        limit = max(1, min(int(inp.get("max_items") or 40), 200))

        client = None
        first_html = ""
        async for label, proxy_url in _client_chain():
            c = await _make_client(proxy_url)
            try:
                probe = await c.get(_search_url(keyword, 1))
                if probe.status_code == 200 and "__NEXT_DATA__" in probe.text:
                    Actor.log.info(f"connection ok via {label}")
                    client = c
                    first_html = probe.text
                    break
                Actor.log.warning(f"{label}: HTTP {probe.status_code} — trying next route")
            except Exception as e:
                Actor.log.warning(f"{label}: {e} — trying next route")
            await c.aclose()
        if client is None:
            raise RuntimeError("Musinsa unreachable from all routes (direct/proxy/residential)")

        items: list[dict] = []
        seen: set[str] = set()
        first_state, first_reason = "", ""
        try:
            page = 1
            while len(items) < limit and page <= 6:
                html = first_html if page == 1 else None
                if html is None:
                    r = await client.get(_search_url(keyword, page))
                    r.raise_for_status()
                    html = r.text
                rows, state, reason = parse_page(html)
                if page == 1:
                    first_state, first_reason = state, reason
                Actor.log.info(f"page {page}: {len(rows)} rows [{state}] {reason}")
                if state == "layout_unknown":
                    # Refuse to adopt a page we cannot read — never report it as empty.
                    break
                fresh = [x for x in rows if x["goods_no"] not in seen]
                for x in fresh:
                    seen.add(x["goods_no"])
                if not fresh:
                    break
                items.extend(fresh[: limit - len(items)])
                page += 1
        finally:
            await client.aclose()

        if not items:
            if first_state == "empty_confirmed":
                Actor.log.info(
                    f"Musinsa reports no results for '{keyword}' — empty dataset is genuine "
                    f"({first_reason})")
            else:
                raise RuntimeError(
                    f"0 products for '{keyword}' and Musinsa did not confirm an empty result "
                    f"[{first_state or 'unparsed'}: {first_reason}] — layout change or block. "
                    "Failing loudly instead of returning an empty dataset.")
        await Actor.push_data(items)
        Actor.log.info(f"done — {len(items)} products for '{keyword}' [{first_state}]")
