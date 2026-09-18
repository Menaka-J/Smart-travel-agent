import requests
import time
import re
from urllib.parse import quote
from ddgs import DDGS


# ============================================================
# GLOBAL SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "SmartTravelAgent/1.0 Student Project"
})


# ============================================================
# SEARCH
# ============================================================

def search_internet(query: str, max_results: int = 5) -> list:

    try:

        results = DDGS().text(
            query,
            max_results=max_results
        )

        return [
            {
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", "")
            }
            for item in results
        ]

    except Exception as e:

        return [{
            "title": "Search unavailable",
            "url": "",
            "snippet": str(e)
        }]


# ============================================================
# NOMINATIM
# ============================================================

def nominatim_geocode(query: str):

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": query,
        "format": "json",
        "limit": 3,
        "addressdetails": 1
    }

    try:

        response = SESSION.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            return None

        # Return ALL candidates
        candidates = []

        for item in data:

            candidates.append({
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "display_name": item.get(
                    "display_name",
                    query
                ),
                "address": item.get(
                    "address",
                    {}
                )
            })

        time.sleep(1)

        return candidates

    except Exception:

        return None


# ============================================================
# PHOTON
# ============================================================

def photon_geocode(query: str):

    url = "https://photon.komoot.io/api/"

    params = {
        "q": query,
        "limit": 5
    }

    try:

        response = SESSION.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        features = data.get(
            "features",
            []
        )

        if not features:
            return None

        candidates = []

        for feature in features:

            coordinates = feature[
                "geometry"
            ]["coordinates"]

            properties = feature.get(
                "properties",
                {}
            )

            candidates.append({

                "lat": float(
                    coordinates[1]
                ),

                "lon": float(
                    coordinates[0]
                ),

                "display_name": ", ".join(
                    str(x)
                    for x in [
                        properties.get(
                            "name",
                            query
                        ),
                        properties.get(
                            "city",
                            ""
                        ),
                        properties.get(
                            "state",
                            ""
                        ),
                        properties.get(
                            "country",
                            ""
                        )
                    ]
                    if x
                ),

                "address": properties

            })

        return candidates

    except Exception:

        return None


# ============================================================
# DISTANCE BETWEEN TWO COORDINATES
# ============================================================

def haversine_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    from math import (
        radians,
        sin,
        cos,
        sqrt,
        atan2
    )

    R = 6371.0

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        +
        cos(lat1)
        * cos(lat2)
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return R * c


# ============================================================
# SELECT BEST GEOCODING CANDIDATE
# ============================================================

def choose_candidate(
    candidates,
    reference=None,
    max_distance_km=None
):

    if not candidates:
        return None

    # If we don't have a reference location,
    # take the first reasonable candidate.
    if not reference:

        return {
            "lat": candidates[0]["lat"],
            "lon": candidates[0]["lon"],
            "display_name": candidates[0][
                "display_name"
            ],
            "address": candidates[0].get(
                "address",
                {}
            )
        }

    best = None
    best_distance = float("inf")

    for candidate in candidates:

        distance = haversine_distance(

            reference["lat"],
            reference["lon"],

            candidate["lat"],
            candidate["lon"]
        )

        if (
            max_distance_km is not None
            and distance > max_distance_km
        ):
            continue

        if distance < best_distance:

            best_distance = distance
            best = candidate

    if not best:
        return None

    return {
        "lat": best["lat"],
        "lon": best["lon"],
        "display_name": best[
            "display_name"
        ],
        "address": best.get(
            "address",
            {}
        ),
        "distance_from_destination_km":
            round(best_distance, 1)
    }


# ============================================================
# GLOBAL GEOCODE
# ============================================================

_GEOCODE_CACHE = {}


def geocode(place: str):

    if not place:
        return None

    place = place.strip()

    key = place.lower()

    if key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[key]

    # Nominatim
    candidates = nominatim_geocode(
        place
    )

    if candidates:

        result = choose_candidate(
            candidates
        )

        if result:

            _GEOCODE_CACHE[key] = result

            return result

    # Photon fallback
    candidates = photon_geocode(
        place
    )

    if candidates:

        result = choose_candidate(
            candidates
        )

        if result:

            _GEOCODE_CACHE[key] = result

            return result

    return None


# ============================================================
# GLOBAL ATTRACTION GEOCODING
# ============================================================

def geocode_attraction(
    attraction: str,
    destination: str,
    destination_coordinates=None
):

    if not attraction:
        return None

    attraction = attraction.strip()
    destination = destination.strip()

    if destination_coordinates is None:

        destination_coordinates = geocode(
            destination
        )

    # Several global query formats
    queries = [

        f"{attraction}, {destination}",

        f"{attraction} in {destination}",

        f"{destination} {attraction}",

        attraction

    ]

    for query in queries:

        # Nominatim
        candidates = nominatim_geocode(
            query
        )

        if candidates:

            result = choose_candidate(

                candidates,

                reference=destination_coordinates,

                max_distance_km=300
            )

            if result:

                return result

        # Photon fallback
        candidates = photon_geocode(
            query
        )

        if candidates:

            result = choose_candidate(

                candidates,

                reference=destination_coordinates,

                max_distance_km=300
            )

            if result:

                return result

    return None


# ============================================================
# ROUTE BETWEEN COORDINATES
# ============================================================

def calculate_route_from_coordinates(
    start,
    end
):

    url = (
        "https://router.project-osrm.org/"
        "route/v1/driving/"
        f"{start['lon']},{start['lat']};"
        f"{end['lon']},{end['lat']}"
    )

    params = {
        "overview": "false",
        "steps": "false"
    }

    try:

        response = SESSION.get(
            url,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if data.get("code") != "Ok":

            return {
                "success": False,
                "message": (
                    "OSRM could not calculate "
                    "this route."
                )
            }

        routes = data.get(
            "routes",
            []
        )

        if not routes:

            return {
                "success": False,
                "message": "No road route found."
            }

        route = routes[0]

        return {

            "success": True,

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
            "message": str(e)
        }


# ============================================================
# COMPLETE TRIP ROUTE
# ============================================================

def calculate_trip_route(
    destination,
    attractions
):

    destination_coordinates = geocode(
        destination
    )

    if not destination_coordinates:

        return {
            "success": False,
            "locations": [],
            "legs": [],
            "total_distance_km": 0,
            "total_drive_minutes": 0,
            "successful_legs": 0,
            "failed_locations": [
                destination
            ]
        }

    verified = [
        {
            "name": destination,
            "coordinates":
                destination_coordinates
        }
    ]

    failed_locations = []

    # --------------------------------------------------------
    # Geocode every attraction
    # --------------------------------------------------------

    for attraction in attractions:

        attraction = attraction.strip()

        if not attraction:
            continue

        print(
            f"   Geocoding: {attraction}"
        )

        coordinates = geocode_attraction(

            attraction,

            destination,

            destination_coordinates
        )

        if coordinates:

            verified.append({

                "name": attraction,

                "coordinates":
                    coordinates

            })

        else:

            print(
                f"   ✗ Rejected: "
                f"{attraction}"
            )

            failed_locations.append(
                attraction
            )

    # --------------------------------------------------------
    # Routes
    # --------------------------------------------------------

    legs = []

    total_distance = 0
    total_minutes = 0

    for i in range(
        len(verified) - 1
    ):

        start = verified[i]
        end = verified[i + 1]

        print(
            f"   Route: "
            f"{start['name']} → "
            f"{end['name']}"
        )

        route = calculate_route_from_coordinates(

            start["coordinates"],

            end["coordinates"]
        )

        if route["success"]:

            legs.append({

                "success": True,

                "start": start["name"],

                "end": end["name"],

                "distance_km":
                    route["distance_km"],

                "duration_minutes":
                    route[
                        "duration_minutes"
                    ]
            })

            total_distance += route[
                "distance_km"
            ]

            total_minutes += route[
                "duration_minutes"
            ]

        else:

            legs.append({

                "success": False,

                "start": start["name"],

                "end": end["name"],

                "message":
                    route["message"]
            })

    return {

        "success": True,

        "locations": [
            item["name"]
            for item in verified
        ],

        "legs": legs,

        "total_distance_km":
            round(total_distance, 1),

        "total_drive_minutes":
            round(total_minutes),

        "successful_legs":
            sum(
                1
                for x in legs
                if x["success"]
            ),

        "failed_locations":
            failed_locations
    }


# ============================================================
# DESTINATION COUNTRY / CURRENCY
# ============================================================

def get_destination_information(
    destination
):

    coordinates = geocode(
        destination
    )

    if not coordinates:

        return {
            "country": None,
            "currency": None,
            "currency_code": None
        }

    address = coordinates.get(
        "address",
        {}
    )

    country = address.get(
        "country"
    )

    country_code = address.get(
        "country_code"
    )

    if not country_code:

        return {
            "country": country,
            "currency": None,
            "currency_code": None
        }

    country_code = country_code.upper()

    # Country code → currency
    currency_map = {

        "IN": ("Indian Rupee", "INR"),
        "GB": ("British Pound", "GBP"),
        "US": ("US Dollar", "USD"),
        "DE": ("Euro", "EUR"),
        "FR": ("Euro", "EUR"),
        "IT": ("Euro", "EUR"),
        "ES": ("Euro", "EUR"),
        "JP": ("Japanese Yen", "JPY"),
        "AU": ("Australian Dollar", "AUD"),
        "CA": ("Canadian Dollar", "CAD"),
        "SG": ("Singapore Dollar", "SGD"),
        "AE": ("UAE Dirham", "AED"),
        "CH": ("Swiss Franc", "CHF"),
        "TH": ("Thai Baht", "THB"),
        "MY": ("Malaysian Ringgit", "MYR")
    }

    currency = currency_map.get(
        country_code
    )

    if currency:

        return {

            "country": country,

            "currency":
                currency[0],

            "currency_code":
                currency[1]
        }

    # Fallback
    return {

        "country": country,

        "currency": None,

        "currency_code": "USD"
    }


# ============================================================
# BUDGET
# ============================================================

def calculate_budget(
    max_budget,
    days,
    distance_km,
    currency="INR"
):

    currency = (
        currency or "USD"
    ).upper()

    profiles = {

        "INR": {
            "vehicle_day": 2200,
            "hotel_night": 2500,
            "food_day": 900,
            "fuel_litre": 100
        },

        "USD": {
            "vehicle_day": 75,
            "hotel_night": 100,
            "food_day": 45,
            "fuel_litre": 1.0
        },

        "GBP": {
            "vehicle_day": 65,
            "hotel_night": 100,
            "food_day": 45,
            "fuel_litre": 1.5
        },

        "EUR": {
            "vehicle_day": 70,
            "hotel_night": 100,
            "food_day": 45,
            "fuel_litre": 1.7
        },

        "JPY": {
            "vehicle_day": 10000,
            "hotel_night": 12000,
            "food_day": 5000,
            "fuel_litre": 180
        },

        "AUD": {
            "vehicle_day": 100,
            "hotel_night": 150,
            "food_day": 60,
            "fuel_litre": 2
        },

        "CAD": {
            "vehicle_day": 100,
            "hotel_night": 140,
            "food_day": 60,
            "fuel_litre": 1.7
        }
    }

    profile = profiles.get(
        currency,
        profiles["USD"]
    )

    vehicle = (
        profile["vehicle_day"]
        * days
    )

    accommodation = (
        profile["hotel_night"]
        * max(days - 1, 0)
    )

    food = (
        profile["food_day"]
        * days
    )

    fuel = (
        distance_km / 12
    ) * profile["fuel_litre"]

    entry_misc = (
        500
        if currency == "INR"
        else 50
    )

    total = (
        vehicle
        + accommodation
        + food
        + fuel
        + entry_misc
    )

    return {

        "currency": currency,

        "vehicle":
            round(vehicle),

        "fuel":
            round(fuel),

        "accommodation":
            round(accommodation),

        "food":
            round(food),

        "entry_misc":
            round(entry_misc),

        "total":
            round(total),

        "budget":
            round(max_budget),

        "remaining":
            round(
                max_budget - total
            ),

        "within_budget":
            total <= max_budget
    }


# ============================================================
# HOSPITALS
# ============================================================

def search_hospitals(
    destination,
    max_results=5
):

    results = search_internet(

        f"major hospitals near "
        f"{destination}",

        max_results
    )

    return [

        {
            "name": r["title"],
            "url": r["url"],
            "description":
                r["snippet"]
        }

        for r in results
    ]


# ============================================================
# SOS
# ============================================================

def generate_sos_link(
    emergency_number,
    location_name
):

    clean_number = "".join(
        filter(
            str.isdigit,
            emergency_number
        )
    )

    message = (
        f"SOS! I am currently at "
        f"{location_name}. "
        "Please check on me."
    )

    return (
        f"https://wa.me/"
        f"{clean_number}"
        f"?text={quote(message)}"
    )


# ============================================================
# CLEAN ATTRACTION
# ============================================================

def clean_attraction_name(name):

    if not name:
        return ""

    name = str(name)

    name = re.sub(
        r"^[\-\*\•\d\.\)\s]+",
        "",
        name
    )

    name = name.replace(
        "**",
        ""
    )

    return name.strip()