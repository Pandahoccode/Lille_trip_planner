import os
import time
from datetime import datetime, timedelta, date

import folium
import pandas as pd
import streamlit as st
from folium import FeatureGroup
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
    page_title="Lille Command Center",
    page_icon="⚜️",
    layout="wide",
)

# ── Dependency Injection (Services) ────────────────────────────────────
@st.cache_resource
def get_services():
    return {
        "poi": POIService(),
        "weather": WeatherService(),
        "train": TrainService(),
        "wiki": WikiService(),
        "route": RouteService(),
    }

SERVICES = get_services()

# ── Constants ──────────────────────────────────────────────────────────
LILLE_COORDS = [50.6292, 3.0573]
AMBER = "#FFBF00"
NAVY = "#0a192f"
COLD_THRESHOLD_C = 12.0
RAIN_KEYWORDS = ["rain", "drizzle", "shower", "thunderstorm", "snow"]
BUDGET_CAP_EUR = 1500  # Default cap

# Custom CSS
st.markdown("""
<style>
    /* Global Theme */
    .stApp { background-color: #0a192f; color: #e6f1ff; }
    h1, h2, h3, h4, h5, h6 { color: #ccd6f6 !important; font-family: 'Segoe UI', sans-serif; }
    p, div, label, span { color: #8892b0; }

    /* Metrics & Cards */
    .metric-card {
        background: #112240; border: 1px solid #233554;
        border-radius: 8px; padding: 15px; text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 10px;
    }
    .metric-card h3 { margin: 0; font-size: 0.9em; color: #64ffda; text-transform: uppercase; letter-spacing: 1px; }
    .metric-card .value { font-size: 1.5em; font-weight: bold; color: #e6f1ff; margin-top: 5px; }

    /* Weather Horizontal Bar */
    .weather-row { display: flex; gap: 10px; justify-content: space-between; margin-bottom: 20px; overflow-x: auto; }
    .weather-card {
        background: #112240; border: 1px solid #233554; border-radius: 8px;
        padding: 10px; min-width: 100px; text-align: center; flex: 1;
    }
    .weather-card .wdate { font-size: 0.8em; color: #64ffda; margin-bottom: 4px; }
    .weather-card .temp { font-size: 1.1em; font-weight: bold; color: #e6f1ff; }
    .weather-card .desc { font-size: 0.8em; color: #8892b0; text-transform: capitalize; }
    .indoor-alert {
        background: rgba(255, 99, 71, 0.2); border: 1px solid tomato; color: tomato;
        padding: 8px; border-radius: 5px; margin-bottom: 10px; text-align: center;
    }

    /* Move / Route Tables */
    .route-card {
        background: #112240; border-left: 4px solid #64ffda; padding: 15px;
        margin-bottom: 15px; border-radius: 0 8px 8px 0;
    }
    .route-card h4 { margin: 0; color: #e6f1ff; }
    .route-price { font-size: 1.2rem; color: #FFBF00; font-weight: bold; margin: 5px 0; }
    .route-detail { font-size: 0.9rem; margin: 2px 0; }

    /* Comparison Badge */
    .vs-badge {
        background: #FFBF00; color: #0a192f; font-weight: bold;
        border-radius: 50%; width: 40px; height: 40px;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 0 10px rgba(255,191,0,0.5);
    }
    .compare-card {
        background: rgba(17,34,64,0.5); border: 1px solid #233554;
        border-radius: 12px; padding: 20px; text-align: center;
    }
    .compare-card .price { font-size: 2em; color: #64ffda; font-weight: bold; }

    /* Planner */
    .day-card {
        background: #112240; border-top: 3px solid #64ffda;
        padding: 15px; margin-bottom: 20px; border-radius: 0 0 8px 8px;
    }
    .map-container { border: 2px solid #233554; border-radius: 8px; overflow: hidden; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ── Session State & Sidebar ────────────────────────────────────────────
if "lang" not in st.session_state:
    st.session_state["lang"] = "en"

with st.sidebar:
    st.title("⚜️ Lille Trip Planner")

    # Language
    lang_choice = st.radio("Language / Langue", ["English", "Français"], horizontal=True)
    st.session_state["lang"] = "fr" if lang_choice == "Français" else "en"
    T = TRANSLATIONS[st.session_state["lang"]]

    st.markdown("---")
    st.markdown(f"**{T['trip_settings']}**")

    start_city = st.text_input(T["start_city"], value="Paris")
    start_date = st.date_input(T["start_date"], value=date.today())
    nb_days = st.number_input(T["duration_days"], min_value=1, max_value=7, value=2)
    nb_people = st.number_input(T["travelers"], min_value=1, max_value=10, value=2)

    st.markdown("---")
    st.markdown(f"**{T['preferences']}**")
    arrival_mode = st.radio(T["transport_mode"], ["train", "car"], format_func=lambda x: x.capitalize())
    hotel_stars = st.slider(f"{T['hotel_stars']}", 1, 5, 3)

    # Budget Calculation
    budget = estimate_budget(nb_days, nb_people, hotel_stars, arrival_mode)
    remaining = BUDGET_CAP_EUR - budget["grand_total"]

    st.markdown("---")
    st.markdown(f"**{T['budget_grand_total']}:** `{budget['grand_total']:.0f} EUR`")
    st.markdown(f"**{T['budget_remaining']}:** `{remaining:.0f} EUR`")
    st.progress(min(budget["grand_total"] / BUDGET_CAP_EUR, 1.0))

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
def fetch_sncf_data(cities, start, end):
    return SERVICES["train"].search_trips(cities, start, end)

# Load Data
hotels, restaurants, sites = load_dest_data("Lille")
weather_service = SERVICES["weather"]
wiki_curr = get_wiki_summary("Lille, France")

# ── Main Layout ────────────────────────────────────────────────────────
st.title(f"⚜️ {T['app_title']}")
tab_home, tab_move, tab_planner = st.tabs([T['tab_home'], T['tab_move'], T['tab_plan']])

# ══════════════════════════════════════════════════════════════════════
# TAB 1: HOME
# ══════════════════════════════════════════════════════════════════════
with tab_home:
    st.info(wiki_curr or T["hero_fallback"])

    # Weather Bar
    st.markdown(f"#### {T['weather_title']}")
    forecast = weather_service.get_forecast(start_date)
    curr_weather = weather_service.get_current_weather()

    # Determine alerts
    is_cold_rainy = False
    if curr_weather is not None:
        try:
            temp_val = float(curr_weather.get("temperature_max", 20))
            desc_val = str(curr_weather.get("weather_description", "")).lower()
            is_cold_rainy = temp_val < COLD_THRESHOLD_C or any(k in desc_val for k in RAIN_KEYWORDS)
        except: pass

    if is_cold_rainy:
        st.markdown(f'<div class="indoor-alert">🌧️ {T["indoor_warning"]}</div>', unsafe_allow_html=True)

    if not forecast.empty:
        cards_html = '<div class="weather-row">'
        for _, row in forecast.iterrows():
            try:
                # _parsed_date is available from service
                d_obj = row.get("_parsed_date") or pd.to_datetime(row.get("date"))
                d_str = d_obj.strftime("%d-%m-%Y")
            except:
                d_str = str(row.get("date", ""))[:10]

            tmax = f"{float(row.get('temperature_max', 0)):.0f}"
            tmin = f"{float(row.get('temperature_min', 0)):.0f}"
            desc = row.get("weather_description", "—")

            cards_html += f"""
            <div class="weather-card">
                <div class="wdate">{d_str}</div>
                <div class="temp">{tmax}°/{tmin}°</div>
                <div class="desc">{desc}</div>
            </div>"""
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)
    else:
        st.warning(T["no_weather"])

    # Map
    st.markdown(f"#### {T['map_legend']}")
    m = folium.Map(location=LILLE_COORDS, zoom_start=14, tiles="CartoDB positron")

    # Feature Groups
    hg = FeatureGroup(name=f"🏨 {T['hotel']}")
    rg = FeatureGroup(name=f"🍴 {T['restaurants']}")
    sg = FeatureGroup(name=f"🏛️ {T['activities']}")

    for h in hotels:
        if h.get("latitude"):
            folium.Marker(
                [h["latitude"], h["longitude"]],
                popup=f"<b>{h.get('name')}</b><br>⭐ {h.get('stars')}",
                icon=folium.Icon(color="blue", icon="bed", prefix="fa")
            ).add_to(hg)

    for r in restaurants[:80]:
        if r.get("latitude"):
            folium.Marker(
                [r["latitude"], r["longitude"]],
                popup=f"<b>{r.get('name')}</b><br>🍽️ {r.get('cuisine')}",
                icon=folium.Icon(color="red", icon="cutlery", prefix="fa")
            ).add_to(rg)

    for s in sites[:80]:
        if s.get("latitude"):
            folium.Marker(
                [s["latitude"], s["longitude"]],
                popup=f"<b>{s.get('name')}</b><br>📌 {s.get('type')}",
                icon=folium.Icon(color="green", icon="landmark", prefix="fa")
            ).add_to(sg)

    hg.add_to(m)
    rg.add_to(m)
    sg.add_to(m)
    folium.LayerControl().add_to(m)

    st_folium(m, width="100%", height=500, returned_objects=[])


# ══════════════════════════════════════════════════════════════════════
# TAB 2: MOVE
# ══════════════════════════════════════════════════════════════════════
with tab_move:
    st.markdown(f"### {T['tab_move']}")

    # Train Data
    st.markdown(f"#### {T['route_table_title']}")

    # Load cached first
    cached_trains = SERVICES["train"].load_cache()
    if cached_trains is not None and not cached_trains.empty:
        st.dataframe(cached_trains, hide_index=True, use_container_width=True)
    else:
        st.info(T["no_trains"])

    # Fetcher
    fetch_cities = st.text_input(T["start_city"], value="Paris, London, Brussels", key="sncf_input")
    if st.button("🔄 Fetch SNCF Trips", key="fetch_btn"):
        c_list = [c.strip() for c in fetch_cities.split(",") if c.strip()]
        dt_start = datetime.combine(start_date, datetime.min.time())
        dt_end = datetime.combine(start_date + timedelta(days=nb_days), datetime.min.time())

        with st.spinner(T["searching"]):
            res = fetch_sncf_data(c_list, dt_start, dt_end)

        if isinstance(res, list) and res:
            st.success(f"Found {len(res)} trips.")
            st.dataframe(pd.DataFrame(res), hide_index=True, use_container_width=True)
        elif isinstance(res, dict) and "error" in res:
            st.error(res["error"])
        else:
            st.warning("No trips found.")

    st.markdown("---")

    # Comparison
    train_total = TRAIN_BASE_EUR * TRAIN_TGV_MULTIPLIER * nb_people
    car_total = (PARKING_DAILY_EUR * nb_days) + CAR_FUEL_BASE_EUR

    c1, c2, c3 = st.columns([5,1,5])
    with c1:
        st.markdown(f"""<div class="compare-card">
            <h3>{T['train_card']}</h3>
            <div class="price">{train_total:.0f} EUR</div>
            <div class="detail">{nb_people} × {TRAIN_BASE_EUR * TRAIN_TGV_MULTIPLIER:.0f} EUR</div>
            <div class="detail">+ {T['budget_local']}: {METRO_DAY_PASS_EUR * nb_days:.0f} EUR</div>
        </div>""", unsafe_allow_html=True)
    with c2:
         st.markdown(f'<div style="margin-top:50px;"><div class="vs-badge">{T["vs"]}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="compare-card">
            <h3>{T['car_card']}</h3>
            <div class="price">{car_total:.0f} EUR</div>
            <div class="detail">{T['parking']}: {PARKING_DAILY_EUR * nb_days} EUR</div>
            <div class="detail">{T['fuel_cost']}: {CAR_FUEL_BASE_EUR} EUR</div>
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
    st.markdown(f"### 💰 {T['budget']}")

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("🏨 " + T["hotel"], f"{budget['hotel_total']}€")
    b2.metric("🍽️ " + T["meals_total"], f"{budget['meals_total']}€")
    b3.metric("🚆/🚗 " + T["transport_total"], f"{budget['transport_total']}€")
    b4.metric("🚌 " + T["budget_local"], f"{budget['local_transport']}€")

    st.markdown("---")

    # Generate Plan
    planner = TravelPlanner()
    plan, recap = planner.plan_trip(start_date, nb_days, hotels, restaurants, sites)

    st.markdown(f"### 📍 {T['master_map']}")
    mm = folium.Map(location=LILLE_COORDS, zoom_start=13, tiles="CartoDB positron")

    DAY_COLORS = ["blue", "red", "green", "purple", "orange", "darkblue", "cadetblue"]

    # Render Itinerary
    for day in plan:
        day_num = day["day"]
        color = DAY_COLORS[(day_num - 1) % len(DAY_COLORS)]

        # Weather Header
        d_weather = "—"
        d_temp = "—"
        # Find weather for this day
        d_date = pd.Timestamp(day["date"])
        # We need weather df from service to match dates
        # Simplification: just iterate forecast we already fetched
        w_row = forecast[forecast["_parsed_date"] == d_date]
        if not w_row.empty:
            r = w_row.iloc[0]
            d_temp = f"{(r.get('temperature_max',0)+r.get('temperature_min',0))/2:.0f}°C"
            d_weather = r.get("weather_description", "—")

        st.markdown(f"""
        <div class="day-card">
            <h4 style="color:{color}">📅 {T['day_label']} {day_num} — {day['date']} ({d_temp}, {d_weather})</h4>
        </div>""", unsafe_allow_html=True)

        col_act, col_din = st.columns([3, 2])

        # Activities
        with col_act:
            st.markdown(f"**{T['morning_activities']}**")
            for i, a in enumerate(day["morning_activities"]):
                st.markdown(f"- 09:00 🏛️ **{a['name']}**")
                folium.Marker([a["latitude"], a["longitude"]],
                              popup=f"D{day_num}: {a['name']}",
                              icon=folium.Icon(color=color, icon="landmark", prefix="fa")).add_to(mm)

            st.markdown(f"**{T['afternoon_activities']}**")
            for i, a in enumerate(day["afternoon_activities"]):
                st.markdown(f"- 14:00 📍 **{a['name']}**")
                folium.Marker([a["latitude"], a["longitude"]],
                              popup=f"D{day_num}: {a['name']}",
                              icon=folium.Icon(color=color, icon="camera", prefix="fa")).add_to(mm)

        # Dining
        with col_din:
            st.markdown(f"**{T['morning_dining']}** (Breakfast/Lunch)")
            if day["breakfast"]:
                st.markdown(f"- 🥐 {day['breakfast']['name']}")
                folium.Marker([day["breakfast"]["latitude"], day["breakfast"]["longitude"]],
                              popup=f"D{day_num} Breakfast",
                              icon=folium.Icon(color=color, icon="coffee", prefix="fa")).add_to(mm)
            if day["lunch"]:
                st.markdown(f"- 🥗 {day['lunch']['name']}")
                folium.Marker([day["lunch"]["latitude"], day["lunch"]["longitude"]],
                              popup=f"D{day_num} Lunch",
                              icon=folium.Icon(color=color, icon="cutlery", prefix="fa")).add_to(mm)

            st.markdown(f"**{T['evening_dining']}**")
            if day["dinner"]:
                st.markdown(f"- 🍷 {day['dinner']['name']}")
                folium.Marker([day["dinner"]["latitude"], day["dinner"]["longitude"]],
                              popup=f"D{day_num} Dinner",
                              icon=folium.Icon(color=color, icon="glass", prefix="fa")).add_to(mm)

    st_folium(mm, width="100%", height=500, returned_objects=[])
