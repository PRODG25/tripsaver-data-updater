import requests
import pandas as pd
from itertools import product
import time
import os
from datetime import datetime, timedelta
from urllib.parse import quote


# ----------------------------------
# CONFIG
# ----------------------------------
url = "https://google-flights2.p.rapidapi.com/api/v1/getCalendarPicker"
api_key = os.getenv("API_KEY")

headers = {
    "x-rapidapi-key": api_key,
    "x-rapidapi-host": "google-flights2.p.rapidapi.com"
}

#departure_ids = ["WAW", "KRK", "BER", "VIE", "ARN", "CPH", "MAD", "ATH", "FCO", "BUD", "PRG"]         # example: Warsaw, Krakow
#arrival_ids = ["BKK", "HKT", "MNL", "SIN", "KBV", "NRT", "ICN", "PEK", "MEX", "CUN", "MIA", "PVG", "ZNZ", "SID", "CMB", "MLE", "SGN", "PUJ", "HAN"]    # example: Bangkok, Phuket, Dubai
departure_ids = ["WAW"]#, "KRK"]        # example: Warsaw, Krakow
arrival_ids = ["BKK", "HKT"] 

trip_days_range = range(10, 11)         # 10 to 16 days

# ----------------------------------
# LOOP OVER ALL COMBINATIONS
# ----------------------------------
all_results = []  # list to collect dataframes


start_date = date.today().isoformat()

for dep, arr, days in product(departure_ids, arrival_ids, trip_days_range):
    params = {
        "departure_id": dep,
        "arrival_id": arr,
        "start_date": start_date,
        "end_date": "2026-04-30",
        "travel_class": "ECONOMY",
        "trip_type": "ROUND",
        "trip_days": str(days),
        "adults": "1",
        "currency": "PLN",
        "country_code": "PL"
    }

    try:
        response = requests.get(url, headers=headers, params=params, verify=True)
        data = response.json()

        # Only process if data is valid
        if data.get("status") and "data" in data:
            df_temp = pd.DataFrame(data["data"])
            df_temp["departure_airport"] = dep
            df_temp["arrival_airport"] = arr
            df_temp["trip_days"] = days
            all_results.append(df_temp)

        print(f"✅ {dep} → {arr} ({days} days): Success")

    except Exception as e:
        print(f"❌ {dep} → {arr} ({days} days): {e}")

    # To respect rate limits (good practice)
    time.sleep(0.5)

# ----------------------------------
# COMBINE ALL RESULTS
# ----------------------------------
if all_results:
    df_all = pd.concat(all_results, ignore_index=True)
    df_all['departure'] = pd.to_datetime(df_all['departure'])
    df_all['return'] = pd.to_datetime(df_all['return'])
    df_all = df_all.sort_values(by='price', ascending=True)
    print("✅ Combined DataFrame created successfully!")
else:
    print("⚠️ No data returned from API.")


exotic_airport_data = [
    # 🇵🇱 Poland
    {"IATA": "WAW", "City": "Warszawa", "Country": "Polska"},
    {"IATA": "KRK", "City": "Kraków", "Country": "Polska"},
    {"IATA": "KTW", "City": "Katowice", "Country": "Polska"},
    {"IATA": "POZ", "City": "Poznań", "Country": "Polska"},

    # 🇩🇪 Germany
    {"IATA": "BER", "City": "Berlin", "Country": "Niemcy"},

    # 🇦🇹 Austria
    {"IATA": "VIE", "City": "Wiedeń", "Country": "Austria"},

    # 🇸🇪 Sweden
    {"IATA": "ARN", "City": "Sztokholm", "Country": "Szwecja"},

    # 🇩🇰 Denmark
    {"IATA": "CPH", "City": "Kopenhaga", "Country": "Dania"},

    # 🇪🇸 Spain
    {"IATA": "MAD", "City": "Madryt", "Country": "Hiszpania"},

    # 🇬🇷 Greece
    {"IATA": "ATH", "City": "Ateny", "Country": "Grecja"},

    # 🇮🇹 Italy
    {"IATA": "FCO", "City": "Rzym", "Country": "Włochy"},

    # 🇭🇺 Hungary
    {"IATA": "BUD", "City": "Budapeszt", "Country": "Węgry"},

    # 🇨🇿 Czech Republic
    {"IATA": "PRG", "City": "Praga", "Country": "Czechy"},

    # 🇬🇧 United Kingdom
    {"IATA": "LGW", "City": "Londyn", "Country": "Wielka Brytania"},
    {"IATA": "LHR", "City": "Londyn", "Country": "Wielka Brytania"},

    # 🇹🇭 Thailand
    {"IATA": "BKK", "City": "Bangkok", "Country": "Tajlandia"},
    {"IATA": "HKT", "City": "Phuket", "Country": "Tajlandia"},
    {"IATA": "KBV", "City": "Krabi", "Country": "Tajlandia"},

    # 🇵🇭 Philippines
    {"IATA": "MNL", "City": "Manila", "Country": "Filipiny"},

    # 🇸🇬 Singapore
    {"IATA": "SIN", "City": "Singapur", "Country": "Singapur"},

    # 🇯🇵 Japan
    {"IATA": "NRT", "City": "Tokio", "Country": "Japonia"},

    # 🇰🇷 South Korea
    {"IATA": "ICN", "City": "Seul", "Country": "Korea Południowa"},

    # 🇨🇳 China
    {"IATA": "PEK", "City": "Pekin", "Country": "Chiny"},
    {"IATA": "PVG", "City": "Szanghaj", "Country": "Chiny"},

    # 🇲🇽 Mexico
    {"IATA": "MEX", "City": "Meksyk", "Country": "Meksyk"},
    {"IATA": "CUN", "City": "Cancún", "Country": "Meksyk"},

    # 🇺🇸 USA
    {"IATA": "MIA", "City": "Miami", "Country": "Stany Zjednoczone"},

    # 🇹🇿 Tanzania
    {"IATA": "ZNZ", "City": "Zanzibar", "Country": "Tanzania"},

    # 🇨🇻 Cape Verde
    {"IATA": "SID", "City": "Sal", "Country": "Wyspy Zielonego Przylądka"},
    {"IATA": "CMB", "City": "Colombo", "Country": "Sri Lanka"},
    {"IATA": "MLE", "City": "Male", "Country": "Malediwy"},
    {"IATA": "SGN", "City": "Ho Chi Min", "Country": "Wietnam"},
    {"IATA": "PUJ", "City": "Punta Cana", "Country": "Dominikana"},
    {"IATA": "HAN", "City": "Hanoi", "Country": "Wietnam"}

    
]


# Create DataFrame
exotic_airport_df = pd.DataFrame(exotic_airport_data)

# Preview
print(exotic_airport_df.head())

df = df_all
# Merge to get DepartureCity and DepartureCountry
df = df.merge(
    exotic_airport_df.rename(columns={"IATA": "departure_airport", "City": "DepartureCity", "Country": "DepartureCountry"}),
    on="departure_airport",
    how="left"
)

# Merge to get ArrivalCity and ArrivalCountry
df = df.merge(
    exotic_airport_df.rename(columns={"IATA": "arrival_airport", "City": "ArrivalCity", "Country": "ArrivalCountry"}),
    on="arrival_airport",
    how="left"
)
print(df.head())

df['return'] = pd.to_datetime(df['return'])
df['route'] = df['departure_airport'] + ' - ' + df['arrival_airport']
df['departure_month'] = df['return'].dt.to_period('M')

# Group by route and departure month, get top 10% cheapest flights per group
def top_10_percent(group):
    cutoff = int(len(group) * 0.1)
    if cutoff == 0:
        cutoff = 1
    return group.nsmallest(cutoff, 'price')

df = (
    df
    .groupby(['route', 'departure_month'], group_keys=False)
    .apply(top_10_percent)
)

def format_ddmm(date_val):
    return date_val.strftime("%d%m")  # ensure datetime

# Round trip

# === CREATE TODAY'S UNIQUE ID ===
df["route_id"] = (
    df["departure_airport"] + "_" +
    df["arrival_airport"] + "_" +
    df["departure"].astype(str) + "_" +
    df["return"].astype(str)
)

# === LOAD YESTERDAY'S FILE ===
yesterday_filename = "archive/exotic_flight_prices_raw.csv"

if os.path.exists(yesterday_filename):
    df_yesterday = pd.read_csv(yesterday_filename)

    df_yesterday["route_id"] = (
        df_yesterday["departure_airport"] + "_" +
        df_yesterday["arrival_airport"] + "_" +
        df_yesterday["departure"].astype(str) + "_" +
        df_yesterday["return"].astype(str)
    )
    
    # Select only needed columns
    df_yesterday = df_yesterday[["route_id", "price"]].rename(columns={"price": "price_yesterday"})
    df_yesterday = df_yesterday.sort_values("price_yesterday").drop_duplicates("route_id", keep="first")
    print("Duplicates in df:", df.duplicated(subset="route_id").sum())
    print("Duplicates in df_yesterday:", df_yesterday.duplicated(subset="route_id").sum())


    # Merge today's and yesterday's data
    df = df.merge(df_yesterday, on="route_id", how="left")
    print("After merge with yesterday:", len(df))

    # Calculate % change
    df["price_change_percent"] = ((df["price"] - df["price_yesterday"]) / df["price_yesterday"]) * 100
    df["price_change_percent"] = df["price_change_percent"].fillna(0).round(2)
else:
    print(f"⚠️ Yesterday's file '{yesterday_filename}' not found. Skipping price comparison.")
    df["price_change_percent"] = None

df = df.drop(columns=[
    'departure_month', 
    'route_id'
])

def format_skyscanner_date(dt):
    return dt.strftime("%y%m%d")  # Skyscanner uses YYMMDD

# --- Replace this with your Skyscanner parameters ---
ASSOCIATE_ID = "AFF_TRA_19354_00001"
UTM_SOURCE = "6439681-Trip Saver"
MARKER = "6439681"   # Example — update to yours
# ----------------------------------------------------


def create_trip_link(row):
    departure = row['departure_airport'].lower()
    destination = row['arrival_airport'].lower()
    return_airport = row['departure_airport'].lower()

    # Round trip format uses YYMMDD (via format_skyscanner_date)
    departure_date = row['departure'].strftime('%Y-%m-%d')
    return_date = row['return'].strftime('%Y-%m-%d')
    return (f"https://www.skyscanner.net/g/referrals/v1/flights/day-view/"
            f"?origin={departure}&destination={destination}&outboundDate={departure_date}&inboundDate={return_date}&market=PL&locale=pl-PL&currency=PLN&mediaPartnerId=6439681")
#2026-01-01

df['Round_Trip_Link'] = df.apply(create_trip_link, axis=1)

print(df.head())
# Create filename with today's date in DDMMYYYY format
filename = "exotic_flight_prices_raw.csv"
df.to_csv(filename, index=False)

print(f"DataFrame with all exotic fight prices created saved")    
