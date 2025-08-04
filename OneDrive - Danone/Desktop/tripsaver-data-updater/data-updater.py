import requests
import pandas as pd
import os

polish_airports = [
    "KTW",  # Katowice
    "POZ",  # Poznan
]

summer_destinations_from_poland = [
    # Greece
    "SKG",  # Thessaloniki
    "CFU",  # Corfu
    "ZTH",  # Zakynthos
    "KGS",  # Kos
    "CHQ",  # Chania
]


#Creating List of Routes
import pandas as pd

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
        "end_date":"2025-10-31"
    }

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

# Print DataFrame
print(df)

df.to_excel("flight_prices_all.xlsx", index=False)



