from crewai import Agent, LLM
import os
from dotenv import load_dotenv


load_dotenv()


# ============================================================
# GEMINI
# ============================================================

main_llm = LLM(
    model="gemini/gemini-3.6-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    max_tokens=1800
)


# ============================================================
# AGENT 1
# ============================================================

destination_agent = Agent(

    role="Destination Researcher",

    goal=(
        "Research the destination and select suitable "
        "real tourist attractions based on the user's "
        "preferences and trip duration."
    ),

    backstory=(
        "An expert travel researcher who creates "
        "personalized destination recommendations."
    ),

    llm=main_llm,

    verbose=True,

    cache=False,

    max_iter=2
)


# ============================================================
# AGENT 2
# ============================================================

routing_agent = Agent(

    role="Routing Specialist",

    goal=(
        "Analyze the verified attraction locations and "
        "organize them into a practical travel sequence."
    ),

    backstory=(
        "A logistics specialist who creates efficient "
        "road travel routes between attractions."
    ),

    llm=main_llm,

    verbose=True,

    cache=False,

    max_iter=2
)


# ============================================================
# AGENT 3
# ============================================================

budget_agent = Agent(

    role="Budget Manager",

    goal=(
        "Analyze transportation, accommodation, food "
        "and miscellaneous expenses and ensure the trip "
        "respects the user's maximum budget."
    ),

    backstory=(
        "A travel financial planning specialist."
    ),

    llm=main_llm,

    verbose=True,

    cache=False,

    max_iter=2
)


# ============================================================
# AGENT 4
# ============================================================

safety_agent = Agent(

    role="Safety Coordinator",

    goal=(
        "Provide useful emergency information, nearby "
        "medical facilities and safety recommendations."
    ),

    backstory=(
        "A travel safety specialist responsible for "
        "emergency preparedness."
    ),

    llm=main_llm,

    verbose=True,

    cache=False,

    max_iter=2
)


# ============================================================
# FINAL AGENT
# ============================================================

final_agent = Agent(

    role="Itinerary Planning Agent",

    goal=(
        "Create a clear personalized day-wise itinerary "
        "using the verified attractions, calculated routes, "
        "budget and emergency information."
    ),

    backstory=(
        "An expert autonomous travel planner who combines "
        "multiple specialized agent outputs into one "
        "practical travel plan."
    ),

    llm=main_llm,

    verbose=True,

    cache=False,

    max_iter=2
)