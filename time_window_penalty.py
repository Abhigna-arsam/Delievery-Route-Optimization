
def check_time_windows(optimized_addresses, eta_minutes):
    status = []
    current_time = eta_minutes

    for i, location in enumerate(optimized_addresses):
        window_start = 0
        window_end = 120  # Example 2 hour window

        within = window_start <= current_time <= window_end

        status.append({
            "location_id": i,
            "arrival_time": round(current_time, 1),
            "within_window": within
        })

        current_time += 15  # assume 15 min between stops

    return status
