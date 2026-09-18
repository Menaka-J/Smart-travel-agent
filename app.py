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
### 🌍 Autonomous Global AI Travel Planning System

The system combines:

- 🔎 Live destination research
- 🤖 AI travel planning
- 📍 Global geocoding
- 🚗 Real road-route calculation
- 💰 Destination-aware budget estimation
- 🏥 Emergency hospital search
- 📱 WhatsApp SOS generation
- 🧠 Gemini-powered itinerary generation
"""
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "🌍 Trip Configuration"
    )

    destination = st.text_input(
        "Destination City / Region",
        "Munnar, Kerala"
    )

    budget = st.text_input(
        "Maximum Budget",
        "₹15,000"
    )

    days = st.number_input(
        "Trip Duration (Days)",
        min_value=1,
        max_value=30,
        value=3,
        step=1
    )

    preferences = st.text_area(
        "Travel Style & Preferences",
        "Nature, peaceful, photography spots"
    )

    st.divider()

    st.header(
        "🚨 Emergency Protocol"
    )

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

    # --------------------------------------------------------
    # INPUT VALIDATION
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # EXECUTION STATUS
    # --------------------------------------------------------

    with st.status(
        "🤖 Autonomous travel agents are working...",
        expanded=True
    ) as status:

        try:

            st.write(
                "🔎 Researching destination..."
            )

            result = run_smart_travel_agent(

                destination=destination,

                budget=budget,

                preferences=preferences,

                emergency_contact=emergency_contact,

                days=int(days)
            )

            st.write(
                "📍 Attractions and routes verified."
            )

            st.write(
                "💰 Budget calculated."
            )

            st.write(
                "🏥 Emergency facilities searched."
            )

            st.write(
                "🤖 Final itinerary generated."
            )

            status.update(

                label="✅ Travel planning completed",

                state="complete"
            )

        except Exception as e:

            status.update(

                label="❌ Travel planning failed",

                state="error"
            )

            st.error(
                f"An execution error occurred: {e}"
            )

            st.exception(
                e
            )

            st.stop()

    # ========================================================
    # SUCCESS
    # ========================================================

    st.success(
        "✅ Travel plan generated successfully!"
    )

    # ========================================================
    # SUMMARY CARDS
    # ========================================================

    route = result[
        "route_data"
    ]

    budget_data = result[
        "budget_data"
    ]

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "📍 Destination",
            result["destination"]
        )

    with col2:

        st.metric(
            "📅 Duration",
            f"{result['days']} days"
        )

    with col3:

        st.metric(
            "🚗 Verified Distance",
            f"{route.get('total_distance_km', 0)} km"
        )

    with col4:

        st.metric(
            "💰 Estimated Cost",
            f"{budget_data.get('currency', '')} "
            f"{budget_data.get('total', 0):,}"
        )

    st.divider()

    # ========================================================
    # ROUTE STATUS
    # ========================================================

    st.subheader(
        "🗺️ Route Verification"
    )

    successful = route.get(
        "successful_legs",
        0
    )

    total_legs = len(
        route.get(
            "legs",
            []
        )
    )

    st.write(
        f"Verified route legs: "
        f"**{successful}/{total_legs}**"
    )

    if route.get(
        "failed_locations"
    ):

        st.warning(

            "Some attractions could not be "
            "verified on the map and were "
            "excluded from route calculations: "
            + ", ".join(
                route[
                    "failed_locations"
                ]
            )

        )

    # ========================================================
    # VERIFIED ROUTES
    # ========================================================

    for leg in route.get(
        "legs",
        []
    ):

        if leg.get(
            "success"
        ):

            st.write(

                f"🚗 **{leg['start']}** → "
                f"**{leg['end']}**  \n"
                f"Distance: "
                f"**{leg['distance_km']} km** | "
                f"Driving time: "
                f"**{leg['duration_minutes']} min**"

            )

    st.divider()

    # ========================================================
    # BUDGET
    # ========================================================

    st.subheader(
        "💰 Budget Summary"
    )

    currency = budget_data.get(
        "currency",
        ""
    )

    budget_cols = st.columns(5)

    with budget_cols[0]:

        st.metric(
            "Transport",
            f"{currency} "
            f"{budget_data['vehicle']:,}"
        )

    with budget_cols[1]:

        st.metric(
            "Fuel",
            f"{currency} "
            f"{budget_data['fuel']:,}"
        )

    with budget_cols[2]:

        st.metric(
            "Accommodation",
            f"{currency} "
            f"{budget_data['accommodation']:,}"
        )

    with budget_cols[3]:

        st.metric(
            "Food",
            f"{currency} "
            f"{budget_data['food']:,}"
        )

    with budget_cols[4]:

        st.metric(
            "Total",
            f"{currency} "
            f"{budget_data['total']:,}"
        )

    if budget_data[
        "within_budget"
    ]:

        st.success(
            "✅ Estimated trip cost is "
            "within the maximum budget."
        )

    else:

        st.error(
            "⚠️ Estimated trip cost exceeds "
            "the maximum budget."
        )

    st.divider()

    # ========================================================
    # FINAL ITINERARY
    # ========================================================

    st.subheader(
        "🧠 AI Generated Travel Itinerary"
    )

    st.markdown(
        result[
            "final_itinerary"
        ]
    )

    # ========================================================
    # SOS
    # ========================================================

    st.divider()

    st.subheader(
        "📱 Emergency SOS"
    )

    st.markdown(
        f"[🚨 Open WhatsApp SOS]"
        f"({result['sos_link']})"
    )

    # ========================================================
    # HOSPITALS
    # ========================================================

    st.subheader(
        "🏥 Emergency Facilities"
    )

    hospitals = result.get(
        "hospitals",
        []
    )

    if hospitals:

        for hospital in hospitals:

            st.markdown(
                f"**{hospital['name']}**"
            )

            if hospital.get(
                "url"
            ):

                st.markdown(
                    f"[View source]"
                    f"({hospital['url']})"
                )

            st.caption(
                hospital.get(
                    "description",
                    ""
                )
            )

    else:

        st.warning(
            "No hospital search results were found."
        )