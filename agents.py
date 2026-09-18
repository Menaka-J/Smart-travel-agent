import os

from dotenv import load_dotenv
from crewai import Agent, LLM


load_dotenv()


# ============================================================
# GEMINI LLM
# ============================================================

main_llm = LLM(
    model="gemini/gemini-3.6-flash",
    api_key=os.getenv(
        "GEMINI_API_KEY"
    ),
    max_tokens=1800
)


# ============================================================
# DESTINATION RESEARCH AGENT
# ============================================================

destination_agent = Agent(

    role="Global Destination Research Agent",

    goal=(
        "Research the requested destination using "
        "the supplied live search results. Identify "
        "real attractions that match the traveler's "
        "preferences and trip duration."
    ),

    backstory=(
        "You are a professional global travel researcher. "
        "You research destinations around the world and "
        "select practical attractions based on traveler "
        "preferences rather than inventing locations."
    ),

    llm=main_llm,

    verbose=True,

    cache=False,

    max_iter=2
)


# ============================================================
# TRIP ANALYSIS AGENT
# ============================================================

trip_analysis_agent = Agent(

    role="Travel Operations Analyst",

    goal=(
        "Analyze verified destination, route, budget "
        "and safety information. Never invent numerical "
        "route distances, travel times, prices or "
        "hospital information."
    ),

    backstory=(
        "You are a travel operations specialist. "
        "You work with verified data produced by "
        "external tools and turn it into practical "
        "travel-planning information."
    ),

    llm=main_llm,

    verbose=True,

    cache=False,

    max_iter=2
)


# ============================================================
# FINAL ITINERARY AGENT
# ============================================================

final_agent = Agent(

    role="Global Itinerary Planning Agent",

    goal=(
        "Create a clear day-wise travel itinerary using "
        "only the supplied verified research, route, "
        "budget and safety information."
    ),

    backstory=(
        "You are an expert international travel planner. "
        "You combine research and verified operational "
        "data into a realistic itinerary."
    ),

    llm=main_llm,

    verbose=True,

    cache=False,

    max_iter=2
)


# ============================================================
# VALIDATION
# ============================================================

def validate_plan(
    budget,
    max_budget,
    routes,
    attractions
):

    problems = []

    if budget > max_budget:

        problems.append(
            f"Budget exceeded by "
            f"{budget - max_budget}"
        )

    if not attractions:

        problems.append(
            "No verified attractions found."
        )

    if not routes:

        problems.append(
            "Route information unavailable."
        )

    return {
        "valid": not problems,
        "problems": problems
    }