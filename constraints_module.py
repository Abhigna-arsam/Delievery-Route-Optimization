class ConstraintManager:

    @staticmethod
    def check_time_windows(route_indices, distance_matrix, avg_speed=35):

        results = []
        elapsed = 0

        for i in range(len(route_indices)):

            if i > 0:
                prev = route_indices[i - 1]
                curr = route_indices[i]
                dist = distance_matrix[prev][curr]
                elapsed += (dist / avg_speed) * 60

            results.append({
                "location_id": route_indices[i],
                "arrival_time": round(elapsed, 1),
                "within_window": elapsed <= 120
            })

        return results

    @staticmethod
    def apply_emergency(route_indices, emergency_idx):

        if emergency_idx in route_indices:
            route_indices.remove(emergency_idx)
            route_indices.insert(1, emergency_idx)

        return route_indices
