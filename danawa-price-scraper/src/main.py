# -*- coding: utf-8 -*-
"""Danawa Price Scraper — product prices from Korea's largest price-comparison site."""
from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from apify import Actor

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for el in soup.select("li.prod_item"):
        name_el = el.select_one("p.prod_name a")
        if not name_el:
            continue
        pid = re.sub(r"\D", "", el.get("id") or "")
        price_el = el.select_one(".price_sect strong")
        price = None
        if price_el:
            digits = re.sub(r"\D", "", price_el.get_text())
            price = int(digits) if digits else None
        spec_el = el.select_one(".spec_list")
        img = el.select_one(".thumb_image img")
        img_src = (img.get("src") or img.get("data-src") or "") if img else ""
        rows.append({
            "product_id": pid or None,
            "name": name_el.get_text(strip=True),
            "lowest_price_krw": price,
            "specs": spec_el.get_text(" ", strip=True) if spec_el else None,
            "url": name_el.get("href"),
            "image": ("https:" + img_src) if img_src.startswith("//") else (img_src or None),
            "scraped_at": _now(),
        })
    return rows


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        keyword = (inp.get("keyword") or "").strip()
        if not keyword:
            raise ValueError('Input "keyword" is required.')
        limit = max(1, min(int(inp.get("max_items") or 40), 200))

        items: list[dict] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(headers=HEADERS, timeout=25,
                                     follow_redirects=True) as client:
            page = 1
            while len(items) < limit and page <= 6:
                url = ("https://search.danawa.com/dsearch.php?"
                       f"query={urllib.parse.quote(keyword)}&page={page}")
                r = await client.get(url)
                r.raise_for_status()
                rows = parse_page(r.text)
                fresh = [x for x in rows if (x["product_id"] or x["name"]) not in seen]
                for x in fresh:
                    seen.add(x["product_id"] or x["name"])
                Actor.log.info(f"page {page}: {len(rows)} rows ({len(fresh)} new)")
                if not fresh:
                    break
                items.extend(fresh[: limit - len(items)])
                page += 1
        await Actor.push_data(items)
        Actor.log.info(f"done — {len(items)} products for '{keyword}'")
