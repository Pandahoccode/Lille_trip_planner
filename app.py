import os
import time
from datetime import datetime, timedelta, date

import folium
import pandas as pd
import streamlit as st
from folium import FeatureGroup
import pygwalker as pyg
from pygwalker.api.streamlit import StreamlitRenderer
from streamlit_folium import st_folium

from src.translations import TRANSLATIONS
from src.planner import (
    TravelPlanner, estimate_budget,
    DAILY_MEAL_TOTAL, HOTEL_BASE_EUR, HOTEL_STAR_INCREMENT_EUR,
    METRO_DAY_PASS_EUR, PARKING_DAILY_EUR, CAR_FUEL_BASE_EUR,
    TRAIN_BASE_EUR, TRAIN_TGV_MULTIPLIER,
    MEAL_BREAKFAST_EUR, MEAL_LUNCH_EUR, MEAL_DINNER_EUR,
)
from src.services import (
    POIService, WeatherService, TrainService, WikiService, RouteService
)

# ── Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lille Trip Planner",
    page_icon="⚜️",
    layout="wide",
)

# ── Dependency Injection (Services) ────────────────────────────────────
@st.cache_resource
def get_services_v4():
    return {
        "poi": POIService(),
        "weather": WeatherService(),
        "train": TrainService(),
        "wiki": WikiService(),
        "route": RouteService(),
    }

SERVICES = get_services_v4()

# ── Constants ──────────────────────────────────────────────────────────
LILLE_COORDS = [50.6292, 3.0573]
AMBER = "#FFBF00"
NAVY = "#0a192f"
COLD_THRESHOLD_C = 12.0
RAIN_KEYWORDS = ["rain", "drizzle", "shower", "thunderstorm", "snow"]
BUDGET_CAP_EUR = 1500  # Default cap

# Custom CSS
from src.css_custom import CUSTOM_CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Data Loading Wrappers ──────────────────────────────────────────────
@st.cache_data
def load_dest_data(city):
    return SERVICES["poi"].load_destination(city)

@st.cache_data
def get_wiki_summary(city):
    return SERVICES["wiki"].get_summary(city)

@st.cache_data
def get_route_calc(from_city, to_city, profile):
    try:
        svc = SERVICES["route"]
        cf, lf = svc.geocode_city(from_city)
        ct, lt = svc.geocode_city(to_city)
        if not cf or not ct:
            return {"error": "Geocoding failed"}

        data = svc.calculate_route(cf, ct, profile)
        d, t = svc.extract_metrics(data)
        est = svc.estimate_cost(d, profile)

        return {
            "geojson": data,
            "dist": svc.format_km(d),
            "dur": svc.format_duration(t),
            "est": est,
            "lf": lf, "lt": lt,
            "from": cf, "to": ct
        }
    except Exception as e:
        return {"error": str(e)}

@st.cache_data
def fetch_sncf_trips_v2(cities, start, end):
    return SERVICES["train"].search_trips(cities, start, end)

# Load Data
hotels, restaurants, sites = load_dest_data("Lille")
weather_service = SERVICES["weather"]
wiki_curr = get_wiki_summary("Lille, France")

# ── Session State & Sidebar ────────────────────────────────────────────
if "lang" not in st.session_state:
    st.session_state["lang"] = "en"

# Initialize global trip vars with defaults to prevent NameErrors
nb_days = 3
nb_people = 2
start_date = date.today()
start_city = "Paris"
arrival_mode = "train"
hotel_stars = 3

with st.sidebar:
    st.title("⚜️ Lille Trip Planner")

    # Language
    lang_choice = st.radio("Language / Langue", ["English", "Français"], horizontal=True)
    st.session_state["lang"] = "fr" if lang_choice == "Français" else "en"
    T = TRANSLATIONS[st.session_state["lang"]]

    st.markdown("---")
    st.markdown(f"**{T['trip_settings']}**")

    start_city = st.text_input(T["start_city"], value=start_city)
    start_date = st.date_input(T["start_date"], value=start_date)
    nb_days = st.number_input(T["duration_days"], min_value=1, max_value=7, value=nb_days)
    nb_people = st.number_input(T["travelers"], min_value=1, max_value=10, value=nb_people)

    st.markdown("---")
    st.markdown(f"**{T['preferences']}**")
    arrival_mode = st.radio(T["transport_mode"], ["train", "car"], format_func=lambda x: x.capitalize())
    hotel_stars = st.slider(f"{T['hotel_stars']}", 1, 5, hotel_stars)

    # Budget Calculation
    train_budget_price = None
    if arrival_mode == "train":
         try:
             cached = SERVICES["train"].load_cache()
             if cached is not None and not cached.empty and "price" in cached.columns:
                 v = cached[cached["price"] > 0]["price"]
                 if not v.empty:
                     train_budget_price = v.mean()
         except: pass

    budget = estimate_budget(nb_days, nb_people, hotel_stars, arrival_mode, train_price_override=train_budget_price)
    remaining = BUDGET_CAP_EUR - budget["grand_total"]

    st.markdown("---")
    st.markdown(f"**{T['budget_grand_total']}:** `{budget['grand_total']:.0f} EUR`")
    st.markdown(f"**{T['budget_remaining']}:** `{remaining:.0f} EUR`")
    st.progress(min(budget["grand_total"] / BUDGET_CAP_EUR, 1.0))

    st.markdown("---")
    st.markdown("### 🏨 Lille Essentials")

    # Module 3: Discovery Cards
    # We display fixed recommendations as requested, or dynamic if available
    sel_hotel = hotels[0] if hotels else {"name": "L'Hermitage Gantois", "stars": 5}
    sel_resto = next((r for r in restaurants if "broc" in r.get("name", "").lower()), restaurants[0] if restaurants else {"name": "Le Broc", "cuisine": "French"})

    # 1. Hotel Card
    with st.expander("🏨 Selected Stay", expanded=True):
        st.markdown(f"**{sel_hotel.get('name')}**")
        st.caption(f"⭐ {sel_hotel.get('stars', 'N/A')} Stars | Tier: €50–€100")
        st.success("✅ Status: Booked")

    # 2. Sites & Museums Card
    with st.expander("🏛️ Sites & Museums", expanded=True):
        st.markdown("**Palais des Beaux-Arts**")
        st.caption("Category: Museum | Hours: 10h-18h")
        st.info("🎟️ Tickets Available")

    # 3. Restaurant Card
    with st.expander("🍴 Local Dining", expanded=True):
        st.markdown(f"**{sel_resto.get('name')}**")
        st.caption("Fixed Price: €14 Lunch/Dinner")
        st.warning("📅 Reservation Recommended")


# ── Main Layout ────────────────────────────────────────────────────────
st.title(f"⚜️ {T['app_title']}")
tab_home, tab_move, tab_planner, tab_data = st.tabs([T['tab_home'], T['tab_move'], T['tab_plan'], "📊 Data"])

# ══════════════════════════════════════════════════════════════════════
# TAB 1: HOME
# ══════════════════════════════════════════════════════════════════════
with tab_home:
    # ── Module 1: The "Hero" (Reformatted Intelligence) ────────────────
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Lille_Collage.jpg/960px-Lille_Collage.jpg",
             caption="Ville de Lille", use_column_width=True)

    st.markdown("""
    <div style="text-align: justify; font-size: 1.1em; margin-bottom: 20px;">
    <strong>Lille, known as the 'Capital of Flanders,'</strong> is a vibrant cultural powerhouse in northern France near the Belgian border.
    As the fourth-largest metropolitan area in France after Paris, Lyon, and Marseille, Lille serves as the prefecture of the Nord department
    and the capital of the Hauts-de-France region. Positioned along the Deûle River, it represents the heart of the European Metropolis of Lille,
    a bustling cross-border hub. With its unique blend of French elegance and Flemish charm, the city offers a rich tapestry of history,
    from its small municipal territory of 35 km² to its vast suburban expansion housing over 1.5 million residents. This 'Crossroads of Europe'
    is defined by its architectural grandeur, world-class museums, and a population that embodies the warmth and industrious spirit of the north.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Module 2: The "Environmental Strip" ────────────────────────────
    st.markdown(f"#### {T['weather_title']}")

    # Fetch 3 days past, 2 days future (Total 5 days typically around current date)
    # The prompt implies strictly 3 past, 2 future relative to 'NOW' or 'Start Date'.
    # We use start_date from sidebar.
    forecast_df = weather_service.get_forecast(start_date, days_past=3, days_future=2)

    cols = st.columns(5)
    # Try to populate 5 columns
    if not forecast_df.empty:
        records = forecast_df.to_dict('records')
        # Ensure we don't exceed columns
        for i, col in enumerate(cols):
            with col:
                if i < len(records):
                    row = records[i]
                    # Date parsing
                    d_obj = row.get("_parsed_date")
                    if not pd.isnull(d_obj):
                         d_lbl = d_obj.strftime("%d/%m")
                    else:
                         d_lbl = str(row.get("date"))[:5]

                    # Data
                    t_max = row.get("temperature_max", "N/A")
                    w_desc = str(row.get("weather_description", "—")).title()

                    # Icon placeholder
                    icon = "🌤️"
                    if "rain" in w_desc.lower(): icon = "🌧️"
                    elif "cloud" in w_desc.lower(): icon = "☁️"
                    elif "sun" in w_desc.lower(): icon = "☀️"
                    elif "snow" in w_desc.lower(): icon = "❄️"

                    st.metric(label=d_lbl, value=f"{t_max}°C", delta=icon)
                    st.caption(w_desc)
                else:
                    st.write("—")
    else:
        st.warning("Weather data unavailable. Please fetch data.")

    # The Map Anchor: Wide Macro-View
    st.markdown("#### 🗺️ Lille Macro-View")
    m = folium.Map(location=LILLE_COORDS, zoom_start=14, tiles="CartoDB positron")
    folium.Marker(LILLE_COORDS, popup="Centre Ville", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)
    st_folium(m, width="100%", height=400, returned_objects=[])


# ══════════════════════════════════════════════════════════════════════
# TAB 2: MOVE
# ══════════════════════════════════════════════════════════════════════
with tab_move:
    # ── Module 4: The "Move" Tab (SNCF Integration) ────────────────────
    st.markdown(f"### {T['tab_move']}")

    st.info("💡 **Pro Tip**: Compare fetching trips below with the real-time prices on SNCF Connect.")

    # UI Controls
    c1, c2 = st.columns([3, 1])
    with c1:
        fetch_cities = st.text_input(T["start_city"], value="Paris, London, Brussels", key="sncf_input")
    with c2:
        st.write("") # Spacer
        st.write("")
        do_fetch = st.button("🔄 Fetch SNCF Prices")

    if do_fetch:
        c_list = [c.strip() for c in fetch_cities.split(",") if c.strip()]
        dt_start = datetime.combine(start_date, datetime.min.time())
        dt_end = datetime.combine(start_date + timedelta(days=nb_days), datetime.min.time())

        with st.spinner("Talking to Navitia/SNCF..."):
            res = fetch_sncf_trips_v2(c_list, dt_start, dt_end)

        if isinstance(res, list) and res:
            st.success(f"✅ Found {len(res)} connections.")
            df_trip = pd.DataFrame(res)

            # Format Data for the Clean Table
            # Req: Departure Station | Arrival Station | Live Price | SNCF Link

            # Prepare columns
            if "departure_station" not in df_trip.columns: df_trip["departure_station"] = df_trip["from"]
            if "arrival_station" not in df_trip.columns: df_trip["arrival_station"] = "Lille Flandres/Europe"

            # Price logic
            df_trip["price"] = df_trip["price"].apply(lambda x: f"€{x:.2f}" if isinstance(x, (int, float)) and x > 0 else "N/A")

            # Link logic
            df_trip["SNCF Link"] = "https://www.sncf-connect.com/"

            # Filter and Rename
            display_cols = ["departure_station", "arrival_station", "departure", "price", "SNCF Link"]
            df_display = df_trip[display_cols].copy()

            df_display.columns = ["Departure St.", "Arrival St.", "Time", "Live Price", "Booking Link"]

            st.data_editor(
                df_display,
                column_config={
                    "Booking Link": st.column_config.LinkColumn(
                        "Book on SNCF", display_text="Go to SNCF"
                    )
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.error("No trips found or API Error.")
    else:
        st.write("Click fetch to see real-time routes.")

    st.markdown("---")
    # Car vs Train Calculation (Keep existing logic just for reference if needed, or minimal)
    # The prompt mainly asked for the API One. We'll leave the Comparison cards below essentially untouched
    # but re-verified they work.

    # Comparison
    cached_trains = SERVICES["train"].load_cache()
    train_avg_price = TRAIN_BASE_EUR * TRAIN_TGV_MULTIPLIER # fallback
    if cached_trains is not None and not cached_trains.empty:
        if "price" in cached_trains.columns:
             valid_prices = cached_trains[cached_trains["price"] > 0]["price"]
             if not valid_prices.empty:
                 train_avg_price = valid_prices.mean()

    train_total = train_avg_price * nb_people
    car_total = (PARKING_DAILY_EUR * nb_days) + CAR_FUEL_BASE_EUR

    c1, c2, c3 = st.columns([5,1,5])
    with c1:
        st.markdown(f"""<div class="compare-card">
            <h3>{T['train_card']}</h3>
            <div class="price">{train_total:.0f} EUR</div>
            <div class="detail">Approx. avg based on cache</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="compare-card">
            <h3>{T['car_card']}</h3>
            <div class="price">{car_total:.0f} EUR</div>
            <div class="detail">{T['fuel_cost']} + {T['parking']}</div>
        </div>""", unsafe_allow_html=True)

    # Car Route Map
    if arrival_mode == "car" and start_city.strip():
        st.markdown("---")
        st.markdown(f"#### {T['route_map']}")
        with st.spinner(T["searching"]):
            r_data = get_route_calc(start_city, "Lille", "driving-car")

        if "error" not in r_data:
            est = r_data["est"]
            k1, k2, k3 = st.columns(3)
            k1.metric(f"{T['fuel_cost']} + {T['toll_cost']}", f"{est['total_cost_eur']:.0f} EUR")
            k2.metric(T['distance'], r_data['dist'])
            k3.metric(T['duration'], r_data['dur'])

            rm = folium.Map(location=[(r_data["from"][1]+r_data["to"][1])/2,
                                      (r_data["from"][0]+r_data["to"][0])/2],
                            zoom_start=6, tiles="CartoDB positron")

            geo = r_data["geojson"]
            if geo.get("features"):
                coords = geo["features"][0]["geometry"]["coordinates"]
                folium.PolyLine([[c[1], c[0]] for c in coords], color=AMBER, weight=5).add_to(rm)

            folium.Marker([r_data["from"][1], r_data["from"][0]], icon=folium.Icon(color="green", icon="play")).add_to(rm)
            folium.Marker([r_data["to"][1], r_data["to"][0]], icon=folium.Icon(color="red", icon="flag")).add_to(rm)

            st_folium(rm, width="100%", height=400, returned_objects=[])
        else:
            st.error(r_data["error"])


# ══════════════════════════════════════════════════════════════════════
# TAB 3: PLANNER
# ══════════════════════════════════════════════════════════════════════
with tab_planner:
    # ── Module 5: The "Planner" Tab (The Logic Engine) ─────────────────

    # 1. The Global Budget Box
    st.markdown("### 💰 Trip Budget Control")

    daily_meal_cost = 9 + 14 + 14 # 37
    total_meals = daily_meal_cost * nb_days * nb_people
    # Hotel var is hotel_stars dependent in approximation or just placeholder
    # usage of existing budget calc

    # We use the 'budget' dict calculated in sidebar

    bg_cols = st.columns(3)
    bg_cols[0].metric("Meal Budget", f"€{daily_meal_cost}/day", "€9+€14+€14")
    # Using the calculated totals from the sidebar logic
    bg_cols[1].metric("Hotel Budget", f"€{budget['hotel_total']}", f"Tier: {hotel_stars}⭐")
    bg_cols[2].metric("Total Trip Cost", f"€{budget['grand_total']:.0f}", f"Rem: €{remaining:.0f}")

    st.markdown("---")

    # Generate Plan
    planner = TravelPlanner()
    plan, recap = planner.plan_trip(start_date, nb_days, hotels, restaurants, sites)

    # 2. The Session Grid
    st.markdown("### 🗓️ Session-First Itinerary")

    for day in plan:
        day_num = day["day"]
        d_date = day["date"]

        # Header: Morning Session
        st.markdown(f"#### 📅 Day {day_num} ({d_date})") # Add weather icon if mapped

        # Grid: Activities (Left) | Dining (Right) -> Prompt says Col 1 Activities, Col 2 Dining

        c_act, c_din = st.columns([1, 1])

        with c_act:
            st.markdown(f"**Morning Session (09:00 - 12:00)**")
            for a in day["morning_activities"]:
                st.write(f"🏛️ {a['name']}")

            st.markdown(f"**Afternoon Session (14:00 - 18:00)**")
            for a in day["afternoon_activities"]:
                st.write(f"📍 {a['name']}")

        with c_din:
            st.markdown(f"**Dining Plan**")
            if day["breakfast"]:
                st.write(f"☕ 08:00 - {day['breakfast']['name']} (€9)")
            if day["lunch"]:
                st.write(f"🍽️ 12:30 - {day['lunch']['name']} (€14)")
            if day["dinner"]:
                st.write(f"🍷 20:00 - {day['dinner']['name']} (€14)")

        st.divider()

    # 3. The Master Map
    st.markdown(f"### {T['master_map']}")
    mm = folium.Map(location=LILLE_COORDS, zoom_start=13, tiles="CartoDB positron")

    # Add Markers with Numbered Labels (Approximated with Tooltips/Popups)

    # We iterate the plan to add markers
    for day in plan:
        d_num = day["day"]
        color = ["blue", "green", "red", "purple", "orange"][d_num % 5]

        # Morning items -> Label "Day X - AM"
        for i, item in enumerate(day["morning_activities"]):
            folium.Marker(
                [item["latitude"], item["longitude"]],
                popup=f"Day {d_num} AM: {item['name']}",
                tooltip=f"{d_num}A",
                icon=folium.Icon(color=color, icon="landmark", prefix="fa")
            ).add_to(mm)

        # Afternoon items -> Label "Day X - PM"
        for i, item in enumerate(day["afternoon_activities"]):
            folium.Marker(
                [item["latitude"], item["longitude"]],
                popup=f"Day {d_num} PM: {item['name']}",
                tooltip=f"{d_num}B",
                icon=folium.Icon(color=color, icon="camera", prefix="fa")
            ).add_to(mm)

    st_folium(mm, width="100%", height=500, returned_objects=[])


# ══════════════════════════════════════════════════════════════════════
# TAB 4: DATA
# ══════════════════════════════════════════════════════════════════════
with tab_data:
    st.markdown("### 📊 Data Visualization")
    st.markdown("Explore the underlying datasets using PyGWalker. Drag and drop columns to create charts.")

    dataset_name = st.selectbox("Select Dataset", ["Weather", "Train Trips", "Hotels", "Restaurants", "Historical Sites"])

    df_viz = None

    if dataset_name == "Weather":
        df_viz = SERVICES["weather"].weather_df
        if df_viz is not None and not df_viz.empty:
             # Cleanup for viz
             if "_parsed_date" in df_viz.columns:
                 df_viz = df_viz.drop(columns=["_parsed_date"])

    elif dataset_name == "Train Trips":
        df_viz = SERVICES["train"].load_cache()

    elif dataset_name == "Hotels":
        df_viz = pd.DataFrame(hotels)

    elif dataset_name == "Restaurants":
        df_viz = pd.DataFrame(restaurants)

    elif dataset_name == "Historical Sites":
        df_viz = pd.DataFrame(sites)

    if df_viz is not None and not df_viz.empty:
        st.write(f"Loaded **{len(df_viz)}** rows.")
        # PyGWalker Renderer
        renderer = StreamlitRenderer(df_viz, spec="./gw_config.json", spec_io_mode="RW")
        renderer.explorer()
    else:
        st.write("No data available or empty dataset.")
