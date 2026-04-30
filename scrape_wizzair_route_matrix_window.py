import argparse
import asyncio
import calendar
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.async_api import Browser, Page, async_playwright


EXTRACT_PRICES_JS = """() => {
    const raw = [];
    const elements = Array.from(document.querySelectorAll('div, button, li'));
    for (const el of elements) {
        const text = (el.textContent || '').replace(/\\s+/g, ' ').trim();
        if (!/\\bPLN\\b/i.test(text)) continue;
        if (/\\bPLN\\b/gi.test(text) && (text.match(/\\bPLN\\b/gi) || []).length !== 1) continue;
        const compactMatch = text.match(/^(\\d{1,2})\\D{0,20}?(\\d{2,4})\\s*PLN\\b/i);
        let dayMatch = null;
        let priceMatch = null;
        if (compactMatch) {
            dayMatch = [compactMatch[0], compactMatch[1]];
            priceMatch = [compactMatch[0], compactMatch[2]];
        } else {
            dayMatch = text.match(/^(\\d{1,2})\\b/);
            priceMatch = text.match(/(\\d{2,4})\\s*PLN\\b/i);
        }
        if (!dayMatch || !priceMatch) continue;
        const day = Number(dayMatch[1]);
        const price = Number(String(priceMatch[1]).replace(/\\s/g, ''));
        if (!Number.isFinite(day) || !Number.isFinite(price)) continue;
        if (day < 1 || day > 31) continue;
        if (price < 1 || price > 10000) continue;
        const rect = el.getBoundingClientRect();
        if (rect.width < 30 || rect.height < 30) continue;
        raw.push({ day, pricePLN: price, x: rect.x, y: rect.y });
    }
    raw.sort((a, b) => a.y - b.y || a.x - b.x);
    const outboundByDay = new Map();
    const returnByDay = new Map();
    const uniqueX = [...new Set(raw.map((r) => Math.round(r.x)))].sort((a, b) => a - b);
    let splitX = null;
    let bestGap = 0;
    for (let i = 1; i < uniqueX.length; i++) {
        const gap = uniqueX[i] - uniqueX[i - 1];
        if (gap > bestGap) {
            bestGap = gap;
            splitX = (uniqueX[i] + uniqueX[i - 1]) / 2;
        }
    }
    const hasTwoCalendars = bestGap >= 80;
    for (const item of raw) {
        const side = hasTwoCalendars && splitX !== null && item.x > splitX ? 'return' : 'outbound';
        const target = side === 'outbound' ? outboundByDay : returnByDay;
        if (!target.has(item.day)) target.set(item.day, { day: item.day, pricePLN: item.pricePLN });
    }
    const outbound = Array.from(outboundByDay.values()).sort((a, b) => a.day - b.day);
    const ret = Array.from(returnByDay.values()).sort((a, b) => a.day - b.day);
    return { outbound, return: ret };
}"""


NO_FLIGHTS_MARKERS = [
    "brak lot",
    "brak dost",
    "nie znaleziono lot",
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


def parse_airports_file(path: Path) -> Tuple[List[str], List[str]]:
    content = path.read_text(encoding="utf-8")

    def extract_list(name: str) -> List[str]:
        block = re.search(rf"{name}\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if not block:
            raise ValueError(f"List '{name}' missing in {path}")
        return re.findall(r'"([A-Z]{3})"', block.group(1))

    return extract_list("polish_airports"), extract_list("summer_destinations_from_poland")


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
        while True:
            body = await page.locator("body").inner_text()
            if "PLN" in body:
                break
            if any(marker in body.lower() for marker in NO_FLIGHTS_MARKERS):
                status = "no_flights"
                break
            if time.perf_counter() - start > max_wait_for_prices_seconds:
                status = "blocked_or_timeout"
                break
            await page.wait_for_timeout(700)

        outbound = []
        ret = []
        if status == "ok":
            extracted = await page.evaluate(EXTRACT_PRICES_JS)
            outbound = extracted.get("outbound", [])
            ret = extracted.get("return", [])

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
            clicked = await page.evaluate(
                """() => {
                    const icon = document.querySelector('.month-selector__pager__icon.icon__arrow--toright');
                    if (!icon) return false;
                    const target = icon.closest('button,[role="button"],a,div');
                    if (target instanceof HTMLElement) { target.click(); return true; }
                    return false;
                }"""
            )
            await page.wait_for_timeout(render_wait_ms if clicked else render_wait_ms + 400)

    return {
        "base_url": base_url,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "months": months,
    }


async def run(args: argparse.Namespace) -> None:
    now = datetime.now()
    start_month = args.start_month or f"{now.year}-{now.month:02d}"
    year, month = [int(x) for x in start_month.split("-")]

    origins, destinations = parse_airports_file(Path(args.airports_file))
    if args.route_pairs.strip():
        selected_routes = [tuple(x.strip().upper().split("-", 1)) for x in args.route_pairs.split(",") if x.strip()]
    else:
        selected_routes = [(o, d) for o in origins for d in destinations if o != d][: args.max_routes]

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
    print(f"Done. Total elapsed: {summary['total_elapsed_seconds']}s")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wizzair route matrix scraper with one browser per N routes.")
    parser.add_argument("--airports-file", default="Airports")
    parser.add_argument("--route-pairs", default="")
    parser.add_argument("--max-routes", type=int, default=5)
    parser.add_argument("--start-month", default=None)
    parser.add_argument("--month-count", type=int, default=4)
    parser.add_argument("--output-dir", default="route_matrix_output_window")
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
