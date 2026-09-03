# -*- coding: utf-8 -*-
"""layout_unknown probe — cycle-08 (2026-09-03).

!!! EVERY PAGE IN THIS FILE IS AN ARTIFICIAL FIXTURE. !!!
None of the HTML below was ever served by Saramin, JobKorea, Danawa or Musinsa.
These are hand-written documents built to force the `layout_unknown` branch,
which has never fired in production on any of the three Actors. Passing here
means the branch is reachable and reports honestly for the shapes we imagined —
it does NOT mean the Actors survive a real layout change. Do not cite this file
as evidence of live behaviour.

Run: python tests/layout_unknown_probe.py   (no network, no Apify cloud run)
"""
from __future__ import annotations

import asyncio
import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(actor_dir: str, alias: str):
    """Import an Actor's src/main.py with the apify SDK stubbed out."""
    apify = types.ModuleType("apify")

    class _Log:
        @staticmethod
        def info(*a, **k): pass

        @staticmethod
        def warning(*a, **k): pass

    class _Actor:
        log = _Log()

    apify.Actor = _Actor
    sys.modules["apify"] = apify
    spec = importlib.util.spec_from_file_location(
        alias, ROOT / actor_dir / "src" / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class StubResponse:
    def __init__(self, text, payload=None):
        self.text = text
        self._payload = payload

    def raise_for_status(self): return None

    def json(self): return self._payload


class StubClient:
    """Serves one fixture document for any URL. No sockets are opened."""

    def __init__(self, text, payload=None):
        self._text = text
        self._payload = payload

    async def get(self, url, *a, **k):
        return StubResponse(self._text, self._payload)


# --- fixtures: pages with neither a result container nor a no-results marker ---
BLANK_HTML = "<html><body><div class='site-header'>Hello</div></body></html>"

DANAWA_EMPTY_CONTAINER = (
    "<html><body><div id='productListArea'>"
    "<div class='ad_banner'>광고</div>"   # container exists but holds no products
    "</div></body></html>")

# NOTE: the attribute quoting below is deliberate. musinsa parse_page locates the
# block with a regex that expects exactly `__NEXT_DATA__" type="application/json">`,
# so single-quoted attributes do not match. Written with single quotes these two
# fixtures fell into the "block not found" branch instead of the branches they were
# meant to exercise.
MUSINSA_NO_QUERY = (
    '<html><body><script id="__NEXT_DATA__" type="application/json">'
    '{"props":{"pageProps":{"dehydratedState":{"queries":[]}}}}'
    "</script></body></html>")

MUSINSA_NO_PAGES = (
    '<html><body><script id="__NEXT_DATA__" type="application/json">'
    '{"props":{"pageProps":{"dehydratedState":{"queries":['
    '{"queryKey":["search","goods",{"keyword":"test"}],'
    '"state":{"data":{"totalCount":0}}}]}}}}'
    "</script></body></html>")


def check(label: str, rows, state: str, reason: str) -> bool:
    ok_state = state == "layout_unknown"
    ok_not_empty = state != "empty_confirmed" and not rows
    ok_reason = bool(reason) and len(reason) > 20
    print(f"[{'PASS' if (ok_state and ok_not_empty and ok_reason) else 'FAIL'}] {label}")
    print(f"    1. state == layout_unknown          : {ok_state} (got '{state}')")
    print(f"    2. 0 rows NOT taken as empty result : {ok_not_empty}")
    print(f"    3. reason is human-readable         : {ok_reason} -> {reason!r}")
    return ok_state and ok_not_empty and ok_reason


def main() -> int:
    # Windows consoles default to cp949 here and the reason strings contain em-dashes.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    results = []

    danawa = _load("danawa-price-scraper", "danawa_main")
    results.append(check("danawa / no result container, no no-results notice",
                         *danawa.parse_page(BLANK_HTML)))
    results.append(check("danawa / container present but no products",
                         *danawa.parse_page(DANAWA_EMPTY_CONTAINER)))

    musinsa = _load("musinsa-scraper", "musinsa_main")
    results.append(check("musinsa / __NEXT_DATA__ absent",
                         *musinsa.parse_page(BLANK_HTML)))
    results.append(check("musinsa / search-goods query absent",
                         *musinsa.parse_page(MUSINSA_NO_QUERY)))
    results.append(check("musinsa / query present but no pages array",
                         *musinsa.parse_page(MUSINSA_NO_PAGES)))

    jobs = _load("korean-jobs-scraper", "jobs_main")
    client = StubClient(BLANK_HTML)
    results.append(check("jobs/saramin / neither #recruit_info_list nor .not_found",
                         *asyncio.run(jobs.scrape_saramin(client, "테스트", 20))))
    results.append(check("jobs/jobkorea / no embedded job objects, no no-results marker",
                         *asyncio.run(jobs.scrape_jobkorea(client, "테스트", 20))))

    # wanted is a JSON API, so its fixture is a payload rather than a document.
    # Before cycle-08 this source had no layout_unknown state at all: any payload
    # without a usable 'data' array came back as empty_confirmed, i.e. a shape
    # change was indistinguishable from a genuine no-match.
    results.append(check("jobs/wanted / payload has no 'data' array",
                         *asyncio.run(jobs.scrape_wanted(
                             StubClient("", {"message": "deprecated endpoint"}),
                             "테스트", 20))))
    results.append(check("jobs/wanted / payload is not an object at all",
                         *asyncio.run(jobs.scrape_wanted(
                             StubClient("", ["unexpected", "list"]), "테스트", 20))))

    # Control: an explicit empty list must still read as a genuine empty result,
    # not as a layout failure. This one is expected NOT to be layout_unknown.
    rows, state, reason = asyncio.run(jobs.scrape_wanted(
        StubClient("", {"data": []}), "테스트", 20))
    ok = (state == "empty_confirmed" and not rows)
    print(f"[{'PASS' if ok else 'FAIL'}] jobs/wanted / explicit empty list stays empty_confirmed")
    print(f"    state == empty_confirmed            : {ok} (got '{state}', {reason!r})")
    results.append(ok)

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
