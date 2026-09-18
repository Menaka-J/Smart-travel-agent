import requests
import time
import re
from urllib.parse import quote
from ddgs import DDGS


# ============================================================
# GLOBAL HTTP SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "SmartTravelAgent/1.0 Student Project"
})


# ============================================================
# INTERNET SEARCH
# ============================================================

def search_internet(query: str, max_results: int = 5) -> list:
    """
    Perform live internet search using DuckDuckGo.
    Works with destinations worldwide.
    """

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
            "snippet": f"Internet search error: {str(e)}"
        }]


# ============================================================
# NOMINATIM GEOCODING
# ============================================================

def nominatim_geocode(query: str):
    """
    Global geocoding using OpenStreetMap Nominatim.
    """

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
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

        result = data[0]

        return {
            "lat": float(result["lat"]),
            "lon": float(result["lon"]),
            "display_name": result.get(
                "display_name",
                query
            )
        }

    except Exception:

        return None


# ============================================================
# PHOTON FALLBACK GEOCODING
# ============================================================

def photon_geocode(query: str):
    """
    Photon is used as a second global geocoding source
    when Nominatim cannot find the location.
    """

    url = "https://photon.komoot.io/api/"

    params = {
        "q": query,
        "limit": 1
    }

    try:

        response = SESSION.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        features = data.get("features", [])

        if not features:
            return None

        feature = features[0]

        coordinates = feature["geometry"]["coordinates"]

        properties = feature.get("properties", {})

        name = properties.get(
            "name",
            query
        )

        city = properties.get("city", "")
        country = properties.get("country", "")

        display_parts = [
            str(x)
            for x in [name, city, country]
            if x
        ]

        return {
            "lat": float(coordinates[1]),
            "lon": float(coordinates[0]),
            "display_name": ", ".join(display_parts)
        }

    except Exception:

        return None


# ============================================================
# GLOBAL GEOCODING
# ============================================================

_GEOCODE_CACHE = {}


def geocode(place: str):
    """
    Robust global geocoder.

    Strategy:
        1. Nominatim
        2. Photon

    Results are cached to avoid repeated API calls.
    """

    if not place:
        return None

    place = place.strip()

    cache_key = place.lower()

    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    # First attempt
    result = nominatim_geocode(place)

    if result:

        _GEOCODE_CACHE[cache_key] = result

        # Be polite to Nominatim
        time.sleep(1)

        return result

    # Second attempt
    result = photon_geocode(place)

    if result:

        _GEOCODE_CACHE[cache_key] = result

        return result

    return None


# ============================================================
# GLOBAL ATTRACTION GEOCODING
# ============================================================

def geocode_attraction(
    attraction: str,
    destination: str
):
    """
    Attempts to find a tourist attraction globally.

    The important point is that we DO NOT assume Kerala,
    India, or any particular country.
    """

    if not attraction:
        return None

    attraction = attraction.strip()
    destination = destination.strip()

    queries = [

        # Most specific
        f"{attraction}, {destination}",

        # Destination + attraction
        f"{attraction} in {destination}",

        # Attraction + destination
        f"{destination} {attraction}",

        # Exact attraction
        attraction
    ]

    checked = set()

    for query in queries:

        key = query.lower()

        if key in checked:
            continue

        checked.add(key)

        result = geocode(query)

        if result:

            return result

    return None


# ============================================================
# ROUTE CALCULATION
# ============================================================

def calculate_route_from_coordinates(
    start,
    end
):
    """
    Calculate actual road distance using OSRM.
    """

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
                "message": "OSRM could not calculate this road route."
            }

        routes = data.get("routes", [])

        if not routes:

            return {
                "success": False,
                "message": "No road route was found."
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
# GLOBAL TRIP ROUTING
# ============================================================

def calculate_trip_route(
    destination: str,
    attractions: list
):
    """
    Calculate route through destination + attractions.

    Only successfully geocoded attractions are included.

    This prevents fake:
        0 km
        0 minutes

    values.
    """

    destination = destination.strip()

    destination_coordinates = geocode(destination)

    if not destination_coordinates:

        # Try a broader query
        destination_coordinates = geocode(
            destination + " city center"
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
            ],
            "message": (
                f"Could not geocode destination: "
                f"{destination}"
            )
        }

    verified_locations = [
        {
            "name": destination,
            "coordinates": destination_coordinates
        }
    ]

    failed_locations = []

    # --------------------------------------------------------
    # Geocode attractions
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
            destination
        )

        if coordinates:

            verified_locations.append({
                "name": attraction,
                "coordinates": coordinates
            })

        else:

            failed_locations.append(
                attraction
            )

    # --------------------------------------------------------
    # Calculate route legs
    # --------------------------------------------------------

    legs = []

    total_distance = 0
    total_minutes = 0

    for i in range(
        len(verified_locations) - 1
    ):

        start = verified_locations[i]
        end = verified_locations[i + 1]

        print(
            f"   Route: "
            f"{start['name']} → {end['name']}"
        )

        route = calculate_route_from_coordinates(
            start["coordinates"],
            end["coordinates"]
        )

        if route.get("success"):

            leg = {
                "success": True,
                "start": start["name"],
                "end": end["name"],
                "distance_km": route["distance_km"],
                "duration_minutes": route[
                    "duration_minutes"
                ]
            }

            total_distance += route[
                "distance_km"
            ]

            total_minutes += route[
                "duration_minutes"
            ]

        else:

            leg = {
                "success": False,
                "start": start["name"],
                "end": end["name"],
                "message": route.get(
                    "message",
                    "Route unavailable"
                )
            }

        legs.append(leg)

    return {
        "success": True,
        "locations": [
            item["name"]
            for item in verified_locations
        ],
        "legs": legs,
        "total_distance_km": round(
            total_distance,
            1
        ),
        "total_drive_minutes": round(
            total_minutes
        ),
        "successful_legs": sum(
            1
            for leg in legs
            if leg.get("success")
        ),
        "failed_locations": failed_locations
    }


# ============================================================
# DESTINATION INFORMATION
# ============================================================

def get_destination_information(
    destination: str
):
    """
    Get country/currency information globally.

    Uses REST Countries API.
    """

    query = destination.strip()

    url = (
        "https://restcountries.com/v3.1/"
        f"name/{quote(query)}"
    )

    try:

        response = SESSION.get(
            url,
            timeout=15
        )

        if response.status_code != 200:

            return {
                "country": None,
                "currency": None,
                "currency_code": None
            }

        data = response.json()

        if not data:

            return {
                "country": None,
                "currency": None,
                "currency_code": None
            }

        country = data[0]

        currencies = country.get(
            "currencies",
            {}
        )

        currency_code = None
        currency_name = None

        if currencies:

            currency_code = list(
                currencies.keys()
            )[0]

            currency_name = currencies[
                currency_code
            ].get("name")

        return {
            "country": country.get(
                "name",
                {}
            ).get("common"),

            "currency": currency_name,

            "currency_code": currency_code
        }

    except Exception:

        return {
            "country": None,
            "currency": None,
            "currency_code": None
        }


# ============================================================
# CURRENCY CONVERSION
# ============================================================

def get_exchange_rate(
    from_currency: str,
    to_currency: str = "USD"
):
    """
    Get approximate live exchange rate.
    """

    if not from_currency:

        return None

    if from_currency.upper() == to_currency.upper():

        return 1.0

    url = (
        "https://api.frankfurter.app/latest"
    )

    params = {
        "from": from_currency.upper(),
        "to": to_currency.upper()
    }

    try:

        response = SESSION.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        rate = data.get(
            "rates",
            {}
        ).get(
            to_currency.upper()
        )

        if rate:

            return float(rate)

    except Exception:

        pass

    return None


# ============================================================
# BUDGET ESTIMATION
# ============================================================

def calculate_budget(
    max_budget: float,
    days: int,
    distance_km: float,
    currency: str = "INR"
):
    """
    Destination-independent estimated budget.

    IMPORTANT:
    These are planning estimates, not live hotel,
    restaurant, rental-car or ticket prices.
    """

    currency = (
        currency or "INR"
    ).upper()

    # --------------------------------------------------------
    # Approximate planning assumptions by currency
    # --------------------------------------------------------

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
            "fuel_litre": 2.0
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

    # Approximate fuel consumption
    mileage = 12

    fuel = (
        distance_km / mileage
    ) * profile["fuel_litre"]

    entry_misc = (
        50
        if currency == "USD"
        else 500
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
        "budget": round(max_budget),
        "remaining": round(
            max_budget - total
        ),
        "within_budget": (
            total <= max_budget
        )
    }


# ============================================================
# HOSPITAL / EMERGENCY SEARCH
# ============================================================

def search_hospitals(
    destination: str,
    max_results: int = 5
):
    """
    Search for hospitals near the destination.
    """

    query = (
        f"major hospitals near "
        f"{destination}"
    )

    results = search_internet(
        query,
        max_results
    )

    hospitals = []

    for result in results:

        hospitals.append({
            "name": result["title"],
            "url": result["url"],
            "description": result[
                "snippet"
            ]
        })

    return hospitals


# ============================================================
# WHATSAPP SOS
# ============================================================

def generate_sos_link(
    emergency_number: str,
    location_name: str
):
    """
    Generate WhatsApp SOS link.
    """

    clean_number = "".join(
        filter(
            str.isdigit,
            emergency_number
        )
    )

    message = (
        "SOS! I am currently at "
        f"{location_name}. "
        "Please check on me."
    )

    return (
        f"https://wa.me/"
        f"{clean_number}"
        f"?text={quote(message)}"
    )


# ============================================================
# CLEAN ATTRACTION NAME
# ============================================================

def clean_attraction_name(name: str):
    """
    Clean attraction names returned by an LLM.
    """

    if not name:
        return ""

    name = str(name)

    # Remove bullets
    name = re.sub(
        r"^[\-\*\•\d\.\)\s]+",
        "",
        name
    )

    # Remove markdown
    name = name.replace(
        "**",
        ""
    )

    return name.strip()


# ============================================================
# ROUTE SUMMARY
# ============================================================

def format_route_summary(
    route_data: dict
):
    """
    Convert route data into readable text.
    """

    if not route_data.get("success"):

        return (
            "Route calculation was unavailable."
        )

    lines = []

    for leg in route_data.get(
        "legs",
        []
    ):

        if leg.get("success"):

            lines.append(
                f"{leg['start']} → "
                f"{leg['end']}: "
                f"{leg['distance_km']} km, "
                f"{leg['duration_minutes']} min"
            )

    if not lines:

        return (
            "No verified road routes "
            "were available."
        )

    return "\n".join(lines)