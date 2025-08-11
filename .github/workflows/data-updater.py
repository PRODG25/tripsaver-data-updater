import requests
import pandas as pd
import os
import json
from datetime import datetime, timedelta
import time


polish_airports = [
    "WAW",  # Warszawa Chopin
    "WMI",  # Warszawa Modlin
    "KRK",  # Krakow
    "GDN",  # Gdansk
    "WRO",  # Wroclaw
    "KTW",  # Katowice
    "POZ",  # Poznan
]

summer_destinations_from_poland = [
    # Grecja
    "HER",  # Heraklion (Crete)
    "RHO",  # Rhodes
    "SKG",  # Thessaloniki
    "CFU",  # Corfu
    "ZTH",  # Zakynthos
    "KGS",  # Kos
    "CHQ",  # Chania

    # Hiszpania
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

    # Włochy
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
    
 # Portugalia
    "FAO",  # Faro (Algarve)
    "LIS",  # Lisbon
    "OPO",  # Porto
    "FNC",  # Madeira

    # Francja
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
    {"IATA": "WAW", "City": "Warszawa", "Country": "Polska"},
    {"IATA": "WMI", "City": "Warszawa", "Country": "Polska"},
    {"IATA": "KRK", "City": "Kraków", "Country": "Polska"},
    {"IATA": "GDN", "City": "Gdańsk", "Country": "Polska"},
    {"IATA": "WRO", "City": "Wrocław", "Country": "Polska"},
    {"IATA": "KTW", "City": "Katowice", "Country": "Polska"},
    {"IATA": "POZ", "City": "Poznań", "Country": "Polska"},
    {"IATA": "RZE", "City": "Rzeszow", "Country": "Polska"},
    {"IATA": "LUZ", "City": "Lublin", "Country": "Polska"},


    # Greece
    {"IATA": "HER", "City": "Heraklion", "Country": "Grecja"},
    {"IATA": "RHO", "City": "Rodos", "Country": "Grecja"},
    {"IATA": "SKG", "City": "Saloniki", "Country": "Grecja"},
    {"IATA": "CFU", "City": "Korfu", "Country": "Grecja"},
    {"IATA": "ZTH", "City": "Zakynthos", "Country": "Grecja"},
    {"IATA": "KGS", "City": "Kos", "Country": "Grecja"},
    {"IATA": "CHQ", "City": "Chania", "Country": "Grecja"},

    # Hiszpania
    {"IATA": "MAD", "City": "Madryt", "Country": "Hiszpania"},
    {"IATA": "BCN", "City": "Barcelona", "Country": "Hiszpania"},
    {"IATA": "AGP", "City": "Malaga", "Country": "Hiszpania"},
    {"IATA": "PMI", "City": "Majorka", "Country": "Hiszpania"},
    {"IATA": "ALC", "City": "Alicante", "Country": "Hiszpania"},
    {"IATA": "TFS", "City": "Teneryfa", "Country": "Hiszpania"},
    {"IATA": "SVQ", "City": "Sewilla", "Country": "Hiszpania"},
    {"IATA": "IBZ", "City": "Ibiza", "Country": "Hiszpania"},
    {"IATA": "VLC", "City": "Valencia", "Country": "Hiszpania"},
    {"IATA": "BIO", "City": "Bilbao", "Country": "Hiszpania"},
    {"IATA": "TFN", "City": "Teneryfa", "Country": "Hiszpania"},
    {"IATA": "SPC", "City": "Palma", "Country": "Hiszpania"},
    {"IATA": "GRX", "City": "Granada", "Country": "Hiszpania"},

    # Włochy
    {"IATA": "FCO", "City": "Rzym", "Country": "Włochy"},
    {"IATA": "CIA", "City": "Rzym", "Country": "Włochy"},
    {"IATA": "MXP", "City": "Mediolan", "Country": "Włochy"},
    {"IATA": "BGY", "City": "Mediolan", "Country": "Włochy"},
    {"IATA": "VCE", "City": "Wenecja", "Country": "Włochy"},
    {"IATA": "NAP", "City": "Neapol", "Country": "Włochy"},
    {"IATA": "BLQ", "City": "Bolonia", "Country": "Włochy"},
    {"IATA": "PSA", "City": "Piza", "Country": "Włochy"},
    {"IATA": "FLR", "City": "Florencja", "Country": "Włochy"},
    {"IATA": "TRN", "City": "Turyn", "Country": "Włochy"},
    {"IATA": "BRI", "City": "Bari", "Country": "Włochy"},
    {"IATA": "PMO", "City": "Palermo", "Country": "Włochy"},
    {"IATA": "CTA", "City": "Katania", "Country": "Włochy"},
    {"IATA": "OLB", "City": "Olbia", "Country": "Włochy"},
    {"IATA": "AHO", "City": "Alghero", "Country": "Włochy"},
    {"IATA": "VRN", "City": "Werona", "Country": "Włochy"},
    {"IATA": "GOA", "City": "Genoa", "Country": "Włochy"},

    # Croatia
    {"IATA": "SPU", "City": "Split", "Country": "Chorwacja"},
    {"IATA": "DBV", "City": "Dubrovnik", "Country": "Chorwacja"},
    {"IATA": "ZAD", "City": "Zadar", "Country": "Chorwacja"},

    # Cyprus
    {"IATA": "LCA", "City": "Larnaka", "Country": "Cypr"},
    {"IATA": "PFO", "City": "Pafos", "Country": "Cypr"},

    # Bulgaria
    {"IATA": "VAR", "City": "Warna", "Country": "Bułagria"},
    {"IATA": "BOJ", "City": "Burgas", "Country": "Bułagria"},
    {"IATA": "SOF", "City": "Sofia", "Country": "Bułagria"},

    # Montenegro
    {"IATA": "TGD", "City": "Podgorica", "Country": "Czarnogóra"},

    # Albania
    {"IATA": "TIA", "City": "Tirana", "Country": "Albania"},

    # Portugalia
    {"IATA": "FAO", "City": "Faro", "Country": "Portugalia"},
    {"IATA": "LIS", "City": "Lizbona", "Country": "Portugalia"},
    {"IATA": "OPO", "City": "Porto", "Country": "Portugalia"},
    {"IATA": "FNC", "City": "Madera", "Country": "Portugalia"},

    # Francja
    {"IATA": "CDG", "City": "Paryż", "Country": "Francja"},
    {"IATA": "ORY", "City": "Paryż", "Country": "Francja"},
    {"IATA": "BVA", "City": "Paryż", "Country": "Francja"},
    {"IATA": "LYS", "City": "Lyon", "Country": "Francja"},
    {"IATA": "NCE", "City": "Nicea", "Country": "Francja"},
    {"IATA": "MRS", "City": "Marsylia", "Country": "Francja"},
    {"IATA": "BIQ", "City": "Biarritz", "Country": "Francja"},

    # Iceland
    {"IATA": "KEF", "City": "Reykjavik", "Country": "Islandia"},

    # Other
    {"IATA": "RMO", "City": "Kiszyniów", "Country": "Mołdawia"},
    {"IATA": "BBU", "City": "Bukareszt", "Country": "Rumunia"},
    {"IATA": "OTP", "City": "Bukareszt", "Country": "Rumunia"},
    {"IATA": "CPH", "City": "Kopenhaga", "Country": "Dania"},
    {"IATA": "ARN", "City": "Sztokholm", "Country": "Szwecja"},
    {"IATA": "GOT", "City": "Gotenburg", "Country": "Szwecja"},
    {"IATA": "ATH", "City": "Ateny", "Country": "Grecja"},
    {"IATA": "BUD", "City": "Budapeszt", "Country": "Węgry"},
    {"IATA": "AUH", "City": "Abu Dhabi", "Country": "Zjednoczone Emiraty Arabskie"},
    {"IATA": "IST", "City": "Stambuł", "Country": "Turcja"},
    {"IATA": "SKP", "City": "Skopje", "Country": "Macedonia Półncona"},
    {"IATA": "KUT", "City": "Kutaisi", "Country": "Gruzja"},
    {"IATA": "MLA", "City": "Valletta", "Country": "Malta"},
    {"IATA": "AMM", "City": "Amman", "Country": "Jordania"},
    {"IATA": "RAK", "City": "Marakesz", "Country": "Maroko"},
    {"IATA": "AGA", "City": "Agadir", "Country": "Maroko"},
    {"IATA": "RBA", "City": "Rabat", "Country": "Maroko"},
    {"IATA": "EIN", "City": "Eindhoven", "Country": "Holandia"},
    {"IATA": "AMS", "City": "Amsterdam", "Country": "Holandia"},
    {"IATA": "OSL", "City": "Oslo", "Country": "Norwegia"},
    {"IATA": "TRF", "City": "Oslo", "Country": "Norwegia"},
    {"IATA": "STN", "City": "Londyn", "Country": "Wielka Brytania"},
    {"IATA": "LTN", "City": "Londyn", "Country": "Wielka Brytania"},
    {"IATA": "LGW", "City": "Londyn", "Country": "Wielka Brytania"},
    {"IATA": "MAN", "City": "Manchester", "Country": "Wielka Brytania"},
    {"IATA": "DUB", "City": "Dublin", "Country": "Irlandia"},
    {"IATA": "AYT", "City": "Antalya", "Country": "Turcja"},
    {"IATA": "ADB", "City": "Izmir", "Country": "Turcja"},
    {"IATA": "GLA", "City": "Glasgow", "Country": "Szkocja"},
    {"IATA": "EDI", "City": "Edynburg", "Country": "Szkocja"},



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























