import json
import re

from crewai import Crew, Task, Process

from agents import (
    destination_agent,
    trip_analysis_agent,
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
# HELPERS
# ============================================================

def parse_budget(value):
    """
    Convert inputs such as:
        ₹15,000
        $500
        15000
        EUR 1000

    into a number.
    """

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


def extract_attractions(text):
    """
    Extract attraction names from the destination
    research agent output.
    """

    attractions = []

    lines = str(text).splitlines()

    for line in lines:

        line = clean_attraction_name(
            line
        )

        if not line:
            continue

        # Remove common labels
        line = re.sub(
            r"^(attraction|place|location)\s*:\s*",
            "",
            line,
            flags=re.I
        )

        # Ignore obvious prose
        if len(line) > 100:
            continue

        if any(
            keyword in line.lower()
            for keyword in [
                "should visit",
                "recommend",
                "here are",
                "based on",
                "preferences"
            ]
        ):
            continue

        # Avoid JSON-like lines
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

    return unique[:10]


# ============================================================
# MAIN AGENTIC WORKFLOW
# ============================================================

def run_smart_travel_agent(
    destination,
    budget,
    preferences,
    emergency_contact,
    days=3
):

    # ========================================================
    # INPUT PROCESSING
    # ========================================================

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

    # ========================================================
    # DESTINATION INFORMATION
    # ========================================================

    destination_info = (
        get_destination_information(
            destination
        )
    )

    currency = (
        destination_info.get(
            "currency_code"
        )
        or "USD"
    )

    country = (
        destination_info.get(
            "country"
        )
        or "Unknown"
    )

    print(
        "\n=============================="
    )

    print(
        "SMART TRAVEL AGENT"
    )

    print(
        "=============================="
    )

    print(
        f"Destination: {destination}"
    )

    print(
        f"Country: {country}"
    )

    print(
        f"Currency: {currency}"
    )

    print(
        f"Duration: {days} days"
    )

    # ========================================================
    # LIVE DESTINATION RESEARCH
    # ========================================================

    print(
        "\n[1/5] Researching destination..."
    )

    search_queries = [

        f"{destination} top tourist attractions",

        f"{destination} best places to visit",

        f"{destination} tourist attractions "
        f"{preferences}",

        f"{destination} travel guide"
    ]

    research_results = []

    for query in search_queries:

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

    unique_results = unique_results[:15]

    research_text = "\n\n".join(

        [
            (
                f"TITLE: {r['title']}\n"
                f"URL: {r['url']}\n"
                f"INFO: {r['snippet']}"
            )

            for r in unique_results
        ]

    )

    # ========================================================
    # DESTINATION AGENT
    # ========================================================

    research_task = Task(

        description=f"""
You are researching this travel destination:

DESTINATION:
{destination}

TRIP LENGTH:
{days} days

TRAVEL PREFERENCES:
{preferences}

LIVE WEB RESEARCH:
{research_text}

Identify 5 to 8 REAL tourist attractions
from the supplied research.

Rules:

1. Do not invent attractions.
2. Prefer attractions actually associated
   with the destination.
3. Match the user's preferences.
4. Return ONLY a simple numbered list.
5. Use the attraction's commonly recognized name.
6. Do not include explanations.

Example:

1. London Eye
2. Tower of London
3. British Museum
4. Hyde Park
""",

        expected_output=(
            "A numbered list containing "
            "5 to 8 real attractions."
        ),

        agent=destination_agent
    )

    destination_crew = Crew(

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
        destination_crew.kickoff()
    )

    attraction_text = str(
        research_output
    )

    attractions = extract_attractions(
        attraction_text
    )

    # ========================================================
    # FALLBACK: SEARCH RESULT TITLES
    # ========================================================

    if not attractions:

        attractions = []

        for result in unique_results:

            title = result.get(
                "title",
                ""
            )

            title = clean_attraction_name(
                title
            )

            if title:

                attractions.append(
                    title
                )

        attractions = attractions[:8]

    print(
        "\nDiscovered attractions:"
    )

    for attraction in attractions:

        print(
            f"  - {attraction}"
        )

    # ========================================================
    # VERIFIED ROUTING
    # ========================================================

    print(
        "\n[2/5] Calculating verified road routes..."
    )

    route_data = calculate_trip_route(
        destination,
        attractions
    )

    print(
        "\nVerified locations:"
    )

    for location in route_data.get(
        "locations",
        []
    ):

        print(
            f"  ✓ {location}"
        )

    if route_data.get(
        "failed_locations"
    ):

        print(
            "\nLocations that could not "
            "be geocoded:"
        )

        for location in route_data[
            "failed_locations"
        ]:

            print(
                f"  ✗ {location}"
            )

    # ========================================================
    # BUDGET
    # ========================================================

    print(
        "\n[3/5] Calculating estimated budget..."
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

    # ========================================================
    # HOSPITAL SEARCH
    # ========================================================

    print(
        "\n[4/5] Searching emergency facilities..."
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
    # OPERATIONS ANALYSIS AGENT
    # ========================================================

    operations_task = Task(

        description=f"""
Analyze this verified travel data.

DESTINATION:
{destination}

COUNTRY:
{country}

TRIP:
{days} days

PREFERENCES:
{preferences}

ROUTE DATA:
{json.dumps(route_data, indent=2)}

BUDGET DATA:
{json.dumps(budget_data, indent=2)}

HOSPITAL SEARCH:
{json.dumps(hospitals, indent=2)}

Your job is to explain the operational
travel situation.

Do NOT invent data.

Especially do not invent:
- distances
- driving times
- hotel prices
- hospital phone numbers
- ticket prices

Use only the supplied data.
""",

        expected_output=(
            "A concise operational analysis "
            "covering routes, budget and safety."
        ),

        agent=trip_analysis_agent
    )

    operations_crew = Crew(

        agents=[
            trip_analysis_agent
        ],

        tasks=[
            operations_task
        ],

        process=Process.sequential,

        verbose=True
    )

    operations_output = (
        operations_crew.kickoff()
    )

    # ========================================================
    # FINAL ITINERARY AGENT
    # ========================================================

    print(
        "\n[5/5] Creating final itinerary..."
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

USER PREFERENCES:
{preferences}

MAXIMUM BUDGET:
{max_budget} {currency}

VERIFIED ATTRACTIONS:
{json.dumps(
    route_data.get(
        "locations",
        []
    ),
    indent=2
)}

VERIFIED ROUTES:
{json.dumps(
    route_data,
    indent=2
)}

BUDGET:
{json.dumps(
    budget_data,
    indent=2
)}

HOSPITALS:
{json.dumps(
    hospitals,
    indent=2
)}

OPERATIONS ANALYSIS:
{str(operations_output)}

WHATSAPP SOS:
{sos_link}

Create a professional travel itinerary.

FORMAT:

# ✈️ Smart Travel Itinerary

## Trip Overview

Destination:
Country:
Duration:
Travel Style:

## Day 1
- Morning
- Afternoon
- Evening

## Day 2
...

Continue for all {days} days.

## 🗺️ Verified Route Summary

Show only routes that have verified
distance and duration.

Use:

Start → Destination | X km | X min

Do NOT invent route numbers.

## 💰 Budget Breakdown

Show:

- Transport
- Fuel
- Accommodation
- Food
- Entry / Miscellaneous
- Total
- Maximum Budget
- Remaining / Exceeded

Currency:
{currency}

Clearly state whether the estimate
is within the user's budget.

## 🏥 Emergency & Safety

Show the hospitals returned by
the search.

Do not invent hospital phone numbers.

## 📱 Emergency SOS

Show the WhatsApp SOS link.

## ⚠️ Important Notes

Mention that route and budget values
are estimates/verified tool results
where appropriate.

Do not claim hotel or ticket prices
are live unless supplied by a live
pricing source.

Do not create fake information.
""",

        expected_output=(
            "A complete day-wise travel itinerary "
            "with verified routes, estimated budget "
            "and emergency information."
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
    # RETURN EVERYTHING
    # ========================================================

    return {
        "final_itinerary": str(
            final_output
        ),

        "destination": destination,

        "country": country,

        "currency": currency,

        "days": days,

        "attractions": attractions,

        "route_data": route_data,

        "budget_data": budget_data,

        "hospitals": hospitals,

        "sos_link": sos_link
    }