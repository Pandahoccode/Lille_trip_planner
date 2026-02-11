"""Travel planner: POI loading, itinerary generation, and budget estimation."""


import math
import os
import random
from datetime import timedelta

# ── Budget constants ─────────────────────────────────────────────────
MEAL_BREAKFAST_EUR = 9
MEAL_LUNCH_EUR = 14
MEAL_DINNER_EUR = 14
DAILY_MEAL_TOTAL = MEAL_BREAKFAST_EUR + MEAL_LUNCH_EUR + MEAL_DINNER_EUR

HOTEL_BASE_EUR = 50
HOTEL_STAR_INCREMENT_EUR = 10

METRO_DAY_PASS_EUR = 4.64
PARKING_DAILY_EUR = 15
CAR_FUEL_BASE_EUR = 20
TRAIN_BASE_EUR = 25
TRAIN_TGV_MULTIPLIER = 1.5

# ── Train route database ────────────────────────────────────────────
TRAIN_ROUTES = [
    {
        "route": "Paris → Lille",
        "price_min": 10.50,
        "price_max": 30.00,
        "operator": "OUIGO / TGV",
        "departure_station": "Paris Gare du Nord",
        "arrival_station": "Lille Flandres",
        "duration": "~1h02",
    },
    {
        "route": "London → Lille",
        "price_min": 44.00,
        "price_max": 126.00,
        "operator": "Eurostar",
        "departure_station": "London St Pancras",
        "arrival_station": "Lille Europe",
        "duration": "~1h22",
    },
    {
        "route": "Brussels → Lille",
        "price_min": 15.00,
        "price_max": 24.00,
        "operator": "TGV / Thalys",
        "departure_station": "Bruxelles-Midi",
        "arrival_station": "Lille Europe",
        "duration": "~0h35",
    },
]





def _haversine(lat1, lon1, lat2, lon2):
    """Distance in km between two lat/lon points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class TravelPlanner:
    """Generate a day-by-day trip itinerary with proximity pairing."""

    @staticmethod
    def _pick_nearby(items, k, used):
        """Pick k nearby items: random first, then closest unused."""
        available = [
            x for x in items
            if x.get("name") and x.get("name") not in used
            and x.get("latitude") and x.get("longitude")
        ]
        if not available:
            return []
        if len(available) <= k:
            return available

        first = random.choice(available)
        result = [first]
        remaining = [x for x in available if x is not first]

        while len(result) < k and remaining:
            ref = result[-1]
            remaining.sort(
                key=lambda x: _haversine(
                    ref["latitude"], ref["longitude"],
                    x["latitude"], x["longitude"],
                )
            )
            result.append(remaining.pop(0))

        return result

    @staticmethod
    def _pick_one(items, used):
        available = [x for x in items if x.get("name") and x.get("name") not in used]
        return random.choice(available) if available else None

    def pick_unique_hotel(self, hotels):
        ok = [h for h in hotels if h.get("latitude") and h.get("longitude")]
        return random.choice(ok) if ok else None

    def plan_trip(self, start_date, nb_days, hotels, restaurants, sites):
        hotel = self.pick_unique_hotel(hotels)

        restaurants_ok = [r for r in restaurants if r.get("latitude") and r.get("longitude")]
        sites_ok = [s for s in sites if s.get("latitude") and s.get("longitude")]

        used_restaurants = set()
        used_activities = set()
        plan = []

        for i in range(nb_days):
            d = (start_date + timedelta(days=i)).strftime("%d-%m-%Y")

            morning = self._pick_nearby(sites_ok, 2, used_activities)
            for a in morning:
                used_activities.add(a.get("name"))

            afternoon = self._pick_nearby(sites_ok, 2, used_activities)
            for a in afternoon:
                used_activities.add(a.get("name"))

            breakfast = self._pick_one(restaurants_ok, used_restaurants)
            if breakfast:
                used_restaurants.add(breakfast.get("name"))

            lunch = self._pick_one(restaurants_ok, used_restaurants)
            if lunch:
                used_restaurants.add(lunch.get("name"))

            dinner = self._pick_one(restaurants_ok, used_restaurants)
            if dinner:
                used_restaurants.add(dinner.get("name"))

            plan.append({
                "day": i + 1,
                "date": d,
                "morning_activities": morning,
                "afternoon_activities": afternoon,
                "breakfast": breakfast,
                "lunch": lunch,
                "dinner": dinner,
            })

        recap = {
            "hotel": (hotel or {}).get("name"),
            "unique_restaurants": sorted(used_restaurants),
            "unique_activities": sorted(used_activities),
        }
        return plan, recap


def estimate_budget(nb_days, nb_people, hotel_stars, transport_mode):
    """Compute total trip budget breakdown."""
    hotel_per_night = HOTEL_BASE_EUR + (hotel_stars * HOTEL_STAR_INCREMENT_EUR)
    hotel_total = hotel_per_night * nb_days

    meals_total = DAILY_MEAL_TOTAL * nb_days * nb_people

    if transport_mode == "train":
        transport_total = TRAIN_BASE_EUR * TRAIN_TGV_MULTIPLIER
        local_transport = METRO_DAY_PASS_EUR * nb_days
    else:
        transport_total = (PARKING_DAILY_EUR * nb_days) + CAR_FUEL_BASE_EUR
        local_transport = 0

    grand_total = hotel_total + meals_total + transport_total + local_transport

    return {
        "hotel_per_night": hotel_per_night,
        "hotel_total": hotel_total,
        "meals_daily": DAILY_MEAL_TOTAL,
        "meals_total": meals_total,
        "transport_total": transport_total,
        "local_transport": local_transport,
        "grand_total": grand_total,
    }
