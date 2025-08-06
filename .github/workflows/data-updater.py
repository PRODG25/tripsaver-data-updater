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
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        for entry in data.get("data", []):
            entry["departure_airport"] = route["departure_id"]
            entry["arrival_airport"] = route["arrival_id"]
            all_results.append(entry)
    else:
        print(f"Failed for {route['departure_id']} to {route['arrival_id']}")
	    
print("data success")
# Convert to DataFrame
df = pd.DataFrame(all_results)
print("data converted to df")

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
df.to_csv(filename, index=False)

print(f"DataFrame with all fight prices created saved")






















