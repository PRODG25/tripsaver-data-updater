import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


RYANAIR_FARES_URL = "https://www.ryanair.com/api/farfnd/v4/oneWayFares/{origin}/{destination}/cheapestPerDay"
DEFAULT_INPUT_CSV = "data/ryanair_polish_routes.csv"
DEFAULT_OUTPUT_CSV = "data/ryanair_fares_may_aug.csv"
DEFAULT_SUMMARY_JSON = "data/ryanair_fares_may_aug_summary.json"

CSV_FIELDNAMES = [
    "departure",
    "return",
    "price",
    "departure_airport",
    "arrival_airport",
    "date_of_export",
    "DepartureCity",
    "DepartureCountry",
    "ArrivalCity",
    "ArrivalCountry",
    "price_type",
    "class_of_service",
    "has_mac_flight",
    "currency",
    "route",
    "scraped_at_utc",
]


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def month_starts(start_date: date, end_date: date) -> List[date]:
    current = date(start_date.year, start_date.month, 1)
    months = []
    while current <= end_date:
        months.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


def read_routes(path: Path, max_routes: int) -> Tuple[List[Tuple[str, str]], Dict[str, Dict[str, str]]]:
    routes: List[Tuple[str, str]] = []
    airport_lookup: Dict[str, Dict[str, str]] = {}
    seen = set()

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            origin = (row.get("origin") or "").strip().upper()
            destination = (row.get("destination") or "").strip().upper()
            if not origin or not destination or origin == destination:
                continue

            airport_lookup.setdefault(
                origin,
                {
                    "city": row.get("origin_city", ""),
                    "country": row.get("origin_country", ""),
                },
            )
            airport_lookup.setdefault(
                destination,
                {
                    "city": row.get("destination_city", ""),
                    "country": row.get("destination_country", ""),
                },
            )

            route = (origin, destination)
            if route in seen:
                continue
            seen.add(route)
            routes.append(route)
            if max_routes > 0 and len(routes) >= max_routes:
                break

    return routes, airport_lookup


def add_return_routes(routes: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    expanded: List[Tuple[str, str]] = []
    seen = set()
    for origin, destination in routes:
        for route in ((origin, destination), (destination, origin)):
            if route[0] == route[1] or route in seen:
                continue
            seen.add(route)
            expanded.append(route)
    return expanded


def airport_city(airport_lookup: Dict[str, Dict[str, str]], iata: str) -> str:
    return airport_lookup.get(iata, {}).get("city", "")


def airport_country(airport_lookup: Dict[str, Dict[str, str]], iata: str) -> str:
    return airport_lookup.get(iata, {}).get("country", "")


def request_month(origin: str, destination: str, month_start: date, args: argparse.Namespace) -> Dict:
    query = urllib.parse.urlencode(
        {
            "outboundMonthOfDate": month_start.isoformat(),
            "currency": args.currency,
        }
    )
    url = RYANAIR_FARES_URL.format(
        origin=urllib.parse.quote(origin),
        destination=urllib.parse.quote(destination),
    ) + f"?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "User-Agent": args.user_agent,
        },
    )
    with urllib.request.urlopen(request, timeout=args.timeout_seconds) as response:
        return json.load(response)


def extract_rows(
    payload: Dict,
    origin: str,
    destination: str,
    start_date: date,
    end_date: date,
    scraped_at_utc: str,
    date_of_export: str,
    airport_lookup: Dict[str, Dict[str, str]],
) -> List[Dict]:
    rows = []
    route = f"{origin}-{destination}"
    for fare in payload.get("outbound", {}).get("fares", []):
        day = parse_date(fare["day"])
        if not start_date <= day <= end_date:
            continue

        price = fare.get("price") or {}
        price_type = "price" if price.get("value") is not None else ""
        if fare.get("soldOut"):
            price_type = "soldOut"
        elif fare.get("unavailable"):
            price_type = "unavailable"

        rows.append(
            {
                "departure": day.isoformat(),
                "return": "",
                "price": price.get("value"),
                "departure_airport": origin,
                "arrival_airport": destination,
                "date_of_export": date_of_export,
                "DepartureCity": airport_city(airport_lookup, origin),
                "DepartureCountry": airport_country(airport_lookup, origin),
                "ArrivalCity": airport_city(airport_lookup, destination),
                "ArrivalCountry": airport_country(airport_lookup, destination),
                "price_type": price_type,
                "class_of_service": "",
                "has_mac_flight": "",
                "currency": price.get("currencyCode", ""),
                "route": route,
                "scraped_at_utc": scraped_at_utc,
            }
        )
    return rows


def write_csv(rows: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(summary: Dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def scrape_route(
    origin: str,
    destination: str,
    start_date: date,
    end_date: date,
    args: argparse.Namespace,
    scraped_at_utc: str,
    date_of_export: str,
    airport_lookup: Dict[str, Dict[str, str]],
) -> Tuple[List[Dict], List[Dict]]:
    rows_by_date: Dict[str, Dict] = {}
    errors = []
    for month_start in month_starts(start_date, end_date):
        for attempt in range(1, args.retries + 2):
            try:
                payload = request_month(origin, destination, month_start, args)
                for row in extract_rows(
                    payload,
                    origin,
                    destination,
                    start_date,
                    end_date,
                    scraped_at_utc,
                    date_of_export,
                    airport_lookup,
                ):
                    rows_by_date[row["departure"]] = row
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                if attempt > args.retries:
                    errors.append(
                        {
                            "route": f"{origin}-{destination}",
                            "month": month_start.isoformat(),
                            "error": str(exc),
                        }
                    )
                else:
                    time.sleep(args.retry_delay_seconds * attempt)
        time.sleep(args.delay_seconds)

    return [rows_by_date[key] for key in sorted(rows_by_date)], errors


def scrape(args: argparse.Namespace) -> None:
    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)
    if end_date < start_date:
        raise ValueError("--end-date must be on or after --start-date")

    scraped_at_utc = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    date_of_export = datetime.utcnow().date().isoformat()
    if args.input_csv:
        base_routes, airport_lookup = read_routes(Path(args.input_csv), args.max_routes)
    else:
        origin = args.origin.upper()
        destination = args.destination.upper()
        base_routes = [(origin, destination)]
        airport_lookup = {
            origin: {"city": "", "country": ""},
            destination: {"city": "", "country": ""},
        }

    routes = add_return_routes(base_routes) if args.include_return_routes else base_routes
    all_rows: List[Dict] = []
    all_errors: List[Dict] = []
    route_summaries = []

    for index, (origin, destination) in enumerate(routes, start=1):
        print(f"[{index}/{len(routes)}] {origin}-{destination}", flush=True)
        route_started = time.perf_counter()
        rows, errors = scrape_route(
            origin,
            destination,
            start_date,
            end_date,
            args,
            scraped_at_utc,
            date_of_export,
            airport_lookup,
        )
        all_rows.extend(rows)
        all_errors.extend(errors)
        route_summaries.append(
            {
                "route": f"{origin}-{destination}",
                "calendar_days": len(rows),
                "priced_days": sum(1 for row in rows if row.get("price_type") == "price"),
                "errors": len(errors),
                "elapsed_seconds": round(time.perf_counter() - route_started, 2),
            }
        )
        print(
            f"  -> {len(rows)} days, "
            f"{sum(1 for row in rows if row.get('price_type') == 'price')} priced, "
            f"{len(errors)} errors",
            flush=True,
        )

    write_csv(all_rows, Path(args.output_csv))

    summary = {
        "input_csv": args.input_csv,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "currency": args.currency,
        "output_csv": args.output_csv,
        "include_return_routes": args.include_return_routes,
        "base_routes_requested": len(base_routes),
        "route_directions_requested": len(routes),
        "rows_written": len(all_rows),
        "priced_rows": sum(1 for row in all_rows if row.get("price_type") == "price"),
        "missing_airport_metadata": sorted(
            {
                code
                for row in all_rows
                for code, city_key in (
                    (row.get("departure_airport", ""), "DepartureCity"),
                    (row.get("arrival_airport", ""), "ArrivalCity"),
                )
                if code and not row.get(city_key)
            }
        ),
        "errors": all_errors,
        "routes": route_summaries,
        "scraped_at_utc": scraped_at_utc,
    }
    write_summary(summary, Path(args.summary_json))

    print(f"Saved {len(all_rows)} rows to {args.output_csv}", flush=True)
    print(f"Priced rows: {summary['priced_rows']}", flush=True)
    print(f"Summary saved to {args.summary_json}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Ryanair cheapest-per-day one-way fares.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--max-routes", type=int, default=0, help="Limit base routes from input CSV; 0 means all.")
    parser.add_argument("--include-return-routes", action="store_true", default=True)
    parser.add_argument("--no-include-return-routes", action="store_false", dest="include_return_routes")
    parser.add_argument("--origin", default="WAW")
    parser.add_argument("--destination", default="ALC")
    parser.add_argument("--start-date", default="2026-09-01")
    parser.add_argument("--end-date", default="2026-10-30")
    parser.add_argument("--currency", default="PLN")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--summary-json", default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=3.0)
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    parser.add_argument(
        "--user-agent",
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
        ),
    )
    scrape(parser.parse_args())


if __name__ == "__main__":
    main()
