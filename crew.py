import json
import re

from crewai import Crew, Task, Process

from agents import (
    destination_agent,
    routing_agent,
    budget_agent,
    safety_agent,
    final_agent
)

from tools import (
    search_internet,
    calculate_trip_route,
    calculate_budget,
    search_hospitals,
    generate_sos_link
)


# ============================================================
# EXTRACT ATTRACTION NAMES
# ============================================================

def extract_attractions(text):

    attractions = []

    # Try JSON first
    try:

        match = re.search(
            r"\[[\s\S]*\]",
            text
        )

        if match:

            data = json.loads(
                match.group()
            )

            if isinstance(data, list):

                for item in data:

                    if isinstance(item, str):

                        attractions.append(
                            item.strip()
                        )

                    elif isinstance(item, dict):

                        name = item.get(
                            "name"
                        )

                        if name:

                            attractions.append(
                                name.strip()
                            )

    except Exception:
        pass

    # Remove duplicates
    final = []

    for attraction in attractions:

        if attraction not in final:

            final.append(attraction)

    return final[:8]


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

    print("\n")
    print("=" * 60)
    print("SMART TRAVEL AGENT STARTED")
    print("=" * 60)


    # ========================================================
    # 1. DESTINATION RESEARCH
    # ========================================================

    print("\n[1/6] Searching destination...")


    search_results = search_internet(
        f"{destination} tourist attractions "
        f"{preferences}",
        max_results=8
    )


    research_text = "\n".join(

        [
            f"- {r['title']}: {r['snippet']}"
            for r in search_results
        ]

    )


    research_task = Task(

        description=f"""

Destination:
{destination}

Travel preferences:
{preferences}

Trip duration:
{days} days

Use the following live research:

{research_text}

Select 6 to 8 REAL tourist attractions.

IMPORTANT:
Return ONLY a JSON array of attraction names.

Example:

[
    "Eravikulam National Park",
    "Mattupetty Dam",
    "Kundala Lake",
    "Top Station",
    "Echo Point",
    "Tea Museum"
]

Do not include descriptions.
Do not include markdown.
Do not invent places.
""",

        expected_output=(
            "A JSON array containing real attraction names."
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


    destination_result = destination_crew.kickoff()

    attractions = extract_attractions(
        str(destination_result)
    )


    # ========================================================
    # FALLBACK
    # ========================================================

    if len(attractions) < 3:

        print(
            "⚠️ Agent returned insufficient attractions."
        )

        # Search result titles as fallback
        attractions = [
            r["title"]
            for r in search_results
            if r["title"]
        ][:6]


    print(
        f"Selected attractions: {attractions}"
    )


    # ========================================================
    # 2. ROUTING
    # ========================================================

    print("\n[2/6] Calculating OSRM routes...")


    route_data = calculate_trip_route(
        destination,
        attractions
    )


    print(
        f"Total distance: "
        f"{route_data['total_distance_km']} km"
    )

    print(
        f"Total driving time: "
        f"{route_data['total_drive_minutes']} minutes"
    )


    # ========================================================
    # 3. BUDGET
    # ========================================================

    print("\n[3/6] Calculating budget...")


    try:

        max_budget = float(

            re.sub(
                r"[^\d.]",
                "",
                str(budget)
            )

        )

    except:

        max_budget = 15000


    budget_data = calculate_budget(

        max_budget=max_budget,

        days=days,

        distance_km=route_data[
            "total_distance_km"
        ]
    )


    # ========================================================
    # 4. SAFETY
    # ========================================================

    print("\n[4/6] Searching emergency facilities...")


    hospitals = search_hospitals(
        destination
    )


    sos_link = generate_sos_link(
        emergency_contact,
        destination
    )


    # ========================================================
    # 5. ROUTING AGENT
    # ========================================================

    print("\n[5/6] Optimizing itinerary...")


    route_summary = "\n".join(

        [

            f"{leg['start']} → "
            f"{leg['end']}: "
            f"{leg.get('distance_km', 'N/A')} km, "
            f"{leg.get('duration_minutes', 'N/A')} min"

            for leg in route_data["legs"]

            if leg.get("success")
        ]

    )


    # ========================================================
    # 6. FINAL AGENT
    # ========================================================

    print("\n[6/6] Generating final itinerary...")


    final_task = Task(

        description=f"""

Create a professional personalized travel itinerary.

DESTINATION:
{destination}

TRIP DURATION:
{days} days

USER PREFERENCES:
{preferences}

SELECTED REAL ATTRACTIONS:
{attractions}

VERIFIED OSRM ROUTES:
{route_summary}

TOTAL VERIFIED DISTANCE:
{route_data['total_distance_km']} km

TOTAL VERIFIED DRIVING TIME:
{route_data['total_drive_minutes']} minutes

BUDGET:
Vehicle: ₹{budget_data['vehicle']}
Fuel: ₹{budget_data['fuel']}
Accommodation: ₹{budget_data['accommodation']}
Food: ₹{budget_data['food']}
Entry/Misc: ₹{budget_data['entry_misc']}

TOTAL:
₹{budget_data['total']}

MAXIMUM:
₹{budget_data['budget']}

REMAINING:
₹{budget_data['remaining']}

HOSPITALS:
{hospitals}

SOS LINK:
{sos_link}


IMPORTANT RULES:

1. Do NOT invent route distances.
2. Use ONLY the verified route values provided above.
3. Show the total distance and driving time exactly.
4. Do NOT show 0 km if verified route data exists.
5. Do not claim prices are live.
6. Clearly indicate if the budget is exceeded.
7. Create a {days}-day itinerary.
8. Use morning, afternoon and evening.
9. Include emergency information.
10. Include the WhatsApp SOS link.
11. Keep the output clear and student-project friendly.


FORMAT:

# ✈️ Smart Travel Itinerary

## 📍 Trip Overview

- Destination
- Focus
- Duration
- Total Estimated Budget
- Budget Status

## 🗓️ Day 1

### Morning
...

### Afternoon
...

### Evening
...

## 🗓️ Day 2

### Morning
...

### Afternoon
...

### Evening
...

Continue until Day {days}.

## 🚗 Route Summary

- Total Distance
- Total Driving Time

### Verified Route Legs

List every successful route leg.

## 💰 Budget Breakdown

Show a table.

## 🏥 Emergency & Safety

List hospitals and emergency numbers.

## 📱 Emergency SOS

Show the WhatsApp SOS link.

## ⚠️ Important Notes

Mention that prices are estimates.
""",

        expected_output=(
            "A complete personalized travel itinerary "
            "with verified routing, budget and safety."
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


    final_result = final_crew.kickoff()


    print("\n")
    print("=" * 60)
    print("SMART TRAVEL AGENT COMPLETED")
    print("=" * 60)


    return str(final_result)