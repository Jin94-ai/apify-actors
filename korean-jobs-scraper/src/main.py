# -*- coding: utf-8 -*-
"""Korean Jobs Scraper — Saramin, JobKorea, Wanted job postings by keyword."""
from __future__ import annotations

import asyncio
import json
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


def _split_conditions(conds: list[str]) -> dict:
    """Saramin condition tags → structured fields (pattern-based, order-tolerant)."""
    out = {"region": None, "experience": None, "education": None,
           "employment_type": None, "salary": None}
    for c in conds:
        c = c.strip()
        if not c:
            continue
        if out["salary"] is None and re.search(r"만원|억원|시급|월급|연봉", c):
            out["salary"] = c
        elif out["experience"] is None and re.search(r"경력|신입", c):
            out["experience"] = c
        elif out["education"] is None and re.search(r"학력|졸|석사|박사", c):
            out["education"] = c
        elif out["employment_type"] is None and re.search(
                r"정규직|계약직|인턴|파견|프리랜서|아르바이트|위촉|기간제|병역특례", c):
            out["employment_type"] = c
        elif out["region"] is None:
            out["region"] = c
    return out


async def scrape_saramin(client: httpx.AsyncClient, keyword: str,
                         limit: int) -> tuple[list[dict], str, str]:
    """Saramin renders recommendation cards on its no-results page, so cards are only
    trusted inside the search-results container (#recruit_info_list). A page with
    div.not_found is a genuine empty result; anything else is an unrecognised layout."""
    items: list[dict] = []
    page = 1
    while len(items) < limit and page <= 5:
        url = ("https://www.saramin.co.kr/zf_user/search/recruit?searchType=search"
               f"&searchword={urllib.parse.quote(keyword)}&recruitPage={page}")
        r = await client.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        results_box = soup.select_one("div#recruit_info_list")
        if results_box is None:
            if page > 1:
                break  # ran past the last page of a normal result set
            if soup.select_one("div.not_found") is not None:
                return [], "empty_confirmed", "Saramin reports no results for this keyword"
            return [], "layout_unknown", (
                "neither the results container (#recruit_info_list) nor the "
                "no-results page (.not_found) was found — layout may have changed")
        cards = results_box.select("div.item_recruit")
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
                **_split_conditions(conds),
                "conditions": conds,
                "deadline": date.get_text(strip=True) if date else None,
                "url": f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={m.group(1)}",
                "job_id": m.group(1),
                "scraped_at": _now(),
            })
            if len(items) >= limit:
                break
        page += 1
    return items, ("ok" if items else "empty_confirmed"), ""


def _jobkorea_objects(html: str) -> list[dict]:
    """JobKorea embeds job data as escaped JSON in its React payload — extract each object."""
    s = html.replace('\\"', '"')
    out = []
    for m in re.finditer(r'"legacyJobNo"', s):
        # walk back to the object's opening brace
        depth = 0
        start = None
        for j in range(m.start(), max(0, m.start() - 6000), -1):
            ch = s[j]
            if ch == "}":
                depth += 1
            elif ch == "{":
                if depth == 0:
                    start = j
                    break
                depth -= 1
        if start is None:
            continue
        depth = 0
        end = None
        for j in range(start, min(len(s), start + 12000)):
            ch = s[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        if end is None:
            continue
        try:
            obj = json.loads(s[start:end])
        except Exception:
            continue
        if obj.get("legacyJobNo") and obj.get("title"):
            out.append(obj)
    return out


async def scrape_jobkorea(client: httpx.AsyncClient, keyword: str,
                          limit: int) -> tuple[list[dict], str, str]:
    items: list[dict] = []
    seen: set[str] = set()
    page = 1
    while len(items) < limit and page <= 5:
        url = ("https://www.jobkorea.co.kr/Search/?stext="
               f"{urllib.parse.quote(keyword)}&Page_No={page}")
        r = await client.get(url)
        r.raise_for_status()
        objects = _jobkorea_objects(r.text)
        if not objects and page == 1:
            if "검색결과가 없습니다" in r.text:
                return [], "empty_confirmed", "JobKorea reports no results for this keyword"
            return [], "layout_unknown", (
                "no job objects in the React payload and no no-results notice — "
                "the embedded data layout may have changed")
        got_new = False
        for o in objects:
            jid = str(o.get("legacyJobNo"))
            if jid in seen:
                continue
            seen.add(jid)
            got_new = True
            conds = []
            if o.get("isNewcomerJob"):
                conds.append("신입 가능")
            period = o.get("applicationPeriod") or {}
            items.append({
                "source": "jobkorea",
                "title": o.get("title"),
                "company": o.get("companyName") or o.get("postingCompanyName"),
                "region": None,
                "experience": "신입 가능" if o.get("isNewcomerJob") else None,
                "education": None,
                "employment_type": None,
                "salary": None,
                "conditions": conds,
                "deadline": (period.get("end") or "")[:10] or None,
                "url": f"https://www.jobkorea.co.kr/Recruit/GI_Read/{jid}",
                "job_id": jid,
                "scraped_at": _now(),
            })
            if len(items) >= limit:
                break
        if not got_new:
            break
        page += 1
    return items, ("ok" if items else "empty_confirmed"), ""


async def scrape_wanted(client: httpx.AsyncClient, keyword: str,
                        limit: int) -> tuple[list[dict], str, str]:
    items: list[dict] = []
    offset = 0
    while len(items) < limit and offset <= 80:
        url = ("https://www.wanted.co.kr/api/v4/jobs?country=kr&job_sort=job.latest_order"
               f"&query={urllib.parse.quote(keyword)}&limit=20&offset={offset}")
        r = await client.get(url)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            # the API answers with an explicit empty list, so this is a real empty result
            break
        for j in data:
            comp = (j.get("company") or {}).get("name")
            addr = (j.get("address") or {}).get("location")
            items.append({
                "source": "wanted",
                "title": j.get("position"),
                "company": comp,
                "region": addr,
                "experience": None,
                "education": None,
                "employment_type": None,
                "salary": None,
                "conditions": [x for x in [addr] if x],
                "deadline": j.get("due_time"),
                "url": f"https://www.wanted.co.kr/wd/{j.get('id')}",
                "job_id": str(j.get("id")),
                "scraped_at": _now(),
            })
            if len(items) >= limit:
                break
        offset += 20
    return items, ("ok" if items else "empty_confirmed"), ""


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
            report: list[str] = []
            confirmed_empty = 0
            for src in sources:
                fn = SCRAPERS.get(src)
                if not fn:
                    Actor.log.warning(f"unknown source skipped: {src}")
                    continue
                try:
                    rows, state, reason = await fn(client, keyword, limit)
                except Exception as e:
                    Actor.log.error(f"{src} failed: {e}")
                    rows, state, reason = [], "failed", str(e)
                note = f" ({reason})" if reason else ""
                Actor.log.info(f"{src}: {len(rows)} postings [{state}]{note}")
                report.append(f"{src}={len(rows)}/{state}")
                if state == "empty_confirmed":
                    confirmed_empty += 1
                elif state == "layout_unknown":
                    Actor.log.warning(f"{src}: results not adopted — {reason}")
                if rows:
                    await Actor.push_data(rows)
                    total += len(rows)

            Actor.log.info(f"done — total {total} postings for '{keyword}' "
                           f"| {', '.join(report)}")
            # Never let an empty dataset pass as success unless every source said so:
            # a silent zero would look identical to a genuine no-match to the user.
            if total == 0 and confirmed_empty < len(report):
                raise RuntimeError(
                    f"no postings collected for '{keyword}' and at least one source "
                    f"could not confirm a genuine empty result ({', '.join(report)}) — "
                    "failing loudly instead of returning an empty dataset")
