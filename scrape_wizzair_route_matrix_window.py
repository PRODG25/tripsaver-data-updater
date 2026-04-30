import argparse
import asyncio
import calendar
import csv
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.async_api import Browser, Page, async_playwright

POLISH_AIRPORTS = [
    "WAW",
    "WMI",
    "KRK",
    "GDN",
    "WRO",
    "KTW",
    "POZ",
]

SUMMER_DESTINATIONS_FROM_POLAND = [
    "RHO", "SKG", "CFU", "ZTH", "KGS",
    "MAD", "BCN", "AGP", "PMI", "ALC", "TFS", "SVQ", "IBZ", "VLC", "BIO",
    "FCO", "CIA", "MXP", "BGY", "VCE", "NAP", "BLQ", "PSA", "FLR", "TRN", "BRI", "PMO", "CTA", "OLB", "AHO", "VRN", "GOA",
    "SPU", "DBV", "ZAD",
    "LCA", "PFO",
    "VAR", "BOJ", "SOF",
    "TGD", "TIA",
    "FAO", "LIS", "OPO", "FNC",
    "CDG", "ORY", "BVA", "LYS", "NCE", "MRS",
    "KEF", "RMO", "BBU", "OTP", "CPH", "ARN", "GOT", "ATH", "BUD", "AUH",
    "IST", "SKP", "KUT", "MLA", "AMM", "RAK", "RBA", "AGA", "EIN", "OSL", "TRF", "AMS",
    "STN", "LTN", "LGW", "MAN", "DUB", "AYT", "ADB", "GLA", "EDI",
]


EXTRACT_ALL_PRICES_JS = """() => {
    const raw = [];
    const elements = Array.from(document.querySelectorAll('div, button, li'));
    for (const el of elements) {
        const text = (el.textContent || '').replace(/\\s+/g, ' ').trim();
        if (!/\\bPLN\\b/i.test(text)) continue;
        const dayMatch = text.match(/^(\\d{1,2})\\b/);
        if (!dayMatch) continue;
        const priceMatches = [...text.matchAll(/(\\d{2,4})\\s*PLN\\b/gi)];
        if (!priceMatches.length) continue;
        const day = Number(dayMatch[1]);
        // In some tiles Wizzair renders multiple PLN amounts (e.g. club vs regular).
        // Use the highest value as the public/base fare.
        const price = Math.max(...priceMatches.map((m) => Number(String(m[1]).replace(/\\s/g, ''))));
        if (!Number.isFinite(day) || !Number.isFinite(price)) continue;
        if (day < 1 || day > 31) continue;
        if (price < 1 || price > 10000) continue;
        const rect = el.getBoundingClientRect();
        if (rect.width < 30 || rect.height < 30) continue;
        raw.push({ day, pricePLN: price, x: rect.x, y: rect.y });
    }
    raw.sort((a, b) => a.y - b.y || a.x - b.x);
    const byDay = new Map();
    for (const item of raw) {
        if (!byDay.has(item.day)) {
            byDay.set(item.day, { day: item.day, pricePLN: item.pricePLN });
        } else {
            const current = byDay.get(item.day);
            if (item.pricePLN > current.pricePLN) byDay.set(item.day, { day: item.day, pricePLN: item.pricePLN });
        }
    }
    return Array.from(byDay.values()).sort((a, b) => a.day - b.day);
}"""


NO_FLIGHTS_MARKERS = [
    "brak lot",
    "brak dost",
    "nie znaleziono lot",
    "nie znaleziono ofert",
    "nie znaleźliśmy żadnych ofert",
    "no flights",
    "no available flights",
    "no results",
]


def add_months(year: int, month: int, offset: int) -> Tuple[int, int]:
    month_index = (year * 12 + (month - 1)) + offset
    return month_index // 12, (month_index % 12) + 1


def build_month_url(base_url: str, year: int, month: int) -> str:
    month_str = f"{year}-{month:02d}"
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{month_str}-01"
    end_date = f"{month_str}-{last_day:02d}"
    parsed = urlsplit(base_url)
    path = re.sub(r"/\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}$", f"/{start_date}/{end_date}", parsed.path)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["flexible"] = month_str
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(query, doseq=True), parsed.fragment))


def generate_routes_from_lists(
    *,
    include_return_routes: bool,
    max_routes: int,
) -> List[Tuple[str, str]]:
    routes: List[Tuple[str, str]] = []
    for origin in POLISH_AIRPORTS:
        for destination in SUMMER_DESTINATIONS_FROM_POLAND:
            if origin != destination:
                routes.append((origin, destination))

    if include_return_routes:
        for origin in SUMMER_DESTINATIONS_FROM_POLAND:
            for destination in POLISH_AIRPORTS:
                if origin != destination:
                    routes.append((origin, destination))

    if max_routes > 0:
        return routes[:max_routes]
    return routes


def build_base_url(origin: str, destination: str, start_month: str) -> str:
    return (
        "https://www.wizzair.com/pl-pl/loty/wyszukiwarka-lotow/"
        f"{origin.lower()}/{destination.lower()}/0/0/0/1/0/0/"
        f"{start_month}-01/{start_month}-28?flexible={start_month}&duration=1_week"
    )


async def try_accept_cookies(page: Page) -> None:
    for label in ["zaakceptuj", "akceptuj", "accept", "zgadzam", "agree"]:
        button = page.get_by_role("button", name=re.compile(label, re.IGNORECASE)).first
        try:
            if await button.is_visible(timeout=900):
                await button.click(timeout=900)
                await page.wait_for_timeout(250)
                return
        except Exception:
            continue


async def scrape_route_months(
    page: Page,
    base_url: str,
    start_year: int,
    start_month_num: int,
    month_count: int,
    render_wait_ms: int,
    max_wait_for_prices_seconds: int,
) -> dict:
    first_url = build_month_url(base_url, start_year, start_month_num)
    await page.goto(first_url, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(render_wait_ms)
    await try_accept_cookies(page)

    months = []
    for offset in range(month_count):
        year, month = add_months(start_year, start_month_num, offset)
        ym = f"{year}-{month:02d}"
        current_url = build_month_url(base_url, year, month)

        status = "ok"
        start = time.perf_counter()
        clicked_search_once = False
        while True:
            body = await page.locator("body").inner_text()
            if "PLN" in body:
                break

            # Some routes/months open in fare-finder search form state and never render
            # the calendar until user clicks "Wyszukaj" explicitly.
            if not clicked_search_once:
                search_clicked = await page.evaluate(
                    """() => {
                        const root = document.querySelector('.fare-finder--loading, .fare-finder__search--empty-list, .fare-finder');
                        if (!root) return false;
                        const candidates = Array.from(document.querySelectorAll('button, [role="button"], input[type="submit"]'));
                        for (const el of candidates) {
                            const txt = ((el.textContent || el.getAttribute('value') || '') + '').replace(/\\s+/g, ' ').trim();
                            if (!txt) continue;
                            if (/^wyszukaj$|^search$/i.test(txt)) {
                                if (el instanceof HTMLElement) {
                                    el.click();
                                    return true;
                                }
                            }
                        }
                        return false;
                    }"""
                )
                if search_clicked:
                    clicked_search_once = True
                    await page.wait_for_timeout(max(900, render_wait_ms))
                    continue

            lower_body = body.lower()
            has_no_offer_text = any(marker in lower_body for marker in NO_FLIGHTS_MARKERS)
            has_right_arrow = await page.evaluate(
                """() => !!document.querySelector('.month-selector__pager__icon.icon__arrow--toright')"""
            )
            # If "no offers" is visible and month navigation arrow is missing,
            # treat this month as unavailable and continue via next month URL fallback.
            if has_no_offer_text and not has_right_arrow:
                status = "no_flights"
                break
            if time.perf_counter() - start > max_wait_for_prices_seconds:
                status = "blocked_or_timeout"
                break
            await page.wait_for_timeout(700)

        outbound = []
        ret = []
        if status == "ok":
            outbound = await page.evaluate(EXTRACT_ALL_PRICES_JS)
            # Trigger return-calendar view by selecting one available outbound day.
            clicked_for_return = await page.evaluate(
                """() => {
                    const elements = Array.from(document.querySelectorAll('button, [role="button"], div, li'));
                    for (const el of elements) {
                        const text = (el.textContent || '').replace(/\\s+/g, ' ').trim();
                        if (!/^\\d{1,2}\\b/.test(text)) continue;
                        if (!/\\bPLN\\b/i.test(text)) continue;
                        const clickable = el.closest('button, [role="button"], a, div') || el;
                        if (clickable instanceof HTMLElement) {
                            clickable.click();
                            return true;
                        }
                    }
                    return false;
                }"""
            )
            if clicked_for_return:
                await page.wait_for_timeout(max(900, render_wait_ms))
                ret = await page.evaluate(EXTRACT_ALL_PRICES_JS)

        months.append(
            {
                "month": ym,
                "url": current_url,
                "status": status,
                "outbound_days_found": len(outbound),
                "return_days_found": len(ret),
                "data": {
                    "url": current_url,
                    "month": ym,
                    "status": status,
                    "outbound": [
                        {"day": x["day"], "date": f"{ym}-{int(x['day']):02d}", "pricePLN": x["pricePLN"]}
                        for x in outbound
                    ],
                    "return": [
                        {"day": x["day"], "date": f"{ym}-{int(x['day']):02d}", "pricePLN": x["pricePLN"]}
                        for x in ret
                    ],
                },
            }
        )

        if offset < month_count - 1:
            next_year, next_month = add_months(start_year, start_month_num, offset + 1)
            next_ym = f"{next_year}-{next_month:02d}"
            next_url = build_month_url(base_url, next_year, next_month)

            clicked = await page.evaluate(
                """(nextYm) => {
                    const icon = document.querySelector('.month-selector__pager__icon.icon__arrow--toright');
                    if (icon) {
                        const target = icon.closest('button,[role="button"],a,div');
                        if (target instanceof HTMLElement) {
                            target.click();
                            return "arrow";
                        }
                    }

                    const hrefNode = document.querySelector(`a[href*="flexible=${nextYm}"], button[data-month="${nextYm}"]`);
                    if (hrefNode instanceof HTMLElement) {
                        hrefNode.click();
                        return "month_link";
                    }

                    const candidates = Array.from(document.querySelectorAll('a,button,div,span'));
                    const monthTexts = [nextYm, nextYm.replace("-", "/"), nextYm.replace("-", ".")];
                    for (const el of candidates) {
                        const txt = (el.textContent || '').replace(/\\s+/g, ' ').trim();
                        if (!txt) continue;
                        if (!monthTexts.some((m) => txt.includes(m))) continue;
                        if (el instanceof HTMLElement) {
                            el.click();
                            return "text_match";
                        }
                    }
                    return "";
                }""",
                next_ym,
            )

            if clicked:
                await page.wait_for_timeout(render_wait_ms + 300)
            else:
                await page.goto(next_url, wait_until="domcontentloaded", timeout=90000)
                await page.wait_for_timeout(render_wait_ms)

    return {
        "base_url": base_url,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "months": months,
    }


async def run(args: argparse.Namespace) -> None:
    now = datetime.now()
    start_month = args.start_month or f"{now.year}-{now.month:02d}"
    year, month = [int(x) for x in start_month.split("-")]

    if args.route_pairs.strip():
        selected_routes = [tuple(x.strip().upper().split("-", 1)) for x in args.route_pairs.split(",") if x.strip()]
    else:
        selected_routes = generate_routes_from_lists(
            include_return_routes=args.include_return_routes,
            max_routes=args.max_routes,
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: Dict = {"start_month": start_month, "month_count": args.month_count, "routes_requested": len(selected_routes), "routes_processed": []}
    t0 = time.perf_counter()

    async with async_playwright() as p:
        for batch_start in range(0, len(selected_routes), args.routes_per_browser):
            batch = selected_routes[batch_start : batch_start + args.routes_per_browser]
            browser: Browser = await p.chromium.launch(headless=args.headless, slow_mo=0, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = await browser.new_page(viewport={"width": 1440, "height": 1200})

            for i, (origin, destination) in enumerate(batch, start=batch_start + 1):
                route = f"{origin}-{destination}"
                route_t0 = time.perf_counter()
                base_url = build_base_url(origin, destination, start_month)
                try:
                    payload = await asyncio.wait_for(
                        scrape_route_months(
                            page=page,
                            base_url=base_url,
                            start_year=year,
                            start_month_num=month,
                            month_count=args.month_count,
                            render_wait_ms=args.scraper_render_wait_ms,
                            max_wait_for_prices_seconds=args.scraper_max_wait_for_prices_seconds,
                        ),
                        timeout=args.route_timeout_seconds,
                    )
                    out_file = output_dir / f"{origin}_{destination}.json"
                    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    summary["routes_processed"].append(
                        {
                            "route": route,
                            "elapsed_seconds": round(time.perf_counter() - route_t0, 2),
                            "status": "ok",
                            "output_file": str(out_file),
                            "browser_batch": batch_start // args.routes_per_browser,
                        }
                    )
                except Exception as exc:
                    summary["routes_processed"].append(
                        {
                            "route": route,
                            "elapsed_seconds": round(time.perf_counter() - route_t0, 2),
                            "status": "failed",
                            "error": str(exc),
                            "browser_batch": batch_start // args.routes_per_browser,
                        }
                    )

                if i < len(selected_routes):
                    await asyncio.sleep(random.uniform(args.min_delay_seconds, args.max_delay_seconds))

            await page.close()
            await browser.close()

    summary["total_elapsed_seconds"] = round(time.perf_counter() - t0, 2)
    summary["finished_at_utc"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    summary["success_count"] = sum(1 for x in summary["routes_processed"] if x["status"] == "ok")
    summary["failure_count"] = sum(1 for x in summary["routes_processed"] if x["status"] == "failed")
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.csv_path:
        csv_rows = []
        for route_info in summary["routes_processed"]:
            if route_info.get("status") != "ok":
                continue
            route = route_info["route"]
            origin, destination = route.split("-", 1)
            route_file = Path(route_info["output_file"])
            if not route_file.exists():
                continue
            payload = json.loads(route_file.read_text(encoding="utf-8"))
            for month_data in payload.get("months", []):
                month = month_data.get("month")
                status = month_data.get("status", "")
                data = month_data.get("data", {})
                for direction in ("outbound", "return"):
                    for entry in data.get(direction, []):
                        csv_rows.append(
                            {
                                "route": route,
                                "origin": origin,
                                "destination": destination,
                                "month": month,
                                "direction": direction,
                                "day": entry.get("day"),
                                "date": entry.get("date"),
                                "pricePLN": entry.get("pricePLN"),
                                "month_status": status,
                                "exported_at_utc": summary["finished_at_utc"],
                            }
                        )

        csv_output_path = Path(args.csv_path)
        csv_output_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "route",
                    "origin",
                    "destination",
                    "month",
                    "direction",
                    "day",
                    "date",
                    "pricePLN",
                    "month_status",
                    "exported_at_utc",
                ],
            )
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"CSV saved: {csv_output_path}")

    print(f"Done. Total elapsed: {summary['total_elapsed_seconds']}s")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wizzair route matrix scraper with one browser per N routes.")
    parser.add_argument("--route-pairs", default="")
    parser.add_argument("--max-routes", type=int, default=0, help="0 means all generated routes.")
    parser.add_argument("--include-return-routes", action="store_true", default=False)
    parser.add_argument("--start-month", default=None)
    parser.add_argument("--month-count", type=int, default=4)
    parser.add_argument("--output-dir", default="route_matrix_output_window")
    parser.add_argument("--csv-path", default="", help="Optional CSV output path in repo.")
    parser.add_argument("--routes-per-browser", type=int, default=5)
    parser.add_argument("--route-timeout-seconds", type=int, default=300)
    parser.add_argument("--scraper-max-wait-for-prices-seconds", type=int, default=25)
    parser.add_argument("--scraper-render-wait-ms", type=int, default=1400)
    parser.add_argument("--min-delay-seconds", type=float, default=1.0)
    parser.add_argument("--max-delay-seconds", type=float, default=2.0)
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", action="store_false", dest="headless")
    args = parser.parse_args()
    asyncio.run(run(args))
