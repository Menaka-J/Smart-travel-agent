import os
import re
import time
import requests

from dotenv import load_dotenv
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


load_dotenv()


# ============================================================
# GEMINI DIRECT REST API
# ============================================================

GEMINI_MODEL = "gemini-3.5-flash"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{GEMINI_MODEL}:generateContent"
)


def direct_gemini_call(
    prompt,
    attempts=2
):
    """
    Call Google Gemini directly through the REST API.

    This bypasses the CrewAI/LiteLLM Gemini execution path,
    which was returning 503 errors.
    """

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    payload = {

        "contents": [

            {

                "parts": [

                    {
                        "text": prompt
                    }

                ]

            }

        ]

    }

    for attempt in range(
        1,
        attempts + 1
    ):

        try:

            print()
            print(
                f"Direct Gemini REST call "
                f"(attempt {attempt}/{attempts})..."
            )

            response = requests.post(

                GEMINI_URL,

                params={
                    "key": api_key
                },

                json=payload,

                timeout=30
            )

            print(
                f"Gemini HTTP status: "
                f"{response.status_code}"
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if response.status_code == 200:

                data = response.json()

                candidates = data.get(
                    "candidates",
                    []
                )

                if not candidates:

                    raise RuntimeError(
                        "Gemini returned no candidates."
                    )

                content = candidates[0].get(
                    "content",
                    {}
                )

                parts = content.get(
                    "parts",
                    []
                )

                text_parts = []

                for part in parts:

                    text = part.get(
                        "text",
                        ""
                    )

                    if text:

                        text_parts.append(
                            text
                        )

                result = "\n".join(
                    text_parts
                ).strip()

                if not result:

                    raise RuntimeError(
                        "Gemini returned an empty response."
                    )

                return result

            # ------------------------------------------------
            # TEMPORARY SERVER ERROR
            # ------------------------------------------------

            if response.status_code in (
                500,
                502,
                503,
                504
            ):

                print(
                    "Gemini temporarily unavailable."
                )

                print(
                    response.text[:500]
                )

                if attempt < attempts:

                    wait_time = 5 * attempt

                    print(
                        f"Waiting "
                        f"{wait_time} seconds..."
                    )

                    time.sleep(
                        wait_time
                    )

                    continue

                raise RuntimeError(
                    "Gemini is temporarily unavailable "
                    "after all attempts."
                )

            # ------------------------------------------------
            # OTHER API ERROR
            # ------------------------------------------------

            raise RuntimeError(

                f"Gemini API error "
                f"{response.status_code}: "
                f"{response.text[:1000]}"

            )

        except requests.Timeout:

            print(
                "Gemini request timed out."
            )

            if attempt < attempts:

                time.sleep(
                    5 * attempt
                )

                continue

            raise RuntimeError(
                "Gemini request timed out."
            )

    raise RuntimeError(
        "Gemini request failed."
    )


# ============================================================
# AI STAGE
# ============================================================

def run_ai_stage(
    prompt,
    stage_name
):
    """
    Run one AI planning stage using the verified
    Gemini REST API.
    """

    print()
    print(
        "=" * 60
    )

    print(
        f"RUNNING: {stage_name}"
    )

    print(
        "=" * 60
    )

    return direct_gemini_call(
        prompt,
        attempts=2
    )


# ============================================================
# BUDGET PARSER
# ============================================================

def parse_budget(value):

    if isinstance(
        value,
        (int, float)
    ):

        return float(value)

    value = str(value)

    cleaned = re.sub(
        r"[^\d.]",
        "",
        value
    )

    if not cleaned:

        return 0.0

    return float(
        cleaned
    )


# ============================================================
# EXTRACT ATTRACTIONS
# ============================================================

def extract_attractions(
    text
):

    attractions = []

    lines = str(
        text
    ).splitlines()

    for line in lines:

        line = clean_attraction_name(
            line
        )

        if not line:

            continue

        # Remove common prefixes
        line = re.sub(
            r"^(attraction|place|location)\s*:\s*",
            "",
            line,
            flags=re.I
        )

        # Remove numbering
        line = re.sub(
            r"^\s*\d+[\.\)\-:]\s*",
            "",
            line
        )

        # Ignore long explanatory sentences
        if len(line) > 100:

            continue

        ignored = [

            "should visit",
            "recommend",
            "here are",
            "based on",
            "preferences",
            "tourist attractions include",
            "the following",
            "i recommend",
            "you should",
            "these attractions",
            "attractions are"

        ]

        if any(
            word in line.lower()
            for word in ignored
        ):

            continue

        # Ignore JSON
        if (
            "{" in line
            or "}" in line
        ):

            continue

        # Ignore markdown headings
        if line.startswith("#"):

            continue

        attractions.append(
            line
        )

    # Remove duplicates
    unique = []

    seen = set()

    for attraction in attractions:

        key = attraction.lower().strip()

        if key not in seen:

            seen.add(
                key
            )

            unique.append(
                attraction.strip()
            )

    return unique[:8]


# ============================================================
# FALLBACK ITINERARY
# ============================================================

def build_fallback_itinerary(
    destination,
    country,
    currency,
    days,
    preferences,
    route_data,
    budget_data,
    hospitals,
    sos_link
):

    locations = route_data.get(
        "locations",
        []
    )

    attractions = locations[1:]

    lines = []

    lines.append(
        "# ✈️ Smart Travel Itinerary"
    )

    lines.append("")

    lines.append(
        "## Trip Overview"
    )

    lines.append(
        f"**Destination:** {destination}"
    )

    lines.append(
        f"**Country:** {country}"
    )

    lines.append(
        f"**Duration:** {days} days"
    )

    lines.append(
        f"**Travel Style:** {preferences}"
    )

    lines.append("")

    # --------------------------------------------------------
    # Attractions by day
    # --------------------------------------------------------

    if attractions:

        total_attractions = len(
            attractions
        )

        for day in range(
            1,
            days + 1
        ):

            lines.append(
                f"## Day {day}"
            )

            start_index = (
                (day - 1)
                * total_attractions
                // days
            )

            end_index = (
                day
                * total_attractions
                // days
            )

            day_places = attractions[
                start_index:end_index
            ]

            if not day_places:

                lines.append(
                    "Explore the destination "
                    "at your own pace."
                )

            else:

                if len(day_places) >= 1:

                    lines.append(
                        f"**Morning:** Visit "
                        f"{day_places[0]}"
                    )

                if len(day_places) >= 2:

                    lines.append(
                        f"**Afternoon:** Visit "
                        f"{day_places[1]}"
                    )

                if len(day_places) >= 3:

                    lines.append(
                        f"**Evening:** Visit "
                        f"{day_places[2]}"
                    )

            lines.append("")

    else:

        for day in range(
            1,
            days + 1
        ):

            lines.append(
                f"## Day {day}"
            )

            lines.append(
                "Explore the destination "
                "at your own pace."
            )

            lines.append("")

    # --------------------------------------------------------
    # Route
    # --------------------------------------------------------

    lines.append(
        "## 🗺️ Verified Route Summary"
    )

    for leg in route_data.get(
        "legs",
        []
    ):

        if leg.get(
            "success"
        ):

            lines.append(
                f"**{leg['start']} → "
                f"{leg['end']}**"
            )

            lines.append(
                f"- Distance: "
                f"{leg['distance_km']} km"
            )

            lines.append(
                f"- Driving Time: "
                f"{leg['duration_minutes']} minutes"
            )

    lines.append("")

    lines.append(
        f"**Total Distance:** "
        f"{route_data.get('total_distance_km', 0)} km"
    )

    lines.append(
        f"**Total Driving Time:** "
        f"{route_data.get('total_drive_minutes', 0)} minutes"
    )

    lines.append("")

    # --------------------------------------------------------
    # Budget
    # --------------------------------------------------------

    lines.append(
        "## 💰 Budget Breakdown"
    )

    lines.append(
        f"- Transport: "
        f"{budget_data['vehicle']} {currency}"
    )

    lines.append(
        f"- Fuel: "
        f"{budget_data['fuel']} {currency}"
    )

    lines.append(
        f"- Accommodation: "
        f"{budget_data['accommodation']} {currency}"
    )

    lines.append(
        f"- Food: "
        f"{budget_data['food']} {currency}"
    )

    lines.append(
        f"- Entry/Misc: "
        f"{budget_data['entry_misc']} {currency}"
    )

    lines.append(
        f"- **Total: "
        f"{budget_data['total']} {currency}**"
    )

    lines.append(
        f"- Maximum Budget: "
        f"{budget_data['budget']} {currency}"
    )

    lines.append(
        f"- Remaining: "
        f"{budget_data['remaining']} {currency}"
    )

    lines.append(
        f"- Within Budget: "
        f"{budget_data['within_budget']}"
    )

    lines.append("")

    # --------------------------------------------------------
    # Emergency
    # --------------------------------------------------------

    lines.append(
        "## 🏥 Emergency & Safety"
    )

    if hospitals:

        for hospital in hospitals:

            lines.append(
                f"- {hospital['name']}: "
                f"{hospital['url']}"
            )

    else:

        lines.append(
            "No emergency facilities were returned "
            "by the live search."
        )

    lines.append("")

    lines.append(
        "## 📱 Emergency SOS"
    )

    lines.append(
        sos_link
    )

    lines.append("")

    lines.append(
        "## ⚠️ Important Notes"
    )

    lines.append(
        "- Budget figures are estimates."
    )

    lines.append(
        "- Route distances and driving times "
        "are based on verified route calculations."
    )

    lines.append(
        "- Attraction locations were verified "
        "before inclusion in the route."
    )

    lines.append(
        "- Ticket and hotel prices should be "
        "confirmed before booking."
    )

    return "\n".join(
        lines
    )


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

    days = int(
        days
    )

    max_budget = parse_budget(
        budget
    )

    print()
    print(
        "=" * 60
    )

    print(
        "SMART TRAVEL AGENT"
    )

    print(
        "=" * 60
    )

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

            seen_urls.add(
                url
            )

            unique_results.append(
                result
            )

    unique_results = unique_results[:12]

    research_text = "\n\n".join(

        f"TITLE: {r.get('title', '')}\n"
        f"URL: {r.get('url', '')}\n"
        f"INFO: {r.get('snippet', '')}"

        for r in unique_results
    )

    # ========================================================
    # 3. DESTINATION RESEARCH AI
    # ========================================================

    print()
    print(
        "[2/5] Running destination research..."
    )

    research_prompt = f"""

You are the Global Destination Research Agent.

Research the following travel destination.

DESTINATION:
{destination}

TRIP DURATION:
{days} days

TRAVELER PREFERENCES:
{preferences}

LIVE WEB RESEARCH:
{research_text}

Your task is to select 5 to 8 REAL tourist attractions.

Rules:

- Use attractions supported by the supplied research.
- Do not invent attractions.
- Prefer attractions relevant to the traveler's preferences.
- Keep attractions geographically associated with the destination.
- Return ONLY a numbered list.
- Do not add explanations.
- Do not return URLs.
- Do not return descriptions.

Example:

1. London Eye
2. Tower of London
3. British Museum
4. Hyde Park

"""

    # --------------------------------------------------------
    # AI research
    # --------------------------------------------------------

    try:

        research_output = run_ai_stage(
            research_prompt,
            "Destination Research"
        )

    except Exception as error:

        print()
        print(
            "AI destination research failed."
        )

        print(
            error
        )

        research_output = ""

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
    # FALLBACK FROM SEARCH RESULTS
    # ========================================================

    if not attractions:

        print()
        print(
            "AI did not return attractions."
        )

        print(
            "Using available live research results..."
        )

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

    print()
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
    # FINAL GEMINI STAGE
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

        if leg.get(
            "success"
        ):

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

    verified_attractions = "\n".join(

        "- " + x

        for x in route_data.get(
            "locations",
            []
        )[1:]
    )

    final_prompt = f"""

You are the Global Itinerary Planning Agent.

Create the final travel itinerary using ONLY the
verified information supplied below.

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
{verified_attractions}

VERIFIED ROAD ROUTES:
{route_text}

TOTAL VERIFIED DISTANCE:
{route_data.get('total_distance_km', 0)} km

TOTAL VERIFIED DRIVING TIME:
{route_data.get('total_drive_minutes', 0)} minutes

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

==================================================
IMPORTANT RULES
==================================================

1. Create a professional day-wise itinerary.

2. Use the verified attractions supplied above.

3. Distribute the attractions across exactly
   {days} days.

4. Use Morning, Afternoon and Evening sections.

5. Do NOT invent route distances.

6. Do NOT invent driving times.

7. Do NOT invent ticket prices.

8. Do NOT invent hotel prices.

9. Do NOT invent hospital phone numbers.

10. Use ONLY the supplied numerical data.

11. The budget is an estimate.

12. If fewer attractions were successfully verified,
    use only those verified attractions.

==================================================
FORMAT
==================================================

# ✈️ Smart Travel Itinerary

## Trip Overview

**Destination:**
**Country:**
**Duration:**
**Travel Style:**

## Day 1

**Morning:**
**Afternoon:**
**Evening:**

Continue until Day {days}.

## 🗺️ Verified Route Summary

For every verified route:

**Start → Destination**

Distance: X km
Driving Time: X minutes

**Total Distance:** X km
**Total Driving Time:** X minutes

## 💰 Budget Breakdown

Show:

- Transport
- Fuel
- Accommodation
- Food
- Entry/Misc
- Total
- Maximum Budget
- Remaining
- Within Budget

## 🏥 Emergency & Safety

List the supplied emergency facilities.

Do not invent information.

## 📱 Emergency SOS

Include the supplied WhatsApp SOS link.

## ⚠️ Important Notes

Mention that:

- The budget is an estimate.
- Route values are verified.
- Attraction locations were verified.
- Ticket and hotel prices should be confirmed before booking.

"""

    # ========================================================
    # FINAL AI GENERATION
    # ========================================================

    try:

        final_output = run_ai_stage(
            final_prompt,
            "Final Itinerary Generation"
        )

    except Exception as error:

        print()
        print(
            "Final Gemini generation failed."
        )

        print(
            error
        )

        print(
            "Creating deterministic fallback itinerary..."
        )

        final_output = build_fallback_itinerary(

            destination=destination,

            country=country,

            currency=currency,

            days=days,

            preferences=preferences,

            route_data=route_data,

            budget_data=budget_data,

            hospitals=hospitals,

            sos_link=sos_link
        )

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