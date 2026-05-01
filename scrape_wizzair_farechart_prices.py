import argparse
import ast
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


FARECHART_URL = "https://be.wizzair.com/28.8.0/Api/asset/farechart"
WIZZ_MAP_URL = "https://be.wizzair.com/28.8.0/Api/asset/map?languageCode=pl-pl"
DEFAULT_INPUT_CSV = "data/wizzair_polish_routes.csv"
DEFAULT_OUTPUT_CSV = "data/wizzair_farechart_prices_may_aug.csv"
DEFAULT_SUMMARY_JSON = "data/wizzair_farechart_prices_may_aug_summary.json"
DEFAULT_AIRPORT_DATA_SCRIPT = "data-updater.py"

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


def read_routes(path: Path, max_routes: int) -> List[Tuple[str, str]]:
    routes: List[Tuple[str, str]] = []
    seen = set()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            origin = (row.get("origin") or "").strip().upper()
            destination = (row.get("destination") or "").strip().upper()
            if not origin or not destination or origin == destination:
                continue
            route = (origin, destination)
            if route in seen:
                continue
            seen.add(route)
            routes.append(route)
            if max_routes > 0 and len(routes) >= max_routes:
                break
    return routes


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


def parse_airport_data_from_script(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "airport_data" for target in node.targets):
            continue
        airport_data = ast.literal_eval(node.value)
        return {
            entry["IATA"].upper(): {
                "city": entry.get("City", ""),
                "country": entry.get("Country", ""),
            }
            for entry in airport_data
            if entry.get("IATA")
        }
    return {}


def city_from_wizz_short_name(short_name: str) -> str:
    city = (short_name or "").replace("\r", " ").replace("\n", " ").strip()
    city = city.replace(" (wszystkie lotniska)", "")
    city = city.split("–", 1)[0].split("-", 1)[0].strip()
    return city


def fetch_wizz_airport_data(timeout_seconds: int) -> Dict[str, Dict[str, str]]:
    try:
        with urllib.request.urlopen(WIZZ_MAP_URL, timeout=timeout_seconds) as response:
            data = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        print(f"Could not fetch Wizz airport metadata: {exc}", flush=True)
        return {}

    airports = {}
    for city in data.get("cities", []):
        iata = (city.get("iata") or "").strip().upper()
        if not iata:
            continue
        airports[iata] = {
            "city": city_from_wizz_short_name(city.get("shortName", "")),
            "country": city.get("countryName", ""),
        }
    return airports


def load_airport_lookup(args: argparse.Namespace) -> Dict[str, Dict[str, str]]:
    lookup = fetch_wizz_airport_data(args.timeout_seconds)
    # Prefer the curated Polish names from data-updater.py where available.
    lookup.update(parse_airport_data_from_script(Path(args.airport_data_script)))
    return lookup


def airport_city(airport_lookup: Dict[str, Dict[str, str]], iata: str) -> str:
    return airport_lookup.get(iata, {}).get("city", "")


def airport_country(airport_lookup: Dict[str, Dict[str, str]], iata: str) -> str:
    return airport_lookup.get(iata, {}).get("country", "")


def center_dates_for_range(start_date: date, end_date: date, day_interval: int) -> List[date]:
    step_days = max(1, day_interval * 2)
    current = start_date + timedelta(days=day_interval)
    centers = []
    while current <= end_date + timedelta(days=day_interval):
        centers.append(current)
        current += timedelta(days=step_days)
    return centers


def farechart_payload(
    origin: str,
    destination: str,
    center_date: date,
    adult_count: int,
    child_count: int,
    day_interval: int,
    wdc: bool,
) -> Dict:
    return {
        "isRescueFare": False,
        "adultCount": adult_count,
        "childCount": child_count,
        "dayInterval": day_interval,
        "wdc": wdc,
        "isFlightChange": False,
        "flightList": [
            {
                "departureStation": origin,
                "arrivalStation": destination,
                "date": center_date.isoformat(),
            }
        ],
    }


def request_farechart(
    origin: str,
    destination: str,
    center_date: date,
    args: argparse.Namespace,
) -> Dict:
    payload = farechart_payload(
        origin=origin,
        destination=destination,
        center_date=center_date,
        adult_count=args.adult_count,
        child_count=args.child_count,
        day_interval=args.day_interval,
        wdc=args.wdc,
    )
    referer = (
        "https://www.wizzair.com/pl-pl/booking/select-flight/"
        f"{origin}/{destination}/{center_date.isoformat()}/null/{args.adult_count}/{args.child_count}/0/null"
    )
    request = urllib.request.Request(
        FARECHART_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.wizzair.com",
            "Referer": referer,
            "User-Agent": args.user_agent,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=args.timeout_seconds) as response:
        return json.load(response)


def extract_rows(
    payload: Dict,
    route: str,
    requested_origin: str,
    requested_destination: str,
    start_date: date,
    end_date: date,
    scraped_at_utc: str,
    date_of_export: str,
    airport_lookup: Dict[str, Dict[str, str]],
) -> List[Dict]:
    rows = []
    for flight in payload.get("outboundFlights", []):
        flight_date = datetime.fromisoformat(flight["date"].replace("Z", "+00:00")).date()
        if not start_date <= flight_date <= end_date:
            continue
        price = flight.get("price") or {}
        rows.append(
            {
                "route": route,
                "departure": flight_date.isoformat(),
                "return": "",
                "price": price.get("amount"),
                "departure_airport": requested_origin,
                "arrival_airport": requested_destination,
                "date_of_export": date_of_export,
                "DepartureCity": airport_city(airport_lookup, requested_origin),
                "DepartureCountry": airport_country(airport_lookup, requested_origin),
                "ArrivalCity": airport_city(airport_lookup, requested_destination),
                "ArrivalCountry": airport_country(airport_lookup, requested_destination),
                "currency": price.get("currencyCode"),
                "price_type": flight.get("priceType"),
                "class_of_service": flight.get("classOfService"),
                "has_mac_flight": flight.get("hasMacFlight"),
                "scraped_at_utc": scraped_at_utc,
            }
        )
    return rows


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
    route = f"{origin}-{destination}"
    by_date: Dict[str, Dict] = {}
    errors = []

    for center_date in center_dates_for_range(start_date, end_date, args.day_interval):
        for attempt in range(1, args.retries + 2):
            try:
                payload = request_farechart(origin, destination, center_date, args)
                for row in extract_rows(
                    payload,
                    route,
                    origin,
                    destination,
                    start_date,
                    end_date,
                    scraped_at_utc,
                    date_of_export,
                    airport_lookup,
                ):
                    by_date[row["departure"]] = row
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                if attempt > args.retries:
                    errors.append(
                        {
                            "route": route,
                            "center_date": center_date.isoformat(),
                            "error": str(exc),
                        }
                    )
                else:
                    time.sleep(args.retry_delay_seconds * attempt)
        time.sleep(args.delay_seconds)

    return [by_date[key] for key in sorted(by_date)], errors


def write_csv(rows: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(summary: Dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)
    if end_date < start_date:
        raise ValueError("--end-date must be on or after --start-date")

    base_routes = read_routes(Path(args.input_csv), args.max_routes)
    routes = add_return_routes(base_routes) if args.include_return_routes else base_routes
    scraped_at_utc = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    date_of_export = datetime.utcnow().date().isoformat()
    airport_lookup = load_airport_lookup(args)

    all_rows: List[Dict] = []
    all_errors: List[Dict] = []
    route_summaries = []
    started = time.perf_counter()

    for index, (origin, destination) in enumerate(routes, start=1):
        route_started = time.perf_counter()
        print(f"[{index}/{len(routes)}] {origin}-{destination}", flush=True)
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
        "output_csv": args.output_csv,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
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
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "scraped_at_utc": scraped_at_utc,
    }
    write_summary(summary, Path(args.summary_json))

    print(f"Saved {len(all_rows)} rows to {args.output_csv}", flush=True)
    print(f"Summary saved to {args.summary_json}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Wizz Air farechart prices for route CSVs.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--summary-json", default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--airport-data-script", default=DEFAULT_AIRPORT_DATA_SCRIPT)
    parser.add_argument("--start-date", default="2026-05-01")
    parser.add_argument("--end-date", default="2026-08-31")
    parser.add_argument("--include-return-routes", action="store_true", default=True)
    parser.add_argument("--no-include-return-routes", action="store_false", dest="include_return_routes")
    parser.add_argument("--max-routes", type=int, default=0, help="Limit base routes from input CSV; 0 means all.")
    parser.add_argument("--adult-count", type=int, default=1)
    parser.add_argument("--child-count", type=int, default=0)
    parser.add_argument("--day-interval", type=int, default=9)
    parser.add_argument("--wdc", action="store_true", default=False)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=4.0)
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    parser.add_argument(
        "--user-agent",
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
        ),
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
