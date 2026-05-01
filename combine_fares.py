import argparse
import csv
import json
import urllib.error
import urllib.request
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Tuple


FX_URL = "https://open.er-api.com/v6/latest/PLN"
DEFAULT_OUTPUT_CSV = "data/all_fares_best_prices.csv"
DEFAULT_SUMMARY_JSON = "data/all_fares_best_prices_summary.json"

OUTPUT_FIELDNAMES = [
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
    "provider",
    "source_price",
    "source_currency",
    "fx_rate_to_pln",
    "price_type",
    "class_of_service",
    "has_mac_flight",
    "route",
    "source_scraped_at_utc",
    "combined_at_utc",
]


def decimal_or_none(value: str) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def fetch_pln_rates(timeout_seconds: int) -> Dict[str, Decimal]:
    with urllib.request.urlopen(FX_URL, timeout=timeout_seconds) as response:
        payload = json.load(response)
    if payload.get("result") != "success":
        raise RuntimeError(f"FX API did not return success: {payload}")
    return {currency.upper(): Decimal(str(rate)) for currency, rate in payload.get("rates", {}).items()}


def load_pln_rates(args: argparse.Namespace) -> Tuple[Dict[str, Decimal], str]:
    if args.fx_json:
        payload = json.loads(Path(args.fx_json).read_text(encoding="utf-8"))
        rates = {currency.upper(): Decimal(str(rate)) for currency, rate in payload.get("rates", {}).items()}
        return rates, payload.get("source", args.fx_json)

    rates = fetch_pln_rates(args.timeout_seconds)
    return rates, FX_URL


def convert_to_pln(price: Decimal, currency: str, rates: Dict[str, Decimal]) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    currency = (currency or "").upper()
    if currency == "PLN":
        return price, Decimal("1")

    rate = rates.get(currency)
    if not rate:
        return None, None

    # Rates are quoted as: 1 PLN = rate units of source currency.
    return price / rate, Decimal("1") / rate


def normalized_rows(path: Path, provider: str, rates: Dict[str, Decimal], combined_at_utc: str) -> Tuple[List[Dict], List[Dict]]:
    rows = []
    rejected = []
    if not path.exists():
        rejected.append({"provider": provider, "file": str(path), "reason": "missing_input_file"})
        return rows, rejected

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for source_row in reader:
            if source_row.get("price_type") != "price":
                continue

            source_price = decimal_or_none(source_row.get("price"))
            source_currency = (source_row.get("currency") or "").upper()
            if source_price is None or not source_currency:
                rejected.append(
                    {
                        "provider": provider,
                        "route": source_row.get("route", ""),
                        "departure": source_row.get("departure", ""),
                        "reason": "missing_price_or_currency",
                    }
                )
                continue

            price_pln, fx_rate_to_pln = convert_to_pln(source_price, source_currency, rates)
            if price_pln is None or fx_rate_to_pln is None:
                rejected.append(
                    {
                        "provider": provider,
                        "route": source_row.get("route", ""),
                        "departure": source_row.get("departure", ""),
                        "currency": source_currency,
                        "reason": "missing_fx_rate",
                    }
                )
                continue

            row = {
                "departure": source_row.get("departure", ""),
                "return": source_row.get("return", ""),
                "price": str(price_pln.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "departure_airport": source_row.get("departure_airport", ""),
                "arrival_airport": source_row.get("arrival_airport", ""),
                "date_of_export": source_row.get("date_of_export", ""),
                "DepartureCity": source_row.get("DepartureCity", ""),
                "DepartureCountry": source_row.get("DepartureCountry", ""),
                "ArrivalCity": source_row.get("ArrivalCity", ""),
                "ArrivalCountry": source_row.get("ArrivalCountry", ""),
                "provider": provider,
                "source_price": str(source_price),
                "source_currency": source_currency,
                "fx_rate_to_pln": str(fx_rate_to_pln.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
                "price_type": source_row.get("price_type", ""),
                "class_of_service": source_row.get("class_of_service", ""),
                "has_mac_flight": source_row.get("has_mac_flight", ""),
                "route": source_row.get("route", ""),
                "source_scraped_at_utc": source_row.get("scraped_at_utc", ""),
                "combined_at_utc": combined_at_utc,
                "_price_pln_decimal": price_pln,
            }
            rows.append(row)

    return rows, rejected


def choose_best(rows: List[Dict]) -> List[Dict]:
    best_by_key: Dict[Tuple[str, str, str, str], Dict] = {}
    for row in rows:
        key = (
            row["departure_airport"],
            row["arrival_airport"],
            row["departure"],
            row["return"],
        )
        current = best_by_key.get(key)
        if current is None or row["_price_pln_decimal"] < current["_price_pln_decimal"]:
            best_by_key[key] = row

    output = []
    for row in best_by_key.values():
        clean_row = {field: row.get(field, "") for field in OUTPUT_FIELDNAMES}
        output.append(clean_row)
    return sorted(output, key=lambda item: (item["departure_airport"], item["arrival_airport"], item["departure"], item["return"]))


def write_csv(rows: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(summary: Dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def combine(args: argparse.Namespace) -> None:
    combined_at_utc = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    rates, fx_source = load_pln_rates(args)

    all_rows = []
    rejected = []
    provider_inputs = {
        "wizzair": Path(args.wizzair_csv),
        "ryanair": Path(args.ryanair_csv),
    }
    for provider, path in provider_inputs.items():
        rows, errors = normalized_rows(path, provider, rates, combined_at_utc)
        all_rows.extend(rows)
        rejected.extend(errors)

    best_rows = choose_best(all_rows)
    write_csv(best_rows, Path(args.output_csv))

    summary = {
        "output_csv": args.output_csv,
        "wizzair_csv": args.wizzair_csv,
        "ryanair_csv": args.ryanair_csv,
        "fx_source": fx_source,
        "raw_priced_rows": len(all_rows),
        "best_rows_written": len(best_rows),
        "provider_wins": {
            provider: sum(1 for row in best_rows if row["provider"] == provider)
            for provider in provider_inputs
        },
        "rejected_rows": rejected,
        "combined_at_utc": combined_at_utc,
    }
    write_summary(summary, Path(args.summary_json))

    print(f"Saved {len(best_rows)} best-price rows to {args.output_csv}", flush=True)
    print(f"Summary saved to {args.summary_json}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine Wizz Air and Ryanair fare CSVs into cheapest PLN fares.")
    parser.add_argument("--wizzair-csv", default="data/wizzair_fares_raw.csv")
    parser.add_argument("--ryanair-csv", default="data/ryanair_fares_raw.csv")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--summary-json", default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--fx-json", default="", help="Optional JSON file with rates quoted as 1 PLN = rate currency units.")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    combine(parser.parse_args())


if __name__ == "__main__":
    main()
