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


def parse_page(html: str) -> list[dict]:
    """Musinsa embeds the goods list in __NEXT_DATA__ — walk it for goods objects."""
    m = re.search(r'__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    rows: list[dict] = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("goodsNo") and node.get("goodsName"):
                rows.append(node)
            else:
                for v in node.values():
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
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
    return out


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
        try:
            page = 1
            while len(items) < limit and page <= 6:
                html = first_html if page == 1 else None
                if html is None:
                    r = await client.get(_search_url(keyword, page))
                    r.raise_for_status()
                    html = r.text
                rows = parse_page(html)
                fresh = [x for x in rows if x["goods_no"] not in seen]
                for x in fresh:
                    seen.add(x["goods_no"])
                Actor.log.info(f"page {page}: {len(rows)} rows ({len(fresh)} new)")
                if not fresh:
                    break
                items.extend(fresh[: limit - len(items)])
                page += 1
        finally:
            await client.aclose()
        if not items:
            Actor.log.warning(
                f"0 products for '{keyword}' — if this keyword should have results, "
                "Musinsa's embedded data layout may have changed (check __NEXT_DATA__ structure)")
        await Actor.push_data(items)
        Actor.log.info(f"done — {len(items)} products for '{keyword}'")
