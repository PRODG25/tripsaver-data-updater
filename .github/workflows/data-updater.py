import requests
import pandas as pd
import os
import json
from datetime import datetime, timedelta
import time


polish_airports = [
    "WAW",  # Warsaw Chopin
    "WMI",  # Warsaw Modlin
    "KRK",  # Krakow
    "GDN",  # Gdansk
    "WRO",  # Wroclaw
    "KTW",  # Katowice
    "POZ",  # Poznan
]

summer_destinations_from_poland = [
    # Greece
    "HER",  # Heraklion (Crete)
    "RHO",  # Rhodes
    "SKG",  # Thessaloniki
    "CFU",  # Corfu
    "ZTH",  # Zakynthos
    "KGS",  # Kos
    "CHQ",  # Chania

    # Spain
    "MAD",  # Madrid Barajas
    "BCN",  # Barcelona El Prat
    "AGP",  # Málaga
    "PMI",  # Palma de Mallorca
    "ALC",  # Alicante
    "TFS",  # Tenerife South
    "SVQ",  # Seville
    "IBZ",  # Ibiza
    "VLC",  # Valencia
    "BIO",  # Bilbao
    "TFN",  # Tenerife North
    "SPC",  # La Palma
    "GRX",  # Granada

    # Italy
    "FCO",  # Rome Fiumicino
    "CIA",  # Rome Ciampino
    "MXP",  # Milan Malpensa
    "BGY",  # Bergamo (Orio al Serio)
    "VCE",  # Venice Marco Polo
    "NAP",  # Naples
    "BLQ",  # Bologna
    "PSA",  # Pisa
    "FLR",  # Florence
    "TRN",  # Turin
    "BRI",  # Bari
    "PMO",  # Palermo
    "CTA",  # Catania
    "OLB",  # Olbia
    "AHO",  # Alghero
    "VRN",  # Verona
    "GOA",  # Genoa

    # Croatia
    "SPU",  # Split
    "DBV",  # Dubrovnik
    "ZAD",  # Zadar

    # Cyprus
    "LCA",  # Larnaca
    "PFO",  # Paphos

    # Bulgaria
    "VAR",  # Varna
    "BOJ",  # Burgas
    "SOF",  #Sofia

    # Montenegro
    "TGD",  # Podgorica

    # Albania
    "TIA",  # Tirana
 # Portugal
    "FAO",  # Faro (Algarve)
    "LIS",  # Lisbon
    "OPO",  # Porto
    "FNC",  # Madeira

    # France
    "CDG",  # Paris Charles de Gaulle
    "ORY",  # Paris Orly
    "BVA",  # Paris Beauvais
    "LYS",  # Lyon–Saint-Exupéry
    "NCE",  # Nice Côte d'Azur
    "MRS",  # Marseille Provence
    "BIQ",  # Biarritz Pays Basque

    "KEF",  # Reyjkjavik

    "RMO",  #Moldova
    "BBU",  #Bucharest
    "OTP",  #Bucharest
    "CPH",  #Copenhagen
    "ARN",  #Stocholm
    "GOT",  #Gothenburg
    "ATH",  #Athens
    "BUD",  #Budapest
    "AUH",  #AbuDhabi
    "IST",  #Istanbul
    "SKP",  #Skopje
    "KUT",  #Kutaisi
    "MLA", #Malta
    "AMM", #Amman
    "RAK", #Marakech
    "RBA", #Rabat
    "AGA", #Agadir
    "EIN", #Eindhoven
    "OSL", #Oslo
    "TRF", #Oslo
    "AMS", #Amsterdam
    "STN", #Stansted
    "LTN", #Luton
    "LGW", #Gatwick
    "MAN", #Manchester
    "DUB", #Dublin
    "AYT", # Antalya
    "ADB", #Izmir
    "GLA", #Glasgow
    "EDI", #Edingburgh
	

]




#Creating List of Routes
# Load excluded routes
excluded_df = pd.read_excel("routes_to_exclude.xlsx")

# Create a set of tuples: (departure_id, arrival_id)
excluded_routes = set(
    tuple(route.split("-")) for route in excluded_df["route"]
)

# Initialize routes list
routes = []

# FROM Poland → Summer Destinations
for departure in polish_airports:
    for arrival in summer_destinations_from_poland:
        if (departure.upper(), arrival.upper()) not in excluded_routes:
            routes.append({
                "departure_id": departure,
                "arrival_id": arrival
            })

# FROM Summer Destinations → Poland
for departure in summer_destinations_from_poland:
    for arrival in polish_airports:
        if (departure.upper(), arrival.upper()) not in excluded_routes:
            routes.append({
                "departure_id": departure,
                "arrival_id": arrival
            })


print(f"Total number of routes (API requests): {len(routes)}")


url = "https://google-flights2.p.rapidapi.com/api/v1/getCalendarPicker"

api_key = os.getenv("API_KEY")

headers = {
	"x-rapidapi-key": api_key,
	"x-rapidapi-host": "google-flights2.p.rapidapi.com"
}


# Store all results
all_results = []

# Query API for each route
for route in routes:
    params = {
        "departure_id": route["departure_id"],
        "arrival_id": route["arrival_id"],
        "travel_class": "ECONOMY",
        "trip_type": "ONE_WAY",
        "adults": "1",
        "currency": "PLN",
        "country_code": "PL",
        "end_date":"2025-12-30"
    }
    time.sleep(0.5)
    response = requests.get(url, headers=headers, params=params, verify=False)
    
    if response.status_code == 200:
        data = response.json()
        for entry in data.get("data", []):
            entry["departure_airport"] = route["departure_id"]
            entry["arrival_airport"] = route["arrival_id"]
            all_results.append(entry)
    else:
        print(f"Failed for {route['departure_id']} to {route['arrival_id']}")

# Convert to DataFrame
df = pd.DataFrame(all_results)

# Optional: reorder columns
df = df[["departure", "return", "price", "departure_airport", "arrival_airport"]]

# Define data as a list of dictionaries
airport_data = [
    # Poland
    {"IATA": "WAW", "City": "Warsaw", "Country": "Poland"},
    {"IATA": "WMI", "City": "Warsaw", "Country": "Poland"},
    {"IATA": "KRK", "City": "Krakow", "Country": "Poland"},
    {"IATA": "GDN", "City": "Gdansk", "Country": "Poland"},
    {"IATA": "WRO", "City": "Wroclaw", "Country": "Poland"},
    {"IATA": "KTW", "City": "Katowice", "Country": "Poland"},
    {"IATA": "POZ", "City": "Poznan", "Country": "Poland"},
    {"IATA": "RZE", "City": "Rzeszow", "Country": "Poland"},
    {"IATA": "LUZ", "City": "Lublin", "Country": "Poland"},


    # Greece
    {"IATA": "HER", "City": "Heraklion", "Country": "Greece"},
    {"IATA": "RHO", "City": "Rhodes", "Country": "Greece"},
    {"IATA": "SKG", "City": "Thessaloniki", "Country": "Greece"},
    {"IATA": "CFU", "City": "Corfu", "Country": "Greece"},
    {"IATA": "ZTH", "City": "Zakynthos", "Country": "Greece"},
    {"IATA": "KGS", "City": "Kos", "Country": "Greece"},
    {"IATA": "CHQ", "City": "Chania", "Country": "Greece"},

    # Spain
    {"IATA": "MAD", "City": "Madrid", "Country": "Spain"},
    {"IATA": "BCN", "City": "Barcelona", "Country": "Spain"},
    {"IATA": "AGP", "City": "Malaga", "Country": "Spain"},
    {"IATA": "PMI", "City": "Palma de Mallorca", "Country": "Spain"},
    {"IATA": "ALC", "City": "Alicante", "Country": "Spain"},
    {"IATA": "TFS", "City": "Tenerife", "Country": "Spain"},
    {"IATA": "SVQ", "City": "Seville", "Country": "Spain"},
    {"IATA": "IBZ", "City": "Ibiza", "Country": "Spain"},
    {"IATA": "VLC", "City": "Valencia", "Country": "Spain"},
    {"IATA": "BIO", "City": "Bilbao", "Country": "Spain"},
    {"IATA": "TFN", "City": "Tenerife", "Country": "Spain"},
    {"IATA": "SPC", "City": "La Palma", "Country": "Spain"},
    {"IATA": "GRX", "City": "Granada", "Country": "Spain"},

    # Italy
    {"IATA": "FCO", "City": "Rome", "Country": "Italy"},
    {"IATA": "CIA", "City": "Rome", "Country": "Italy"},
    {"IATA": "MXP", "City": "Milan", "Country": "Italy"},
    {"IATA": "BGY", "City": "Milan", "Country": "Italy"},
    {"IATA": "VCE", "City": "Venice", "Country": "Italy"},
    {"IATA": "NAP", "City": "Naples", "Country": "Italy"},
    {"IATA": "BLQ", "City": "Bologna", "Country": "Italy"},
    {"IATA": "PSA", "City": "Pisa", "Country": "Italy"},
    {"IATA": "FLR", "City": "Florence", "Country": "Italy"},
    {"IATA": "TRN", "City": "Turin", "Country": "Italy"},
    {"IATA": "BRI", "City": "Bari", "Country": "Italy"},
    {"IATA": "PMO", "City": "Palermo", "Country": "Italy"},
    {"IATA": "CTA", "City": "Catania", "Country": "Italy"},
    {"IATA": "OLB", "City": "Olbia", "Country": "Italy"},
    {"IATA": "AHO", "City": "Alghero", "Country": "Italy"},
    {"IATA": "VRN", "City": "Verona", "Country": "Italy"},
    {"IATA": "GOA", "City": "Genoa", "Country": "Italy"},

    # Croatia
    {"IATA": "SPU", "City": "Split", "Country": "Croatia"},
    {"IATA": "DBV", "City": "Dubrovnik", "Country": "Croatia"},
    {"IATA": "ZAD", "City": "Zadar", "Country": "Croatia"},

    # Cyprus
    {"IATA": "LCA", "City": "Larnaca", "Country": "Cyprus"},
    {"IATA": "PFO", "City": "Paphos", "Country": "Cyprus"},

    # Bulgaria
    {"IATA": "VAR", "City": "Varna", "Country": "Bulgaria"},
    {"IATA": "BOJ", "City": "Burgas", "Country": "Bulgaria"},
    {"IATA": "SOF", "City": "Sofia", "Country": "Bulgaria"},

    # Montenegro
    {"IATA": "TGD", "City": "Podgorica", "Country": "Montenegro"},

    # Albania
    {"IATA": "TIA", "City": "Tirana", "Country": "Albania"},

    # Portugal
    {"IATA": "FAO", "City": "Faro", "Country": "Portugal"},
    {"IATA": "LIS", "City": "Lisbon", "Country": "Portugal"},
    {"IATA": "OPO", "City": "Porto", "Country": "Portugal"},
    {"IATA": "FNC", "City": "Madeira", "Country": "Portugal"},

    # France
    {"IATA": "CDG", "City": "Paris", "Country": "France"},
    {"IATA": "ORY", "City": "Paris", "Country": "France"},
    {"IATA": "BVA", "City": "Paris", "Country": "France"},
    {"IATA": "LYS", "City": "Lyon", "Country": "France"},
    {"IATA": "NCE", "City": "Nice", "Country": "France"},
    {"IATA": "MRS", "City": "Marseille", "Country": "France"},
    {"IATA": "BIQ", "City": "Biarritz", "Country": "France"},

    # Iceland
    {"IATA": "KEF", "City": "Reykjavik", "Country": "Iceland"},

    # Other
    {"IATA": "RMO", "City": "Chisinau", "Country": "Moldova"},
    {"IATA": "BBU", "City": "Bucharest", "Country": "Romania"},
    {"IATA": "OTP", "City": "Bucharest", "Country": "Romania"},
    {"IATA": "CPH", "City": "Copenhagen", "Country": "Denmark"},
    {"IATA": "ARN", "City": "Stockholm", "Country": "Sweden"},
    {"IATA": "GOT", "City": "Gothenburg", "Country": "Sweden"},
    {"IATA": "ATH", "City": "Athens", "Country": "Greece"},
    {"IATA": "BUD", "City": "Budapest", "Country": "Hungary"},
    {"IATA": "AUH", "City": "Abu Dhabi", "Country": "United Arab Emirates"},
    {"IATA": "IST", "City": "Istanbul", "Country": "Turkey"},
    {"IATA": "SKP", "City": "Skopje", "Country": "North Macedonia"},
    {"IATA": "KUT", "City": "Kutaisi", "Country": "Georgia"},
    {"IATA": "MLA", "City": "Valletta", "Country": "Malta"},
    {"IATA": "AMM", "City": "Amman", "Country": "Jordan"},
    {"IATA": "RAK", "City": "Marrakesh", "Country": "Morocco"},
    {"IATA": "AGA", "City": "Agadir", "Country": "Morocco"},
    {"IATA": "RBA", "City": "Rabat", "Country": "Morocco"},
    {"IATA": "EIN", "City": "Eindhoven", "Country": "Netherlands"},
    {"IATA": "AMS", "City": "Amsterdam", "Country": "Netherlands"},
    {"IATA": "OSL", "City": "Oslo", "Country": "Norway"},
    {"IATA": "TRF", "City": "Oslo", "Country": "Norway"},
    {"IATA": "STN", "City": "London", "Country": "United Kingdom"},
    {"IATA": "LTN", "City": "London", "Country": "United Kingdom"},
    {"IATA": "LGW", "City": "London", "Country": "United Kingdom"},
    {"IATA": "MAN", "City": "Manchester", "Country": "United Kingdom"},
    {"IATA": "DUB", "City": "Dublin", "Country": "Ireland"},
    {"IATA": "AYT", "City": "Antalya", "Country": "Turkey"},
    {"IATA": "ADB", "City": "Izmir", "Country": "Turkey"},
    {"IATA": "GLA", "City": "Glasgow", "Country": "Scotland"},
    {"IATA": "EDI", "City": "Edinburgh", "Country": "Scotland"},



]

# Create DataFrame
airport_df = pd.DataFrame(airport_data)

# Preview
print(airport_df.head())



# Add today's date to a new column
df['date_of_export'] = pd.to_datetime('today').normalize()

# Merge to get DepartureCity and DepartureCountry
df = df.merge(
    airport_df.rename(columns={"IATA": "departure_airport", "City": "DepartureCity", "Country": "DepartureCountry"}),
    on="departure_airport",
    how="left"
)

# Merge to get ArrivalCity and ArrivalCountry
df = df.merge(
    airport_df.rename(columns={"IATA": "arrival_airport", "City": "ArrivalCity", "Country": "ArrivalCountry"}),
    on="arrival_airport",
    how="left"
)

# Create filename with today's date in DDMMYYYY format
filename = "flight_prices_raw.csv"
df.to_csv(filename, index=False, encoding='utf-8-sig')

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
    cutoff = int(len(group) * 0.5)
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
final_df = final_df.sort_values(by='Total Price').reset_index(drop=True)




# Updated function (now works with pd.Timestamp or datetime.datetime)
def format_date(dt):
    dt_adjusted = dt
    return dt_adjusted.strftime('%y%m%d')

# Create outbound link:
final_df['Outbound_Link'] = final_df.apply(
    lambda row: f"https://www.skyscanner.pl/transport/loty/{row['IATA_Departure']}/{row['IATA_Destination']}/{format_date(row['Departure Date'])}/"
                "?"
                "adultsv2=1&cabinclass=economy&childrenv2=&inboundaltsenabled=false&outboundaltsenabled=false&preferdirects=false&ref=home&rtn=0",
    axis=1
)

# Create inbound link:
final_df['Inbound_Link'] = final_df.apply(
    lambda row: f"https://www.skyscanner.pl/transport/loty/{row['IATA_Destination']}/{row['IATA_Return']}/{format_date(row['Return Date'])}/"
                "?"
                "adultsv2=1&cabinclass=economy&childrenv2=&inboundaltsenabled=false&outboundaltsenabled=false&preferdirects=false&ref=home&rtn=0",
    axis=1
)

# Create round trip link (only if departure = return airport)
final_df['Round_Trip_Link'] = final_df.apply(
    lambda row: (
        f"https://www.skyscanner.pl/transport/loty/{row['IATA_Departure']}/{row['IATA_Destination']}/"
        f"{format_date(row['Departure Date'])}/{format_date(row['Return Date'])}/"
        "?"
        "adultsv2=1&cabinclass=economy&childrenv2=&ref=home&rtn=1&preferdirects=false&outboundaltsenabled=false&inboundaltsenabled=false"
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
#best_deals = df[df['z_score'] <= -1].copy()

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
















