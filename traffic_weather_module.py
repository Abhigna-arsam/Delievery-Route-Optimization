import datetime

class JourneySimulator:

    WEATHER_MAP = {
        "normal": 1.0,
        "rainy": 1.3,
        "heatwave": 1.2,
        "storm": 1.6
    }

    @staticmethod
    def is_peak():
        hour = datetime.datetime.now().hour
        return (8 <= hour <= 10) or (17 <= hour <= 19)

    @staticmethod
    def get_eta_data(distance_km, weather="normal", base_speed=40):

        if distance_km <= 0:
            return {}

        traffic_mult = 1.5 if JourneySimulator.is_peak() else 1.1
        weather_mult = JourneySimulator.WEATHER_MAP.get(weather, 1.0)

        minutes = (distance_km / base_speed) * 60
        adjusted = minutes * traffic_mult * weather_mult

        return {
            "estimated_time": round(adjusted, 1),
            "traffic_multiplier": traffic_mult,
            "weather_multiplier": weather_mult
        }
# traffic_simulation.py

def get_traffic_multiplier(hour):
    if (8 <= hour <= 10) or (17 <= hour <= 19):
        return 1.5
    return 1.1

def simulate_travel_time(distance, base_speed=40, hour=12):
    multiplier = get_traffic_multiplier(hour)
    travel_time = (distance / base_speed) * 60 * multiplier

    return {
        "estimated_time": round(travel_time, 1),
        "traffic_multiplier": multiplier
    }