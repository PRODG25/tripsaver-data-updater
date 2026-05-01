import argparse
import os
from datetime import datetime

import pandas as pd


AIRPORT_TO_CITY = {
    "WMI": "WARS",
    "WAW": "WARS",
    "BBU": "BUCH",
    "OTP": "BUCH",
    "OSL": "OSLO",
    "TRF": "OSLO",
    "LTN": "LOND",
    "STN": "LOND",
    "LHR": "LOND",
    "LGW": "LOND",
    "FCO": "ROME",
    "CIA": "ROME",
    "BGY": "MILA",
    "MXP": "MILA",
}


def airport_for_link(value: str) -> str:
    return AIRPORT_TO_CITY.get(str(value).upper(), str(value).upper())


def create_trip_link(row: pd.Series) -> str:
    departure = str(row["IATA_Departure"]).lower()
    destination = str(row["IATA_Destination"]).lower()
    return_airport = str(row["IATA_Return"]).lower()
    departure_date = row["Departure Date"].strftime("%Y-%m-%d")
    return_date = row["Return Date"].strftime("%Y-%m-%d")

    if departure != return_airport:
        return (
            "https://skyscanner.net/g/referrals/v1/flights/multicity/"
            f"?mediaPartnerId=6439681&origin0={departure}&date0={departure_date}"
            f"&destination0={destination}&origin1={destination}&date1={return_date}"
            f"&destination1={return_airport}&adultsv2=1&market=PL&locale=pl-PL&currency=PLN"
        )

    return (
        "https://www.skyscanner.net/g/referrals/v1/flights/day-view/"
        f"?origin={departure}&destination={destination}&outboundDate={departure_date}"
        f"&inboundDate={return_date}&market=PL&locale=pl-PL&currency=PLN&mediaPartnerId=6439681"
    )


def top_percent(group: pd.DataFrame, fraction: float) -> pd.DataFrame:
    cutoff = int(len(group) * fraction)
    if cutoff == 0:
        cutoff = 1
    return group.nsmallest(cutoff, "total_price")


def build_round_trips(df: pd.DataFrame, top_fraction: float, max_total_price: float) -> pd.DataFrame:
    df = df.copy()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price", "departure"])
    df = df[df["price_type"] == "price"].copy()
    df["departure"] = pd.to_datetime(df["departure"], errors="coerce")
    df = df.dropna(subset=["departure"])

    df = df.rename(
        columns={
            "departure_airport": "DepartureAirport",
            "arrival_airport": "ArrivalAirport",
        }
    )

    outbound = df[df["DepartureCountry"] == "Polska"].copy()
    inbound = df[df["ArrivalCountry"] == "Polska"].copy()
    inbound = inbound.rename(
        columns={
            "DepartureAirport": "ReturnDepartureAirport",
            "ArrivalAirport": "ReturnArrivalAirport",
            "DepartureCity": "ReturnDepartureCity",
            "ArrivalCity": "ReturnArrivalCity",
            "DepartureCountry": "ReturnDepartureCountry",
            "ArrivalCountry": "ReturnArrivalCountry",
            "departure": "return_date",
            "price": "return_price",
            "provider": "return_provider",
            "source_price": "return_source_price",
            "source_currency": "return_source_currency",
        }
    )

    merged = pd.merge(
        outbound,
        inbound,
        left_on="ArrivalCity",
        right_on="ReturnDepartureCity",
        suffixes=("_out", "_in"),
    )
    merged["trip_duration_days"] = (merged["return_date"] - merged["departure"]).dt.days
    valid_trips = merged[
        (merged["trip_duration_days"] >= 2)
        & (merged["trip_duration_days"] <= 7)
    ].copy()

    valid_trips["price"] = pd.to_numeric(valid_trips["price"], errors="coerce").fillna(0).astype(int)
    valid_trips["return_price"] = pd.to_numeric(valid_trips["return_price"], errors="coerce").fillna(0).astype(int)
    valid_trips["total_price"] = valid_trips["price"] + valid_trips["return_price"]
    valid_trips["departure_month"] = valid_trips["return_date"].dt.to_period("M")
    valid_trips["route"] = valid_trips["DepartureCity"] + " - " + valid_trips["ArrivalCity"]

    filtered = (
        valid_trips.groupby(["route", "departure_month"], group_keys=False)
        .apply(lambda group: top_percent(group, top_fraction))
        .reset_index(drop=True)
    )

    final_df = filtered[
        [
            "DepartureCity",
            "ArrivalCity",
            "ArrivalCountry",
            "ReturnArrivalCity",
            "departure",
            "return_date",
            "trip_duration_days",
            "price",
            "return_price",
            "total_price",
            "DepartureAirport",
            "ReturnDepartureAirport",
            "ReturnArrivalAirport",
            "provider",
            "return_provider",
            "source_currency",
            "return_source_currency",
        ]
    ].rename(
        columns={
            "DepartureCity": "Outbound From",
            "ArrivalCity": "Destination",
            "ReturnArrivalCity": "Inbound To",
            "departure": "Departure Date",
            "return_date": "Return Date",
            "price": "Outbound Price",
            "return_price": "Inbound Price",
            "total_price": "Total Price",
            "trip_duration_days": "Trip Duration (Days)",
            "DepartureAirport": "IATA_Departure",
            "ReturnDepartureAirport": "IATA_Destination",
            "ReturnArrivalAirport": "IATA_Return",
            "provider": "Outbound Provider",
            "return_provider": "Inbound Provider",
            "source_currency": "Outbound Source Currency",
            "return_source_currency": "Inbound Source Currency",
        }
    )

    final_df["IATA_Departure"] = final_df["IATA_Departure"].apply(airport_for_link)
    final_df["IATA_Destination"] = final_df["IATA_Destination"].apply(airport_for_link)
    final_df["IATA_Return"] = final_df["IATA_Return"].apply(airport_for_link)

    final_df = final_df[final_df["Total Price"] <= max_total_price].sort_values("Total Price").reset_index(drop=True)
    final_df["Round_Trip_Link"] = final_df.apply(create_trip_link, axis=1)
    return final_df


def build_best_deals(round_trips: pd.DataFrame, previous_best_deals_csv: str) -> pd.DataFrame:
    df = round_trips.copy()
    df["Departure Date"] = pd.to_datetime(df["Departure Date"], errors="coerce")
    df["Route"] = df["Outbound From"] + "-" + df["Destination"]
    df["Month"] = df["Departure Date"].dt.to_period("M")
    df = df.dropna(subset=["Total Price", "Departure Date"])
    df["Total Price"] = pd.to_numeric(df["Total Price"], errors="coerce")
    df = df.dropna(subset=["Total Price"])

    stats = df.groupby(["Route", "Month"])["Total Price"].agg(["mean", "std"]).reset_index()
    stats.rename(columns={"mean": "AvgPrice", "std": "StdDev"}, inplace=True)
    df = df.merge(stats, on=["Route", "Month"], how="left")
    df["z_score"] = (df["Total Price"] - df["AvgPrice"]) / df["StdDev"]
    df = df[df["z_score"] <= -1].copy()
    df = df.sort_values("Total Price")

    df["route_id"] = (
        df["IATA_Departure"]
        + "_"
        + df["IATA_Destination"]
        + "_"
        + df["IATA_Return"]
        + "_"
        + df["Departure Date"].astype(str)
        + "_"
        + df["Return Date"].astype(str)
    )

    if os.path.exists(previous_best_deals_csv):
        previous = pd.read_csv(previous_best_deals_csv)
        previous["route_id"] = (
            previous["IATA_Departure"]
            + "_"
            + previous["IATA_Destination"]
            + "_"
            + previous["IATA_Return"]
            + "_"
            + previous["Departure Date"].astype(str)
            + "_"
            + previous["Return Date"].astype(str)
        )
        previous = previous[["route_id", "Total Price"]].rename(columns={"Total Price": "price_yesterday"})
        previous = previous.sort_values("price_yesterday").drop_duplicates("route_id", keep="first")
        df = df.merge(previous, on="route_id", how="left")
        df["price_change_percent"] = ((df["Total Price"] - df["price_yesterday"]) / df["price_yesterday"]) * 100
        df["price_change_percent"] = df["price_change_percent"].fillna(0).round(2)
    else:
        df["price_change_percent"] = None

    return df.drop(columns=["Month", "StdDev", "route_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build round-trip deal CSVs from combined one-way fare prices.")
    parser.add_argument("--input-csv", default="data/all_fares_best_prices.csv")
    parser.add_argument("--round-trips-csv", default="archive/multi_city_tickets.csv")
    parser.add_argument("--best-deals-csv", default="archive/best_deals_detected.csv")
    parser.add_argument("--previous-best-deals-csv", default="archive/best_deals_detected.csv")
    parser.add_argument("--top-fraction", type=float, default=0.2)
    parser.add_argument("--max-total-price", type=float, default=800)
    args = parser.parse_args()

    raw_df = pd.read_csv(args.input_csv)
    round_trips = build_round_trips(raw_df, args.top_fraction, args.max_total_price)
    os.makedirs(os.path.dirname(args.round_trips_csv) or ".", exist_ok=True)
    round_trips.to_csv(args.round_trips_csv, index=False, encoding="utf-8-sig")
    print(f"Saved {len(round_trips)} round trips to {args.round_trips_csv}")

    best_deals = build_best_deals(round_trips, args.previous_best_deals_csv)
    os.makedirs(os.path.dirname(args.best_deals_csv) or ".", exist_ok=True)
    best_deals.to_csv(args.best_deals_csv, index=False, encoding="utf-8-sig")
    print(f"Saved {len(best_deals)} best deals to {args.best_deals_csv}")


if __name__ == "__main__":
    main()
