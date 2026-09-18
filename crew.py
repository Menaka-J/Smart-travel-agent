import re

from crewai import Crew, Task, Process

from agents import (
    destination_agent,
    final_agent
)

from tools import (
    search_internet,
    calculate_trip_route,
    calculate_budget,
    search_hospitals,
    generate_sos_link,
    get_destination_information,
    clean_attraction_name
)


# ============================================================
# BUDGET PARSER
# ============================================================

def parse_budget(value):

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value)

    cleaned = re.sub(
        r"[^\d.]",
        "",
        value
    )

    if not cleaned:
        return 0.0

    return float(cleaned)



# ============================================================
# EXTRACT ATTRACTIONS
# ============================================================

def extract_attractions(text):

    attractions = []

    lines = str(text).splitlines()

    for line in lines:

        line = clean_attraction_name(line)

        if not line:
            continue

        # Remove common prefixes
        line = re.sub(
            r"^(attraction|place|location)\s*:\s*",
            "",
            line,
            flags=re.I
        )

        # Ignore long explanatory sentences
        if len(line) > 100:
            continue

        # Ignore prose
        ignored = [
            "should visit",
            "recommend",
            "here are",
            "based on",
            "preferences",
            "tourist attractions include",
            "the following"
        ]

        if any(
            word in line.lower()
            for word in ignored
        ):
            continue

        # Ignore JSON
        if "{" in line or "}" in line:
            continue

        attractions.append(line)

    # Remove duplicates
    unique = []

    seen = set()

    for attraction in attractions:

        key = attraction.lower()

        if key not in seen:

            seen.add(key)

            unique.append(
                attraction
            )

    return unique[:8]


# ============================================================
# MAIN WORKFLOW
# ============================================================

def run_smart_travel_agent(
    destination,
    budget,
    preferences,
    emergency_contact,
    days=3
):

    destination = destination.strip()

    preferences = (
        preferences.strip()
        if preferences
        else "general sightseeing"
    )

    days = int(days)

    max_budget = parse_budget(
        budget
    )

    print()
    print("=" * 60)
    print("SMART TRAVEL AGENT")
    print("=" * 60)

    print(
        f"Destination : {destination}"
    )

    print(
        f"Duration    : {days} days"
    )

    print(
        f"Budget      : {max_budget}"
    )

    # ========================================================
    # 1. DESTINATION INFORMATION
    # ========================================================

    print()
    print(
        "[1/5] Identifying destination..."
    )

    destination_info = (
        get_destination_information(
            destination
        )
    )

    country = (
        destination_info.get(
            "country"
        )
        or "Unknown"
    )

    currency = (
        destination_info.get(
            "currency_code"
        )
        or "USD"
    )

    print(
        f"Country     : {country}"
    )

    print(
        f"Currency    : {currency}"
    )

    # ========================================================
    # 2. LIVE WEB RESEARCH
    # ========================================================

    print()
    print(
        "[2/5] Researching destination..."
    )

    queries = [

        f"{destination} top tourist attractions",

        f"{destination} best places to visit",

        f"{destination} tourist attractions "
        f"{preferences}"
    ]

    research_results = []

    for query in queries:

        results = search_internet(
            query,
            max_results=5
        )

        research_results.extend(
            results
        )

    # Remove duplicate URLs
    unique_results = []

    seen_urls = set()

    for result in research_results:

        url = result.get(
            "url",
            ""
        )

        if url not in seen_urls:

            seen_urls.add(url)

            unique_results.append(
                result
            )

    unique_results = unique_results[:12]

    research_text = "\n\n".join(

        f"TITLE: {r['title']}\n"
        f"URL: {r['url']}\n"
        f"INFO: {r['snippet']}"

        for r in unique_results
    )

    # ========================================================
    # 3. DESTINATION RESEARCH AGENT
    # ========================================================

    research_task = Task(

        description=f"""
Research the following travel destination.

DESTINATION:
{destination}

TRIP DURATION:
{days} days

TRAVELER PREFERENCES:
{preferences}

LIVE WEB RESEARCH:
{research_text}

Select 5 to 8 real attractions.

Rules:

- Use attractions supported by the supplied
  research.
- Do not invent attractions.
- Prefer attractions relevant to the
  traveler's preferences.
- Keep attractions geographically associated
  with the destination.
- Return ONLY a numbered list.
- Do not add explanations.

Example:

1. London Eye
2. Tower of London
3. British Museum
4. Hyde Park
""",

        expected_output=(
            "A numbered list of 5 to 8 real "
            "tourist attractions."
        ),

        agent=destination_agent
    )

    research_crew = Crew(

        agents=[
            destination_agent
        ],

        tasks=[
            research_task
        ],

        process=Process.sequential,

        verbose=True
    )

    research_output = (
        research_crew.kickoff()
    )

    attractions = extract_attractions(
        research_output
    )

    print()
    print(
        "Discovered attractions:"
    )

    for attraction in attractions:

        print(
            f"  • {attraction}"
        )

    # ========================================================
    # FALLBACK
    # ========================================================

    if not attractions:

        for result in unique_results:

            title = clean_attraction_name(
                result.get(
                    "title",
                    ""
                )
            )

            if title:

                attractions.append(
                    title
                )

        attractions = attractions[:6]

    # ========================================================
    # 4. VERIFIED ROUTING
    # ========================================================

    print()
    print(
        "[3/5] Verifying locations and routes..."
    )

    route_data = calculate_trip_route(

        destination,

        attractions
    )

    print()
    print(
        f"Verified locations: "
        f"{len(route_data.get('locations', []))}"
    )

    print(
        f"Successful route legs: "
        f"{route_data.get('successful_legs', 0)}"
    )

    print(
        f"Total distance: "
        f"{route_data.get('total_distance_km', 0)} km"
    )

    print(
        f"Total driving time: "
        f"{route_data.get('total_drive_minutes', 0)} min"
    )

    # ========================================================
    # 5. BUDGET
    # ========================================================

    print()
    print(
        "[4/5] Calculating budget..."
    )

    budget_data = calculate_budget(

        max_budget=max_budget,

        days=days,

        distance_km=route_data.get(
            "total_distance_km",
            0
        ),

        currency=currency
    )

    print(
        f"Estimated cost: "
        f"{currency} "
        f"{budget_data['total']}"
    )

    # ========================================================
    # HOSPITAL SEARCH
    # ========================================================

    print(
        "Searching emergency facilities..."
    )

    hospitals = search_hospitals(
        destination,
        max_results=5
    )

    # ========================================================
    # SOS
    # ========================================================

    sos_link = generate_sos_link(

        emergency_contact,

        destination
    )

    # ========================================================
    # FINAL GEMINI AGENT
    # ========================================================

    print()
    print(
        "[5/5] Creating final itinerary..."
    )

    verified_routes = []

    for leg in route_data.get(
        "legs",
        []
    ):

        if leg.get("success"):

            verified_routes.append(
                leg
            )

    route_text = "\n".join(

        f"- {r['start']} → "
        f"{r['end']}: "
        f"{r['distance_km']} km, "
        f"{r['duration_minutes']} min"

        for r in verified_routes
    )

    hospital_text = "\n".join(

        f"- {h['name']}: "
        f"{h['url']}"

        for h in hospitals
    )

    final_task = Task(

        description=f"""
Create the final travel itinerary.

DESTINATION:
{destination}

COUNTRY:
{country}

DURATION:
{days} days

TRAVEL STYLE:
{preferences}

MAXIMUM BUDGET:
{max_budget} {currency}

VERIFIED ATTRACTIONS:
{chr(10).join(
    '- ' + x
    for x in route_data.get(
        'locations',
        []
    )[1:]
)}

VERIFIED ROAD ROUTES:
{route_text}

TOTAL VERIFIED DISTANCE:
{route_data.get(
    'total_distance_km',
    0
)} km

TOTAL VERIFIED DRIVING TIME:
{route_data.get(
    'total_drive_minutes',
    0
)} minutes

BUDGET:

Transport:
{budget_data['vehicle']} {currency}

Fuel:
{budget_data['fuel']} {currency}

Accommodation:
{budget_data['accommodation']} {currency}

Food:
{budget_data['food']} {currency}

Entry/Misc:
{budget_data['entry_misc']} {currency}

TOTAL:
{budget_data['total']} {currency}

MAXIMUM:
{budget_data['budget']} {currency}

REMAINING:
{budget_data['remaining']} {currency}

WITHIN BUDGET:
{budget_data['within_budget']}

EMERGENCY FACILITIES:
{hospital_text}

WHATSAPP SOS:
{sos_link}

Create a professional itinerary.

FORMAT:

# ✈️ Smart Travel Itinerary

## Trip Overview

Destination:
Country:
Duration:
Travel Style:

## Day 1

Morning:
Afternoon:
Evening:

## Day 2

Morning:
Afternoon:
Evening:

Continue until Day {days}.

## 🗺️ Verified Route Summary

Show the verified road routes.

Format:

Start → Destination
Distance: X km
Driving Time: X minutes

DO NOT invent route values.

## 💰 Budget Breakdown

Show all supplied budget values.

Clearly state whether the estimate
is within the maximum budget.

## 🏥 Emergency & Safety

List the supplied hospital search results.

Do not invent hospital phone numbers.

## 📱 Emergency SOS

Include the supplied WhatsApp SOS link.

## ⚠️ Important Notes

Mention that the budget is an estimate.

Do not invent ticket prices,
hotel prices or route values.

Use ONLY the supplied verified data
for numerical information.
""",

        expected_output=(
            "A complete professional day-wise "
            "travel itinerary."
        ),

        agent=final_agent
    )

    final_crew = Crew(

        agents=[
            final_agent
        ],

        tasks=[
            final_task
        ],

        process=Process.sequential,

        verbose=True
    )

    final_output = final_crew.kickoff()

    # ========================================================
    # RETURN
    # ========================================================

    return {

        "final_itinerary":
            str(final_output),

        "destination":
            destination,

        "country":
            country,

        "currency":
            currency,

        "days":
            days,

        "attractions":
            attractions,

        "route_data":
            route_data,

        "budget_data":
            budget_data,

        "hospitals":
            hospitals,

        "sos_link":
            sos_link
    }