import re
import time

from crewai import Crew, Task, Process

from agents import (
    destination_agent,
    final_agent,
    main_llm
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
# GEMINI ERROR HANDLING
# ============================================================

def is_temporary_gemini_error(error):
    """
    Detect temporary Gemini availability/server errors.
    """

    error_text = str(error).upper()

    temporary_errors = [
        "503",
        "UNAVAILABLE",
        "SERVICE UNAVAILABLE",
        "INTERNAL SERVER ERROR",
        "500 INTERNAL"
    ]

    return any(
        error_type in error_text
        for error_type in temporary_errors
    )


def direct_gemini_call(prompt, attempts=3):
    """
    Call Gemini directly with controlled retries.

    This is used when CrewAI's Gemini call fails with
    a temporary 503 error.
    """

    for attempt in range(1, attempts + 1):

        try:

            print(
                f"\nGemini direct call "
                f"(attempt {attempt}/{attempts})..."
            )

            response = main_llm.call(prompt)

            return str(response)

        except Exception as error:

            print(
                f"\nGemini error: {error}"
            )

            if not is_temporary_gemini_error(error):
                raise

            if attempt < attempts:

                wait_time = attempt * 10

                print(
                    f"Gemini temporarily unavailable. "
                    f"Waiting {wait_time} seconds..."
                )

                time.sleep(wait_time)

            else:

                print(
                    "Gemini remained unavailable "
                    "after all retry attempts."
                )

                raise


def run_crew_with_fallback(
    crew,
    prompt,
    stage_name
):
    """
    Try normal CrewAI execution first.

    If Gemini returns a temporary 503 error,
    fall back to a controlled direct Gemini call.
    """

    try:

        print(
            f"\nRunning {stage_name} through CrewAI..."
        )

        result = crew.kickoff()

        return str(result)

    except Exception as error:

        print(
            f"\nCrewAI {stage_name} failed:"
        )

        print(error)

        if not is_temporary_gemini_error(error):
            raise

        print(
            f"\nFalling back to direct Gemini "
            f"for {stage_name}..."
        )

        return direct_gemini_call(
            prompt,
            attempts=3
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

        # Remove numbering
        line = re.sub(
            r"^\s*\d+[\.\)\-:]\s*",
            "",
            line
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
        if "{" in line or "}" in line:
            continue

        # Ignore markdown headings
        if line.startswith("#"):
            continue

        attractions.append(line)

    # Remove duplicates
    unique = []

    seen = set()

    for attraction in attractions:

        key = attraction.lower().strip()

        if key not in seen:

            seen.add(key)

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
    """
    Creates a safe deterministic itinerary if Gemini
    is temporarily unavailable during final generation.

    Only verified data is used.
    """

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

    lines.append("## Trip Overview")

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
    # Divide attractions across days
    # --------------------------------------------------------

    if attractions:

        total_attractions = len(attractions)

        for day in range(1, days + 1):

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

        if leg.get("success"):

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
        f"{sos_link}"
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

    return "\n".join(lines)


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

        f"TITLE: {r.get('title', '')}\n"
        f"URL: {r.get('url', '')}\n"
        f"INFO: {r.get('snippet', '')}"

        for r in unique_results
    )

    # ========================================================
    # 3. DESTINATION RESEARCH AGENT
    # ========================================================

    print()
    print(
        "[2/5] Running destination research agent..."
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

    research_task = Task(

        description=research_prompt,

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

    # --------------------------------------------------------
    # Run research agent safely
    # --------------------------------------------------------

    research_output = run_crew_with_fallback(

        research_crew,

        research_prompt,

        "destination research"
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
    # FALLBACK FROM SEARCH RESULTS
    # ========================================================

    if not attractions:

        print(
            "\nAI did not return attractions."
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

## Day 2

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

    final_task = Task(

        description=final_prompt,

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

    # --------------------------------------------------------
    # Run final agent safely
    # --------------------------------------------------------

    try:

        final_output = run_crew_with_fallback(

            final_crew,

            final_prompt,

            "final itinerary generation"
        )

    except Exception as error:

        print()
        print(
            "Final Gemini generation failed."
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