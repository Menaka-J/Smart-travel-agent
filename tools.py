import requests
from urllib.parse import quote
from ddgs import DDGS


# ============================================================
# INTERNET SEARCH
# ============================================================

def search_internet(query: str, max_results: int = 5) -> list:

    try:
        results = DDGS().text(
            query,
            max_results=max_results
        )

        cleaned = []

        for item in results:
            cleaned.append({
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", "")
            })

        return cleaned

    except Exception as e:

        return [{
            "title": "Search unavailable",
            "url": "",
            "snippet": str(e)
        }]


# ============================================================
# GEOCODING
# ============================================================

def geocode(place: str):

    headers = {
        "User-Agent": "SmartTravelAgent/1.0"
    }

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": place,
        "format": "json",
        "limit": 1
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            return None

        return {
            "lat": float(data[0]["lat"]),
            "lon": float(data[0]["lon"]),
            "display_name": data[0]["display_name"]
        }

    except Exception:

        return None


# ============================================================
# ROBUST GEOCODING
# ============================================================

def geocode_attraction(attraction: str, destination: str):
    """
    Geocode a tourist attraction using multiple increasingly broad queries.
    """

    aliases = {
        "Kundala Lake": [
            "Kundala Lake, Munnar, Idukki, Kerala, India",
            "Kundala Dam, Munnar, Idukki, Kerala, India",
            "Kundala Dam, Kerala, India",
            "Kundala, Munnar, Kerala, India"
        ],

        "Mattupetty Dam": [
            "Mattupetty Dam, Munnar, Idukki, Kerala, India"
        ],

        "Top Station": [
            "Top Station, Munnar, Idukki, Kerala, India"
        ],

        "Eravikulam National Park": [
            "Eravikulam National Park, Rajamalai, Munnar, Kerala, India"
        ],

        "Echo Point": [
            "Echo Point, Munnar, Idukki, Kerala, India"
        ],

        "Attukad Waterfalls": [
            "Attukad Waterfalls, Munnar, Kerala, India"
        ],

        "Tea Museum": [
            "Tea Museum, Munnar, Kerala, India"
        ]
    }

    queries = aliases.get(
        attraction,
        [
            f"{attraction}, {destination}, Kerala, India",
            f"{attraction}, Kerala, India",
            attraction
        ]
    )

    for query in queries:
        result = geocode(query)

        if result:
            return result

    return None

# ============================================================
# SINGLE ROUTE
# ============================================================

def calculate_distance(start_city: str, end_city: str) -> dict:

    start = geocode(start_city)
    end = geocode(end_city)

    if not start:

        return {
            "success": False,
            "start": start_city,
            "end": end_city,
            "message": f"Could not geocode start location: {start_city}"
        }

    if not end:

        return {
            "success": False,
            "start": start_city,
            "end": end_city,
            "message": f"Could not geocode destination: {end_city}"
        }

    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{start['lon']},{start['lat']};"
        f"{end['lon']},{end['lat']}"
    )

    params = {
        "overview": "false"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        if data.get("code") != "Ok":

            return {
                "success": False,
                "start": start_city,
                "end": end_city,
                "message": "OSRM route unavailable."
            }

        route = data["routes"][0]

        return {
            "success": True,
            "start": start_city,
            "end": end_city,
            "distance_km": round(
                route["distance"] / 1000,
                1
            ),
            "duration_minutes": round(
                route["duration"] / 60
            )
        }

    except Exception as e:

        return {
            "success": False,
            "start": start_city,
            "end": end_city,
            "message": str(e)
        }


# ============================================================
# MULTI-STOP ROUTING
# ============================================================

def calculate_trip_route(
    destination: str,
    attractions: list
) -> dict:

    # Start from the main destination
    locations = [destination] + attractions

    legs = []

    total_distance = 0
    total_minutes = 0

    for i in range(len(locations) - 1):

        start = locations[i]
        end = locations[i + 1]

        print(
            f"   Route: {start} → {end}"
        )

        # ----------------------------------------------------
        # GEOCODE START
        # ----------------------------------------------------

        if start == destination:

            start_geo = geocode(
                destination
            )

            # Fallback
            if not start_geo:
                start_geo = geocode(
                    f"{destination}, Kerala, India"
                )

        else:

            start_geo = geocode_attraction(
                start,
                destination
            )

        # ----------------------------------------------------
        # GEOCODE END
        # ----------------------------------------------------

        end_geo = geocode_attraction(
            end,
            destination
        )

        # ----------------------------------------------------
        # CHECK COORDINATES
        # ----------------------------------------------------

        if not start_geo:

            legs.append({
                "success": False,
                "start": start,
                "end": end,
                "message": f"Could not locate {start}"
            })

            continue

        if not end_geo:

            legs.append({
                "success": False,
                "start": start,
                "end": end,
                "message": f"Could not locate {end}"
            })

            continue

        # ----------------------------------------------------
        # OSRM
        # ----------------------------------------------------

        url = (
            "https://router.project-osrm.org/"
            "route/v1/driving/"
            f"{start_geo['lon']},{start_geo['lat']};"
            f"{end_geo['lon']},{end_geo['lat']}"
        )

        try:

            response = requests.get(
                url,
                params={
                    "overview": "false"
                },
                timeout=20
            )

            response.raise_for_status()

            data = response.json()

            if data.get("code") != "Ok":

                legs.append({
                    "success": False,
                    "start": start,
                    "end": end,
                    "message": "OSRM could not calculate route."
                })

                continue

            route = data["routes"][0]

            distance_km = round(
                route["distance"] / 1000,
                1
            )

            duration_minutes = round(
                route["duration"] / 60
            )

            legs.append({
                "success": True,
                "start": start,
                "end": end,
                "distance_km": distance_km,
                "duration_minutes": duration_minutes
            })

            total_distance += distance_km
            total_minutes += duration_minutes

        except Exception as e:

            legs.append({
                "success": False,
                "start": start,
                "end": end,
                "message": str(e)
            })

    successful_legs = sum(
        1
        for leg in legs
        if leg.get("success")
    )

    return {
        "locations": locations,
        "legs": legs,
        "total_distance_km": round(
            total_distance,
            1
        ),
        "total_drive_minutes": round(
            total_minutes
        ),
        "successful_legs": successful_legs
    }
   


# ============================================================
# HOSPITAL SEARCH
# ============================================================

def search_hospitals(destination: str):

    queries = [
        f"hospitals emergency services near {destination}",
        f"general hospital {destination}",
        f"emergency hospital {destination}"
    ]

    hospitals = []

    for query in queries:

        results = search_internet(
            query,
            max_results=3
        )

        for result in results:

            if result["title"]:

                hospitals.append({
                    "name": result["title"],
                    "url": result["url"],
                    "description": result["snippet"]
                })

    # Remove duplicates
    unique = []

    seen = set()

    for hospital in hospitals:

        name = hospital["name"]

        if name not in seen:

            seen.add(name)
            unique.append(hospital)

    return unique[:5]


# ============================================================
# WHATSAPP SOS
# ============================================================

def generate_sos_link(
    emergency_number: str,
    location_name: str
) -> str:

    clean_number = "".join(
        filter(
            str.isdigit,
            emergency_number
        )
    )

    message = (
        f"SOS! I am currently at {location_name}. "
        f"Please check on me."
    )

    return (
        f"https://wa.me/{clean_number}"
        f"?text={quote(message)}"
    )


# ============================================================
# BUDGET
# ============================================================

def calculate_budget(
    max_budget: float,
    days: int,
    distance_km: float
) -> dict:

    vehicle_per_day = 2200
    hotel_per_night = 2500
    food_per_day = 900

    fuel_price = 100
    vehicle_mileage = 15

    vehicle = vehicle_per_day * days

    fuel_litres = distance_km / vehicle_mileage

    fuel = fuel_litres * fuel_price

    accommodation = (
        hotel_per_night *
        max(days - 1, 0)
    )

    food = food_per_day * days

    entry_misc = 500

    total = (
        vehicle
        + fuel
        + accommodation
        + food
        + entry_misc
    )

    remaining = max_budget - total

    return {

        "vehicle": round(vehicle),

        "fuel": round(fuel),

        "accommodation": round(
            accommodation
        ),

        "food": round(food),

        "entry_misc": round(
            entry_misc
        ),

        "total": round(total),

        "budget": round(
            max_budget
        ),

        "remaining": round(
            remaining
        ),

        "within_budget": (
            total <= max_budget
        )
    }