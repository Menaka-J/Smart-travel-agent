import streamlit as st

from crew import run_smart_travel_agent


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Smart Travel Agent",
    page_icon="✈️",
    layout="wide"
)


# ============================================================
# HEADER
# ============================================================

st.title(
    "✈️ Smart Travel Agent - Enterprise Planner"
)

st.markdown(
    """
### Autonomous AI Travel Planning System

The system combines:

- 🔎 Live Internet Research
- 🤖 Multi-Agent AI Planning
- 🚗 OSRM Road Routing
- 💰 Dynamic Budget Calculation
- 🏥 Emergency Hospital Search
- 📱 WhatsApp SOS Generation
- 🧠 Gemini-Powered Itinerary Generation
"""
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Trip Constraints")

    destination = st.text_input(
        "Destination City/Region",
        "Munnar, Kerala"
    )

    budget = st.text_input(
        "Maximum Budget",
        "₹15,000"
    )

    days = st.number_input(
        "Trip Duration (Days)",
        min_value=1,
        max_value=15,
        value=3
    )

    preferences = st.text_area(
        "Travel Style & Preferences",
        "Nature, peaceful atmosphere, photography spots"
    )

    st.divider()

    st.header("Emergency Protocol")

    emergency_contact = st.text_input(
        "Emergency Contact Number",
        "919876543210"
    )

    st.divider()

    generate = st.button(
        "✈️ Generate Autonomous Itinerary",
        type="primary",
        use_container_width=True
    )


# ============================================================
# EXECUTION
# ============================================================

if generate:

    if not destination.strip():

        st.error(
            "Please enter a destination."
        )

        st.stop()


    if not emergency_contact.strip():

        st.error(
            "Please enter an emergency contact number."
        )

        st.stop()


    with st.spinner(
        "Researching destination, calculating routes, "
        "checking budget and preparing your itinerary..."
    ):

        try:

            final_itinerary = run_smart_travel_agent(

                destination=destination,

                budget=budget,

                preferences=preferences,

                emergency_contact=emergency_contact,

                days=int(days)
            )


            st.success(
                "✅ Travel plan generated successfully!"
            )


            st.divider()


            st.markdown(
                final_itinerary,
                unsafe_allow_html=False
            )


        except Exception as e:

            st.error(
                f"An execution error occurred: {str(e)}"
            )

            st.exception(e)