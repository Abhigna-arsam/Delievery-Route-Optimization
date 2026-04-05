class CarbonCalculator:

    CO2_PER_LITER = {
        "petrol": 2.31,
        "diesel": 2.68
    }

    DEFAULT_MILEAGE = 15

    @staticmethod
    def calculate_metrics(optimized_dist, naive_dist=None, fuel_type="petrol"):

        if optimized_dist <= 0:
            return {}

        mileage = CarbonCalculator.DEFAULT_MILEAGE
        co2_rate = CarbonCalculator.CO2_PER_LITER.get(fuel_type, 2.31)

        fuel_used = round(optimized_dist / mileage, 2)
        co2_emitted = round(fuel_used * co2_rate, 2)

        fuel_saved = 0
        carbon_saved = 0

        if naive_dist and naive_dist > optimized_dist:
            fuel_saved = round((naive_dist - optimized_dist) / mileage, 2)
            carbon_saved = round(fuel_saved * co2_rate, 2)

        score = min(100, 70 + int(carbon_saved * 3))

        return {
            "fuel_used": fuel_used,
            "co2_emitted": co2_emitted,
            "fuel_saved": fuel_saved,
            "carbon_saved": carbon_saved,
            "environmental_score": score
        }
def calculate_carbon_metrics(distance_km):
    mileage = 15
    co2_rate = 2.31

    fuel_used = round(distance_km / mileage, 2)
    co2_emitted = round(fuel_used * co2_rate, 2)

    eco_score = max(60, min(100, 100 - int(co2_emitted * 2)))

    return {
        "fuel_used": fuel_used,
        "co2_emitted": co2_emitted,
        "eco_score": eco_score
    }