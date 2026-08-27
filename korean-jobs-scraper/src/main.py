# -*- coding: utf-8 -*-
"""Korean Jobs Scraper — Saramin, JobKorea, Wanted job postings by keyword."""
from __future__ import annotations

import asyncio
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
PAGE_SIZE = 40  # saramin/jobkorea default page sizes are <=40; wanted API limit max


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def scrape_saramin(client: httpx.AsyncClient, keyword: str, limit: int) -> list[dict]:
    items: list[dict] = []
    page = 1
    while len(items) < limit and page <= 5:
        url = ("https://www.saramin.co.kr/zf_user/search/recruit?searchType=search"
               f"&searchword={urllib.parse.quote(keyword)}&recruitPage={page}")
        r = await client.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.item_recruit")
        if not cards:
            break
        for el in cards:
            a = el.select_one(".job_tit a")
            corp = el.select_one(".corp_name a")
            conds = [s.get_text(strip=True) for s in el.select(".job_condition span")]
            date = el.select_one(".job_date .date")
            m = re.search(r"rec_idx=(\d+)", a.get("href", "")) if a else None
            if not (a and m):
                continue
            items.append({
                "source": "saramin",
                "title": (a.get("title") or a.get_text(strip=True)),
                "company": corp.get_text(strip=True) if corp else None,
                "conditions": conds,
                "deadline": date.get_text(strip=True) if date else None,
                "url": f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={m.group(1)}",
                "job_id": m.group(1),
                "scraped_at": _now(),
            })
            if len(items) >= limit:
                break
        page += 1
    return items


async def scrape_jobkorea(client: httpx.AsyncClient, keyword: str, limit: int) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    page = 1
    while len(items) < limit and page <= 5:
        url = ("https://www.jobkorea.co.kr/Search/?stext="
               f"{urllib.parse.quote(keyword)}&Page_No={page}")
        r = await client.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        got_new = False
        for a in soup.select('a[href*="/Recruit/GI_Read/"]'):
            m = re.search(r"/Recruit/GI_Read/(\d+)", a.get("href", ""))
            title = a.get_text(strip=True) or (a.get("title") or "")
            if not m or m.group(1) in seen or len(title) < 4:
                continue
            seen.add(m.group(1))
            got_new = True
            # company name: nearest preceding corp link when present
            corp = None
            card = a.find_parent(["article", "li", "div"])
            if card:
                c = card.select_one('a[href*="/Recruit/Co_Read/"], a[href*="corp"], .name, .corp-name')
                if c:
                    corp = c.get_text(strip=True) or None
            items.append({
                "source": "jobkorea",
                "title": title,
                "company": corp,
                "conditions": [],
                "deadline": None,
                "url": f"https://www.jobkorea.co.kr/Recruit/GI_Read/{m.group(1)}",
                "job_id": m.group(1),
                "scraped_at": _now(),
            })
            if len(items) >= limit:
                break
        if not got_new:
            break
        page += 1
    return items


async def scrape_wanted(client: httpx.AsyncClient, keyword: str, limit: int) -> list[dict]:
    items: list[dict] = []
    offset = 0
    while len(items) < limit and offset <= 80:
        url = ("https://www.wanted.co.kr/api/v4/jobs?country=kr&job_sort=job.latest_order"
               f"&query={urllib.parse.quote(keyword)}&limit=20&offset={offset}")
        r = await client.get(url)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            break
        for j in data:
            comp = (j.get("company") or {}).get("name")
            addr = (j.get("address") or {}).get("location")
            items.append({
                "source": "wanted",
                "title": j.get("position"),
                "company": comp,
                "conditions": [x for x in [addr] if x],
                "deadline": j.get("due_time"),
                "url": f"https://www.wanted.co.kr/wd/{j.get('id')}",
                "job_id": str(j.get("id")),
                "scraped_at": _now(),
            })
            if len(items) >= limit:
                break
        offset += 20
    return items


SCRAPERS = {"saramin": scrape_saramin, "jobkorea": scrape_jobkorea, "wanted": scrape_wanted}


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        keyword = (inp.get("keyword") or "").strip()
        if not keyword:
            raise ValueError('Input "keyword" is required.')
        sources = inp.get("sources") or ["saramin", "jobkorea", "wanted"]
        limit = max(1, min(int(inp.get("max_items_per_source") or 20), 100))

        async with httpx.AsyncClient(headers=HEADERS, timeout=25,
                                     follow_redirects=True) as client:
            total = 0
            for src in sources:
                fn = SCRAPERS.get(src)
                if not fn:
                    Actor.log.warning(f"unknown source skipped: {src}")
                    continue
                try:
                    rows = await fn(client, keyword, limit)
                except Exception as e:
                    Actor.log.error(f"{src} failed: {e}")
                    rows = []
                Actor.log.info(f"{src}: {len(rows)} postings")
                if rows:
                    await Actor.push_data(rows)
                    total += len(rows)
            Actor.log.info(f"done — total {total} postings for '{keyword}'")
