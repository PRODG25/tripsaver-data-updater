import requests
import pandas as pd
import os
import json
from datetime import datetime, timedelta
import time

df = pd.read_excel("flight_prices_05082025.xlsx")
print(f"DataFrame with all fight prices created saved")


# Ensure datetime format
df['departure'] = pd.to_datetime(df['departure'])
df['return'] = pd.to_datetime(df['return'])

# Rename columns to make merging easier
df = df.rename(columns={
    'departure_airport': 'DepartureAirport',
    'arrival_airport': 'ArrivalAirport',
    'DepartureCity': 'DepartureCity',
    'ArrivalCity': 'ArrivalCity',
    'DepartureCountry': 'DepartureCountry',
    'ArrivalCountry': 'ArrivalCountry'
})

# Create outbound and inbound datasets
outbound = df[df['DepartureCountry'] == 'Poland'].copy()
inbound = df[df['ArrivalCountry'] == 'Poland'].copy()

# Rename inbound columns to avoid collisions when merging
inbound = inbound.rename(columns={
    'DepartureAirport': 'ReturnDepartureAirport',
    'ArrivalAirport': 'ReturnArrivalAirport',
    'DepartureCity': 'ReturnDepartureCity',
    'ArrivalCity': 'ReturnArrivalCity',
    'DepartureCountry': 'ReturnDepartureCountry',
    'ArrivalCountry': 'ReturnArrivalCountry',
    'departure': 'return_date',
    'price': 'return_price'
})

# Merge on destination city (city you go to = city you return from)
merged = pd.merge(
    outbound,
    inbound,
    left_on='ArrivalCity',
    right_on='ReturnDepartureCity',
    suffixes=('_out', '_in')
)

# Calculate trip duration
merged['trip_duration_days'] = (merged['return_date'] - merged['departure']).dt.days

# Filter for trips between 2 and 7 days
valid_trips = merged[
    (merged['trip_duration_days'] >= 2) & 
    (merged['trip_duration_days'] <= 7)
].copy()

# Calculate total price
valid_trips['total_price'] = valid_trips['price'] + valid_trips['return_price']

# Extract month for grouping
valid_trips['departure_month'] = valid_trips['return_date'].dt.to_period('M')

# Create route identifier
valid_trips['route'] = valid_trips['DepartureCity'] + ' - ' + valid_trips['ArrivalCity']

# Group by route and departure month, get top 10% cheapest flights per group
def top_10_percent(group):
    cutoff = int(len(group) * 0.2)
    if cutoff == 0:
        cutoff = 1
    return group.nsmallest(cutoff, 'total_price')

filtered_df = (
    valid_trips
    .groupby(['route', 'departure_month'], group_keys=False)
    .apply(top_10_percent)
)

# Final columns
final_df = filtered_df[[
    'DepartureCity', 'ArrivalCity', 'ArrivalCountry', 'ReturnArrivalCity',
    'departure', 'return_date',
    'trip_duration_days', 'price', 'return_price', 'total_price', 'DepartureAirport', 'ReturnDepartureAirport', 'ReturnArrivalAirport'
]].rename(columns={
    'DepartureCity': 'Outbound From',
    'ArrivalCity': 'Destination',
    'ReturnArrivalCity': 'Inbound To',
    'departure': 'Departure Date',
    'return_date': 'Return Date',
    'price': 'Outbound Price',
    'return_price': 'Inbound Price',
    'total_price': 'Total Price',
    'trip_duration_days': 'Trip Duration (Days)',
    'DepartureAirport': 'IATA_Departure',
    'ReturnDepartureAirport': 'IATA_Destination',
    'ReturnArrivalAirport': 'IATA_Return'
})

# Sort by Total Price
final_df = final_df[final_df['Total Price'] <= 2000].sort_values(by='Total Price').reset_index(drop=True)




# Updated function (now works with pd.Timestamp or datetime.datetime)
def format_date(dt):
    dt_adjusted = dt
    return dt_adjusted.strftime('%y%m%d')

# Create outbound link:
final_df['Outbound_Link'] = final_df.apply(
    lambda row: f"https://www.skyscanner.pl/transport/loty/{row['IATA_Departure']}/{row['IATA_Destination']}/{format_date(row['Departure Date'])}/"
                "?"
                "adultsv2=1",
    axis=1
)

# Create inbound link:
final_df['Inbound_Link'] = final_df.apply(
    lambda row: f"https://www.skyscanner.pl/transport/loty/{row['IATA_Destination']}/{row['IATA_Return']}/{format_date(row['Return Date'])}/"
                "?"
                "adultsv2=1",
    axis=1
)

# Create round trip link (only if departure = return airport)
final_df['Round_Trip_Link'] = final_df.apply(
    lambda row: (
        f"https://www.skyscanner.pl/transport/loty/{row['IATA_Departure']}/{row['IATA_Destination']}/"
        f"{format_date(row['Departure Date'])}/{format_date(row['Return Date'])}/"
        "?"
        "adultsv2=1"
    ) if row['IATA_Departure'] == row['IATA_Return'] else None,
    axis=1
)

# Export to Excel
today_str = datetime.today().strftime('%d%m%Y')

filename2 = f"multi_city_tickets.csv"
final_df.to_csv(filename2, index=False, encoding='utf-8-sig')


print("Filtered dataframe with top 50% cheapest round-trips by route and month saved.")

#best deals

# Load data
df = final_df

# Ensure date format
df['Departure Date'] = pd.to_datetime(df['Departure Date'], errors='coerce')

# Create route and departure month
df['Route'] = df['Outbound From'] + '-' + df['Destination']
df['Month'] = df['Departure Date'].dt.to_period('M')

# Drop rows with missing or invalid price data
df = df.dropna(subset=['Total Price', 'Departure Date'])
df['Total Price'] = pd.to_numeric(df['Total Price'], errors='coerce')
df = df.dropna(subset=['Total Price'])

# Group by Route and Month to compute stats
stats = df.groupby(['Route', 'Month'])['Total Price'].agg(['mean', 'std']).reset_index()
stats.rename(columns={'mean': 'AvgPrice', 'std': 'StdDev'}, inplace=True)

# Merge statistics back into main DataFrame
df = df.merge(stats, on=['Route', 'Month'], how='left')

# Calculate z-score
df['z_score'] = (df['Total Price'] - df['AvgPrice']) / df['StdDev']

# Filter best deals: at least 1 std dev below avg
best_deals = df[df['z_score'] <= -1].copy()

# Sort by best deals first
df = df.sort_values(by='Total Price')

# === CREATE TODAY'S UNIQUE ID ===
df["route_id"] = (
    df["IATA_Departure"] + "_" +
    df["IATA_Destination"] + "_" +
    df["IATA_Return"] + "_" +
    df["Departure Date"].astype(str) + "_" +
    df["Return Date"].astype(str)
)

# === LOAD YESTERDAY'S FILE ===
yesterday_filename = "archive/best_deals_detected.csv"

if os.path.exists(yesterday_filename):
    df_yesterday = pd.read_csv(yesterday_filename)

    df_yesterday["route_id"] = (
        df_yesterday["IATA_Departure"] + "_" +
        df_yesterday["IATA_Destination"] + "_" +
        df_yesterday["IATA_Return"] + "_" +
        df_yesterday["Departure Date"].astype(str) + "_" +
        df_yesterday["Return Date"].astype(str)
    )

    # Select only needed columns
    df_yesterday = df_yesterday[["route_id", "Total Price"]].rename(columns={"Total Price": "price_yesterday"})

    # Merge today's and yesterday's data
    df = df.merge(df_yesterday, on="route_id", how="left")

    # Calculate % change
    df["price_change_percent"] = ((df["Total Price"] - df["price_yesterday"]) / df["price_yesterday"]) * 100
    df["price_change_percent"] = df["price_change_percent"].fillna(0).round(2)
else:
    print(f"⚠️ Yesterday's file '{yesterday_filename}' not found. Skipping price comparison.")
    df["price_change_percent"] = None


output_filename = f"best_deals_detected.csv"
df.to_csv(output_filename, index=False)

print(f"✅ Saved {len(df)} best deals to '{output_filename}' with price change info.")
