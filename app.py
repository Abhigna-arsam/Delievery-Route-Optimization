# ============================================================
# app.py — Upgraded Delivery Route Optimizer (VRP System)
#
# Feature markers used throughout:
#   [F1]  Cross-Cluster Stop-Swap Optimization
#   [F2]  Constraint-Aware Weighted Clustering
#   [F3]  DBSCAN Dynamic EPS Tuning
#   [F4]  Improved Sweep Algorithm (Angle + Distance Hybrid)
#   [F5]  Distance Matrix Cache + Haversine Fallback
#   [F6]  Geocoding Cache
#   [F7]  Dynamic Re-Routing Simulation
#   [F8]  Improved CSV Validation
#   [F9]  Proper Logging (replaces all bare except blocks)
#   [F10] Visualization Insights (Heatmap + Long-Segment Highlight)
# ============================================================

import io
import logging
import math
import os
import random
import re
from datetime import datetime
from io import BytesIO
from itertools import permutations

import folium
import numpy as np
import openrouteservice
import pandas as pd
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file
from folium.plugins import HeatMap                          # [F10]
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate,
                                 Spacer, Table, TableStyle)
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans

from carbon_module import calculate_carbon_metrics
from time_window_penalty import check_time_windows
from traffic_weather_module import simulate_travel_time

load_dotenv()

# ============================================================
# [F9] Logging — structured, file + console, replaces bare excepts
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("route_optimizer.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("RouteOptimizer")

# ============================================================
# Constants — replaces all magic numbers throughout codebase
# ============================================================
EARTH_RADIUS_KM              = 6371.0
AVERAGE_SPEED_KMH            = 40          # km/h used for travel time estimates
TIME_DELAY_PENALTY           = 15.0        # minutes penalty per position for perishable
TIME_WINDOW_PENALTY          = 100.0       # minutes penalty for time-window violations
HAVERSINE_FALLBACK_THRESHOLD = 30          # [F5] use haversine if location count exceeds this
MAX_CSV_ROWS                 = 150         # [F8] hard cap on CSV import size
PERISHABLE_CLUSTER_WEIGHT    = 2.5         # [F2] pull-toward-depot factor for perishables
DBSCAN_EPS_START             = 0.5         # [F3] starting epsilon in km
DBSCAN_EPS_MAX               = 15.0        # [F3] maximum epsilon in km before fallback
DBSCAN_EPS_STEP              = 0.5         # [F3] increment per tuning iteration in km
SWEEP_ANGLE_WEIGHT           = 0.60        # [F4] weight for polar angle rank
SWEEP_DISTANCE_WEIGHT        = 0.40        # [F4] weight for distance rank
TRAFFIC_DELAY_PROB           = 0.20        # [F7] probability of delay per segment
TRAFFIC_DELAY_FACTOR_MIN     = 1.2         # [F7] minimum delay multiplier
TRAFFIC_DELAY_FACTOR_MAX     = 2.0         # [F7] maximum delay multiplier
INEFFICIENT_STD_FACTOR       = 1.5         # [F10] flag segment if > mean + N*std

# ============================================================
# App & client setup
# ============================================================
app = Flask(__name__)

ORS_API_KEY = os.getenv(
    "ORS_API_KEY",
    "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImE5ZmQyYzY5ZjY3NjQ0MGM5NTI1MDIzNzdlNjExOGYyIiwiaCI6Im11cm11cjY0In0=",
)
client = openrouteservice.Client(key=ORS_API_KEY)

active_deliveries  = {}
_last_route_result = {}

# ============================================================
# [F6] Geocoding Cache — avoids duplicate API calls
# ============================================================
geo_cache: dict = {}

# ============================================================
# [F5] Distance Matrix Cache — keyed by (lon, lat) tuples
# ============================================================
_dist_matrix_cache: dict = {}


# ============================================================
# Helper: Haversine Distance
# ============================================================
def haversine_km(coord1: tuple, coord2: tuple) -> float:
    """Return great-circle distance in km between two (lon, lat) points."""
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


# ============================================================
# [F5] Haversine Distance Matrix Builder
# ============================================================
def build_haversine_matrix(coords: list) -> list:
    """
    Build a full n×n distance matrix using haversine formula.

    Used as a zero-API-call fallback when len(coords) > HAVERSINE_FALLBACK_THRESHOLD,
    or internally during dynamic re-routing simulation.

    Args:
        coords: list of (lon, lat) tuples

    Returns:
        n×n list of floats (distances in km)
    """
    n = len(coords)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = haversine_km(coords[i], coords[j])
    return matrix


# ============================================================
# Geocoding — Nominatim Fallback  [F9: logging added]
# ============================================================
def geocode_nominatim(address: str, countrycodes: str = "in") -> dict | None:
    """Fallback geocoder using Nominatim (OpenStreetMap)."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json",
            "limit": 1,
            "countrycodes": countrycodes,
        }
        headers = {"User-Agent": "DeliveryRouteOptimizer/1.0"}
        r = requests.get(url, params=params, headers=headers, timeout=8)
        r.raise_for_status()
        arr = r.json()
        if not arr:
            logger.warning("[Nominatim] No result for: %s", address)
            return None
        item = arr[0]
        return {
            "coordinates": (float(item["lon"]), float(item["lat"])),
            "label": item.get("display_name", address),
        }
    except requests.RequestException as exc:
        logger.error("[Nominatim] Request error for '%s': %s", address, exc)
        return None
    except Exception as exc:
        logger.error("[Nominatim] Unexpected error for '%s': %s", address, exc)
        return None


def geocode_address(address: str, focus: tuple | None = None,
                    max_distance_km: float = 60) -> dict | None:
    """Geocode via ORS with Nominatim fallback.  [F9: bare except replaced]"""
    try:
        search_address = f"{address}, India" if ", India" not in address else address
        params = {
            "text": search_address,
            "size": 1,
            "boundary.country": "IN",
            "boundary.rect.min_lon": 77.0,
            "boundary.rect.min_lat": 16.0,
            "boundary.rect.max_lon": 81.0,
            "boundary.rect.max_lat": 19.5,
        }
        if focus:
            lon, lat = focus
            params.update({
                "focus.point.lat": lat,
                "focus.point.lon": lon,
                "boundary.rect.min_lon": lon - 0.4,
                "boundary.rect.max_lon": lon + 0.4,
                "boundary.rect.min_lat": lat - 0.4,
                "boundary.rect.max_lat": lat + 0.4,
            })

        res      = client.request("/geocode/search", params)
        features = res.get("features", [])

        if not features:
            return geocode_nominatim(address)

        feature   = features[0]
        lon, lat  = feature["geometry"]["coordinates"]
        label     = feature.get("properties", {}).get("label", address)
        result    = {"coordinates": (lon, lat), "label": label}

        if focus and haversine_km(focus, result["coordinates"]) > max_distance_km:
            return geocode_nominatim(address) or result

        return result

    except Exception as exc:
        logger.warning("[ORS Geocode] Failed for '%s': %s — falling back to Nominatim", address, exc)
        return geocode_nominatim(address)


# ============================================================
# [F6] Geocoding Cache Wrapper
# ============================================================
def geocode_address_cached(address: str, focus: tuple | None = None,
                            max_distance_km: float = 60) -> dict | None:
    """
    Thin cache layer over geocode_address.

    Cache key = normalised address + focus point (to 4 decimal places).
    Prevents repeated API/Nominatim calls for identical inputs within a session.
    """
    focus_key = f"{focus[0]:.4f},{focus[1]:.4f}" if focus else "none"
    cache_key = f"{address.lower().strip()}|{focus_key}"

    if cache_key in geo_cache:
        logger.debug("[GeoCache] HIT  : %s", address)
        return geo_cache[cache_key]

    result = geocode_address(address, focus=focus, max_distance_km=max_distance_km)
    if result:
        geo_cache[cache_key] = result
        logger.debug("[GeoCache] STORE: %s", address)
    return result


# ============================================================
# [F5] Cached Distance Matrix  (ORS API  or  Haversine fallback)
# ============================================================
def get_distance_matrix(ors_client, coords: list, items: list,
                         geocode_errors: list) -> tuple:
    """
    Obtain a distance matrix with two-level optimisation:

    Level 1 — In-memory cache:
        If the exact set of coordinates was seen before, return cached matrix
        immediately (zero API calls).

    Level 2 — Haversine fallback:
        If len(coords) > HAVERSINE_FALLBACK_THRESHOLD, build a straight-line
        matrix locally instead of making an expensive ORS API call.
        Accuracy is slightly lower but sufficient for large batches.

    Level 3 — ORS API:
        Standard path for small, accurate routing with road-network distances.

    Returns:
        (coords, items, distance_matrix_2d)
    """
    cache_key = tuple(tuple(c) for c in coords)

    if cache_key in _dist_matrix_cache:
        logger.info("[DistCache] HIT for %d locations", len(coords))
        return coords, items, _dist_matrix_cache[cache_key]

    if len(coords) > HAVERSINE_FALLBACK_THRESHOLD:
        logger.info(
            "[DistMatrix] %d locations > threshold %d → haversine fallback",
            len(coords), HAVERSINE_FALLBACK_THRESHOLD,
        )
        matrix = build_haversine_matrix(coords)
        _dist_matrix_cache[cache_key] = matrix
        return coords, items, matrix

    # ORS road-network matrix with bad-coord removal
    result_coords, result_items, matrix = safe_distance_matrix(
        ors_client, coords, items, geocode_errors
    )
    cache_key2 = tuple(tuple(c) for c in result_coords)
    _dist_matrix_cache[cache_key2] = matrix
    logger.info("[DistMatrix] ORS road-network matrix for %d locations", len(result_coords))
    return result_coords, result_items, matrix


# ============================================================
# [F8] Improved CSV Address Parser
# ============================================================
def parse_csv_addresses(file_storage) -> tuple:
    """
    Parse and rigorously validate a CSV file of delivery addresses.

    Required columns : 'address'
    Optional columns : 'item_type'  (perishable | non-perishable)

    Validation steps applied in order:
      1. UTF-8 encoding check  — clear error if Latin-1 / Windows-1252
      2. Header presence       — must contain 'address' column
      3. Empty row removal     — rows where address is blank / too short
      4. Duplicate removal     — case-insensitive, leading/trailing whitespace ignored
      5. Row limit             — rejects batches > MAX_CSV_ROWS after dedup
      6. item_type coercion    — invalid values default to 'non-perishable' with warning

    Returns:
        (records: list[dict],  summary: dict)

    Raises:
        ValueError with a user-friendly message on any validation failure.
    """
    try:
        raw    = file_storage.stream.read()
        stream = io.StringIO(raw.decode("utf-8"), newline=None)
        df     = pd.read_csv(stream)
    except UnicodeDecodeError:
        raise ValueError(
            "CSV encoding error — please save the file as UTF-8 "
            "(Excel: File → Save As → CSV UTF-8 (Comma delimited))."
        )
    except pd.errors.EmptyDataError:
        raise ValueError("CSV file is empty — no data was found after the header row.")
    except pd.errors.ParserError as exc:
        raise ValueError(
            f"CSV could not be parsed: {exc}. "
            "Ensure the file uses comma separators and has exactly one header row."
        )
    except Exception as exc:
        raise ValueError(f"Unexpected error reading CSV: {exc}")

    if df.empty:
        raise ValueError("CSV file has a header but no data rows.")

    # Normalise column names
    df.columns = [c.strip().lower() for c in df.columns]

    if "address" not in df.columns:
        available = ", ".join(f"'{c}'" for c in df.columns)
        raise ValueError(
            f"CSV must contain an 'address' column (case-insensitive). "
            f"Columns detected: {available}. "
            "Rename the correct column to 'address' and re-upload."
        )

    if "item_type" not in df.columns:
        df["item_type"] = "non-perishable"

    df["address"]   = df["address"].astype(str).str.strip()
    df["item_type"] = df["item_type"].astype(str).str.strip().str.lower()

    # ── Step 3: Remove empty / trivially short addresses ──────────────────
    original_count = len(df)
    df             = df[df["address"].str.len() > 3].reset_index(drop=True)
    empty_removed  = original_count - len(df)

    if df.empty:
        raise ValueError(
            f"After removing empty rows, no valid addresses remain "
            f"({empty_removed} empty rows were found)."
        )

    # ── Step 4: Deduplicate (case-insensitive, collapse whitespace) ────────
    df["_norm"]      = df["address"].str.lower().str.replace(r"\s+", " ", regex=True)
    dupes_removed    = int(df.duplicated(subset=["_norm"]).sum())
    df               = df.drop_duplicates(subset=["_norm"]).reset_index(drop=True)
    df               = df.drop(columns=["_norm"])

    # ── Step 5: Row limit ─────────────────────────────────────────────────
    if len(df) > MAX_CSV_ROWS:
        raise ValueError(
            f"CSV contains {len(df)} unique addresses after deduplication, "
            f"which exceeds the {MAX_CSV_ROWS}-row limit. "
            "Please split your data into smaller batches."
        )

    # ── Step 6: Coerce item_type ──────────────────────────────────────────
    valid_types  = {"perishable", "non-perishable"}
    bad_types    = df[~df["item_type"].isin(valid_types)]["item_type"].unique().tolist()
    invalid_fixed = len(bad_types)
    if bad_types:
        logger.warning("[F8-CSV] Invalid item_type values %s → defaulting to non-perishable", bad_types)
    df["item_type"] = df["item_type"].apply(
        lambda t: t if t in valid_types else "non-perishable"
    )

    summary = {
        "total":              len(df),
        "empty_removed":      empty_removed,
        "duplicates_removed": dupes_removed,
        "perishable":         int((df["item_type"] == "perishable").sum()),
        "non_perishable":     int((df["item_type"] == "non-perishable").sum()),
        "invalid_types_fixed": invalid_fixed,
    }
    logger.info("[F8-CSV] Import summary: %s", summary)

    return df[["address", "item_type"]].to_dict(orient="records"), summary


# ============================================================
# Safe Distance Matrix — unchanged logic, [F9] logging added
# ============================================================
def safe_distance_matrix(ors_client, coords, items, geocode_errors):
    """
    ORS distance matrix with automatic removal of unroutable coordinates.
    Retries after each removal until a clean matrix is obtained or coords exhausted.
    """
    working_coords = list(coords)
    working_items  = list(items)

    while len(working_coords) >= 2:
        try:
            matrix = ors_client.distance_matrix(
                locations=working_coords,
                profile="driving-car",
                metrics=["distance"],
                units="km",
            )
            return working_coords, working_items, matrix["distances"]

        except Exception as exc:
            err_str = str(exc)

            if "2010" in err_str:
                bad_idx = None
                for pattern in [
                    r"coordinate\s+(\d+)",
                    r"coordinate[:\s]+(\d+)",
                    r"specified\s+coordinate\s+(\d+)",
                    r'"index":\s*(\d+)',
                    r"index\s+(\d+)",
                ]:
                    m = re.search(pattern, err_str, re.IGNORECASE)
                    if m:
                        candidate = int(m.group(1))
                        if 0 <= candidate < len(working_coords):
                            bad_idx = candidate
                            break

                if bad_idx is None:
                    bad_idx = len(working_coords) - 1

                bad_label = working_items[bad_idx]["address"]
                geocode_errors.append(
                    f'Skipped "{bad_label}" — no drivable road nearby (ORS 2010).'
                )
                logger.warning(
                    "[ORS] Removed unroutable coord [%d] '%s'", bad_idx, bad_label
                )
                working_coords.pop(bad_idx)
                working_items.pop(bad_idx)
                continue

            logger.error("[ORS] Distance matrix error: %s", exc)
            raise

    raise ValueError(
        "No routable delivery locations remain after removing unroutable stops. "
        "Please verify that your addresses have drivable roads nearby."
    )


# ============================================================
# [F1] Cross-Cluster Stop-Swap Optimization
# ============================================================
def improve_cross_cluster(routes: list, coords: list, dist_matrix: list) -> list:
    """
    Inter-vehicle pairwise stop-swap optimization.

    Motivation:
        "Cluster first, route second" produces locally optimal routes per vehicle
        but ignores potential gains from reassigning stops across vehicles.
        This function fixes that by exhaustively trying all pairwise swaps.

    Algorithm:
        For every pair of vehicles (v1, v2):
          For every stop pair (s1 in v1, s2 in v2):
            Temporarily swap s1 ↔ s2
            If combined route distance improves → accept permanently
        Repeat until no improving swap is found (convergence).

    Complexity: O(V² × S²) per iteration — fast for ≤ 5 vehicles / 50 stops.

    Args:
        routes:      list of routes with GLOBAL coord indices, e.g. [0, 3, 7, 0]
        coords:      full list of (lon, lat) tuples (global)
        dist_matrix: full n×n distance matrix indexed by global coord indices

    Returns:
        Optimized routes (same structure, potentially different stop assignments).
    """
    if len(routes) <= 1:
        return routes

    routes      = [list(r) for r in routes]   # deep copy — don't mutate input
    improved    = True
    iteration   = 0
    total_saved = 0.0

    while improved:
        improved  = False
        iteration += 1

        for v1 in range(len(routes)):
            for v2 in range(v1 + 1, len(routes)):
                r1 = routes[v1]
                r2 = routes[v2]

                # Swappable positions: skip position 0 (depot) and last (return-to-depot)
                swap_range1 = range(1, len(r1) - 1)
                swap_range2 = range(1, len(r2) - 1)

                if not list(swap_range1) or not list(swap_range2):
                    continue

                base_cost  = (
                    calculate_route_distance(r1, dist_matrix)
                    + calculate_route_distance(r2, dist_matrix)
                )
                best_gain  = 0.0
                best_state = None

                for i in swap_range1:
                    for j in swap_range2:
                        # Trial swap
                        nr1      = r1[:]
                        nr2      = r2[:]
                        nr1[i], nr2[j] = nr2[j], nr1[i]

                        new_cost = (
                            calculate_route_distance(nr1, dist_matrix)
                            + calculate_route_distance(nr2, dist_matrix)
                        )
                        gain = base_cost - new_cost

                        if gain > best_gain:
                            best_gain  = gain
                            best_state = (nr1[:], nr2[:])

                if best_state:
                    routes[v1], routes[v2] = best_state
                    improved     = True
                    total_saved += best_gain
                    logger.info(
                        "[F1] Iter %d  v%d↔v%d  saved %.3f km  (total %.3f km)",
                        iteration, v1 + 1, v2 + 1, best_gain, total_saved,
                    )

    logger.info("[F1] Cross-cluster done: %d iterations, %.3f km saved", iteration, total_saved)
    return routes


# ============================================================
# [F2] Constraint-Aware Weighted Feature Builder
# ============================================================
def build_weighted_features(coords: list, items: list) -> "np.ndarray":
    """
    Produce a feature matrix for clustering that encodes delivery constraints.

    Perishable items:
        Coordinates are pulled toward the depot proportionally.
        This causes them to cluster near the depot in geographic space,
        which translates to earlier delivery in the optimized route.

    Time-windowed items:
        Further pulled toward the depot in proportion to window urgency
        (tighter / earlier closing time → stronger pull).

    Args:
        coords: list of (lon, lat) — index 0 is always the depot
        items:  list of item dicts with 'type' and optional 'time_window'

    Returns:
        np.ndarray of shape (n_deliveries, 2) — weighted (lon, lat) features
    """
    depot_lon, depot_lat = coords[0]
    delivery_coords = np.array(
        [[lon, lat] for lon, lat in coords[1:]], dtype=float
    )
    weighted = delivery_coords.copy()

    for i, item in enumerate(items[1:]):   # items[0] is depot — skip
        pull_factor = 0.0

        if item.get("type") == "perishable":
            # Pull fraction: how far toward depot to shift (0 = stay, 1 = move to depot)
            pull_factor += 1.0 - (1.0 / PERISHABLE_CLUSTER_WEIGHT)

        if "time_window" in item:
            start_tw, end_tw = item["time_window"]
            # Urgency normalised to [0, 0.4] — tighter window → higher urgency
            urgency      = max(0.0, min(0.4, 1.0 - end_tw / 480.0))
            pull_factor += urgency

        pull_factor = min(pull_factor, 0.75)   # cap: never move more than 75% toward depot

        if pull_factor > 0.0:
            weighted[i, 0] = (
                delivery_coords[i, 0] * (1 - pull_factor) + depot_lon * pull_factor
            )
            weighted[i, 1] = (
                delivery_coords[i, 1] * (1 - pull_factor) + depot_lat * pull_factor
            )

    return weighted


# ============================================================
# Route Scoring & Optimization — unchanged from original
# ============================================================
def calculate_route_distance(route_indices: list, distance_matrix: list) -> float:
    """Sum of road distances along a route (global coordinate indices)."""
    total = 0.0
    for i in range(len(route_indices) - 1):
        total += distance_matrix[route_indices[i]][route_indices[i + 1]]
    return total


def calculate_route_score_with_priority(
    route_indices, items, distance_matrix, average_speed_kmh=AVERAGE_SPEED_KMH
):
    total_distance = calculate_route_distance(route_indices, distance_matrix)
    priority_penalty, arrival_time = 0.0, 0.0
    for i in range(1, len(route_indices)):
        prev_idx = route_indices[i - 1]
        curr_idx = route_indices[i]
        travel_time  = distance_matrix[prev_idx][curr_idx] / average_speed_kmh * 60
        arrival_time += travel_time
        if items[curr_idx]["type"] == "perishable":
            priority_penalty += (i - 1) * TIME_DELAY_PENALTY
        if "time_window" in items[curr_idx]:
            start_tw, end_tw = items[curr_idx]["time_window"]
            if arrival_time > end_tw:
                priority_penalty += TIME_WINDOW_PENALTY
            elif arrival_time < start_tw:
                priority_penalty += (start_tw - arrival_time) * 0.5
    return total_distance + priority_penalty


def nearest_neighbor_with_priority(coords, items, distance_matrix):
    n = len(coords)
    if n <= 1:
        return list(range(n))
    current_pos, unvisited, route = 0, set(range(1, n)), [0]
    perishable_items = {i for i in range(1, n) if items[i]["type"] == "perishable"}
    while unvisited:
        best_next, best_score = None, float("inf")
        for next_pos in unvisited:
            score = distance_matrix[current_pos][next_pos]
            if next_pos in perishable_items:
                score -= 12.0 * len(perishable_items & unvisited)
            elif perishable_items & unvisited:
                score += 15.0
            if score < best_score:
                best_score, best_next = score, next_pos
        route.append(best_next)
        unvisited.remove(best_next)
        current_pos = best_next
    return route


def two_opt_improvement(route_indices, distance_matrix):
    improved = True
    best_route    = route_indices[:]
    best_distance = calculate_route_distance(best_route, distance_matrix)
    while improved:
        improved = False
        for i in range(1, len(route_indices) - 1):
            for j in range(i + 1, len(route_indices)):
                new_route = route_indices[:]
                new_route[i:j + 1] = reversed(new_route[i:j + 1])
                new_distance = calculate_route_distance(new_route, distance_matrix)
                if new_distance < best_distance:
                    best_route, best_distance, improved = new_route, new_distance, True
                    break
            if improved:
                break
    return best_route


def nearest_neighbor_basic(coords, distance_matrix):
    n = len(coords)
    if n <= 1:
        return list(range(n))
    current_pos, unvisited, route = 0, set(range(1, n)), [0]
    while unvisited:
        nearest = min(unvisited, key=lambda x: distance_matrix[current_pos][x])
        route.append(nearest)
        unvisited.remove(nearest)
        current_pos = nearest
    return route


def optimize_delivery_route_advanced(coords, items, distance_matrix):
    n = len(coords)
    if n <= 1:
        return list(range(n))
    if n <= 8:
        best_route, best_score = None, float("inf")
        for perm in permutations(range(1, n)):
            route = [0] + list(perm)
            score = calculate_route_score_with_priority(route, items, distance_matrix)
            if score < best_score:
                best_score, best_route = score, route
        return best_route
    route1  = nearest_neighbor_with_priority(coords, items, distance_matrix)
    route2  = nearest_neighbor_basic(coords, distance_matrix)
    route2  = two_opt_improvement(route2, distance_matrix)
    score1  = calculate_route_score_with_priority(route1, items, distance_matrix)
    score2  = calculate_route_score_with_priority(route2, items, distance_matrix)
    return two_opt_improvement(
        route1 if score1 < score2 else route2, distance_matrix
    )


def analyze_route_quality(route_indices, items, distance_matrix):
    total_distance = calculate_route_distance(route_indices, distance_matrix)
    perish_pos = [
        i for i, idx in enumerate(route_indices)
        if idx > 0 and items[idx]["type"] == "perishable"
    ]
    avg_pos = sum(perish_pos) / len(perish_pos) if perish_pos else 0
    return {
        "total_distance": total_distance,
        "avg_perishable_position": avg_pos,
        "perishable_delivered_early": sum(
            1 for p in perish_pos if p <= len(route_indices) // 2
        ),
    }


# ============================================================
# [MODIFIED F2] KMeans Clustering — accepts weighted_coords
# ============================================================
def cluster_deliveries(coords: list, num_vehicles: int,
                        weighted_coords=None) -> dict:
    """
    KMeans clustering with optional constraint-weighted coordinates.

    When weighted_coords is provided (via build_weighted_features), the clustering
    happens in the weighted space, but returned indices refer to original coords.
    """
    if num_vehicles <= 1:
        return {0: list(range(1, len(coords)))}

    delivery_coords = np.array([[lon, lat] for lon, lat in coords[1:]])

    if len(delivery_coords) <= num_vehicles:
        return {i: [i + 1] for i in range(len(delivery_coords))}

    fit_coords = weighted_coords if weighted_coords is not None else delivery_coords

    kmeans = KMeans(n_clusters=num_vehicles, random_state=42, n_init=10)
    labels = kmeans.fit_predict(fit_coords)

    clusters: dict = {i: [] for i in range(num_vehicles)}
    for idx, label in enumerate(labels):
        clusters[label].append(idx + 1)
    return clusters


# ============================================================
# [FIXED F3] DBSCAN — Dynamic EPS Tuning with Warning
# ============================================================
def cluster_deliveries_dbscan(coords: list, num_vehicles: int,
                               items=None) -> tuple:
    """
    DBSCAN clustering with automatic epsilon tuning.

    Problem with fixed eps:
        A single eps value rarely produces exactly num_vehicles clusters.

    Solution:
        Scan eps from DBSCAN_EPS_START to DBSCAN_EPS_MAX in steps of DBSCAN_EPS_STEP.
        Stop as soon as the cluster count matches num_vehicles.
        If no matching eps found → fall back to KMeans and return a warning string.

    Returns:
        (clusters_dict, warning_or_None)
        warning is non-None when KMeans fallback was triggered.
    """
    if num_vehicles <= 1:
        return {0: list(range(1, len(coords)))}, None

    delivery_coords = np.array([[lon, lat] for lon, lat in coords[1:]])

    if len(delivery_coords) <= num_vehicles:
        return {i: [i + 1] for i in range(len(delivery_coords))}, None

    # Optionally use constraint-weighted space [F2]
    fit_coords = (
        build_weighted_features(coords, items)
        if items is not None else delivery_coords
    )

    best_labels = None
    best_eps    = None
    eps         = DBSCAN_EPS_START

    while eps <= DBSCAN_EPS_MAX + 1e-9:
        db     = DBSCAN(eps=eps, min_samples=1).fit(fit_coords)
        labels = list(db.labels_)
        n_clusters = len({l for l in labels if l != -1})

        if n_clusters == num_vehicles:
            best_labels = labels
            best_eps    = eps
            logger.info("[F3-DBSCAN] Found %d clusters at eps=%.4f", num_vehicles, eps)
            break

        eps = round(eps + DBSCAN_EPS_STEP, 6)

    # Fallback path
    if best_labels is None:
        warning = (
            f"DBSCAN could not form exactly {num_vehicles} clusters "
            f"after scanning eps {DBSCAN_EPS_START:.1f}–{DBSCAN_EPS_MAX:.1f} km. "
            "Falling back to KMeans."
        )
        logger.warning("[F3-DBSCAN] %s", warning)
        return cluster_deliveries(coords, num_vehicles), warning

    # Assign any noise points (-1) to nearest valid cluster
    for i, lbl in enumerate(best_labels):
        if lbl == -1:
            min_dist, nearest = float("inf"), 0
            for j, other in enumerate(best_labels):
                if other != -1:
                    d = float(np.linalg.norm(fit_coords[i] - fit_coords[j]))
                    if d < min_dist:
                        min_dist, nearest = d, other
            best_labels[i] = nearest

    unique_clusters = sorted(set(best_labels))
    label_to_v      = {lbl: vid for vid, lbl in enumerate(unique_clusters)}
    clusters: dict  = {i: [] for i in range(num_vehicles)}

    for idx, lbl in enumerate(best_labels):
        clusters[label_to_v[lbl]].append(idx + 1)

    return clusters, None


# ============================================================
# [MODIFIED F2] Agglomerative Clustering — accepts weighted_coords
# ============================================================
def cluster_deliveries_agglomerative(coords: list, num_vehicles: int,
                                      weighted_coords=None) -> dict:
    """
    Agglomerative (Ward linkage) clustering with optional weighted coordinates.
    """
    if num_vehicles <= 1:
        return {0: list(range(1, len(coords)))}

    delivery_coords = np.array([[lon, lat] for lon, lat in coords[1:]])

    if len(delivery_coords) <= num_vehicles:
        return {i: [i + 1] for i in range(len(delivery_coords))}

    fit_coords = weighted_coords if weighted_coords is not None else delivery_coords

    agg    = AgglomerativeClustering(n_clusters=num_vehicles, linkage="ward")
    labels = agg.fit_predict(fit_coords)

    clusters: dict = {i: [] for i in range(num_vehicles)}
    for idx, label in enumerate(labels):
        clusters[label].append(idx + 1)
    return clusters


# ============================================================
# [IMPROVED F4] Sweep Algorithm — Angle + Distance Hybrid
# ============================================================
def cluster_deliveries_sweep(coords: list, num_vehicles: int,
                              items=None) -> dict:
    """
    Improved Sweep Clustering using a hybrid polar score.

    Original sweep: sorts stops by polar angle from depot only.
    Problem: stops at the same angle but very different distances end up together,
             creating unbalanced route lengths.

    Improvement:
        hybrid_score = SWEEP_ANGLE_WEIGHT  × normalised_angle_rank
                     + SWEEP_DISTANCE_WEIGHT × normalised_distance_rank

    This produces tighter, more balanced clusters.
    Perishable items receive a small score bonus to appear earlier in the sweep.

    Args:
        coords:      full coordinate list (index 0 = depot)
        num_vehicles: number of clusters to form
        items:       optional list of item dicts for perishable prioritisation
    """
    if num_vehicles <= 1:
        return {0: list(range(1, len(coords)))}

    depot          = coords[0]
    delivery_coords = coords[1:]

    if len(delivery_coords) <= num_vehicles:
        return {i: [i + 1] for i in range(len(delivery_coords))}

    n = len(delivery_coords)

    stop_data = []
    for idx, (lon, lat) in enumerate(delivery_coords):
        angle = math.atan2(lat - depot[1], lon - depot[0])
        dist  = haversine_km(depot, (lon, lat))
        is_perishable = (
            items[idx + 1].get("type") == "perishable" if items else False
        )
        stop_data.append({
            "orig_idx":    idx + 1,
            "angle":       angle,
            "dist":        dist,
            "perishable":  is_perishable,
        })

    # Build normalised ranks for angle and distance separately
    sorted_by_angle = sorted(range(n), key=lambda i: stop_data[i]["angle"])
    sorted_by_dist  = sorted(range(n), key=lambda i: stop_data[i]["dist"])
    denom           = max(n - 1, 1)

    angle_rank = [0.0] * n
    dist_rank  = [0.0] * n
    for rank, i in enumerate(sorted_by_angle):
        angle_rank[i] = rank / denom
    for rank, i in enumerate(sorted_by_dist):
        dist_rank[i] = rank / denom

    for i, stop in enumerate(stop_data):
        score = (
            SWEEP_ANGLE_WEIGHT    * angle_rank[i]
            + SWEEP_DISTANCE_WEIGHT * dist_rank[i]
        )
        if stop["perishable"]:
            score = max(0.0, score - 0.05)   # deliver earlier
        stop["score"] = score

    sorted_stops = sorted(stop_data, key=lambda s: s["score"])

    total    = len(sorted_stops)
    base     = total // num_vehicles
    extra    = total % num_vehicles
    clusters: dict = {}
    start    = 0

    for v in range(num_vehicles):
        size        = base + (1 if v < extra else 0)
        clusters[v] = [s["orig_idx"] for s in sorted_stops[start:start + size]]
        start      += size

    return clusters


# ============================================================
# [MODIFIED] Smart Cluster Selector — now returns 3-tuple
# ============================================================
def smart_cluster(coords: list, num_vehicles: int, method: str = "auto",
                  items=None) -> tuple:
    """
    Select and apply the best clustering algorithm based on method and data size.

    Returns:
        (clusters_dict, algorithm_name_str, warning_or_None)

    The warning field is non-None only when DBSCAN falls back to KMeans.
    """
    num_stops = len(coords) - 1

    if method == "kmeans":
        weighted = build_weighted_features(coords, items) if items else None
        return cluster_deliveries(coords, num_vehicles, weighted), "KMeans", None

    elif method == "dbscan":
        clusters, warn = cluster_deliveries_dbscan(coords, num_vehicles, items)
        algo           = "DBSCAN" if warn is None else "DBSCAN→KMeans (fallback)"
        return clusters, algo, warn

    elif method == "agglomerative":
        weighted = build_weighted_features(coords, items) if items else None
        return (cluster_deliveries_agglomerative(coords, num_vehicles, weighted),
                "Agglomerative", None)

    elif method == "sweep":
        return cluster_deliveries_sweep(coords, num_vehicles, items), "Sweep", None

    else:   # auto — choose algorithm by problem size
        if num_stops <= 5:
            weighted = build_weighted_features(coords, items) if items else None
            return cluster_deliveries(coords, num_vehicles, weighted), "KMeans (auto)", None
        elif num_stops <= 15:
            weighted = build_weighted_features(coords, items) if items else None
            return (cluster_deliveries_agglomerative(coords, num_vehicles, weighted),
                    "Agglomerative (auto)", None)
        else:
            return (cluster_deliveries_sweep(coords, num_vehicles, items),
                    "Sweep (auto)", None)


# ============================================================
# [F7] Dynamic Re-Routing Simulation
# ============================================================
def simulate_dynamic_rerouting(route: list, coords: list, items: list,
                                dist_matrix: list) -> dict:
    """
    Simulate realistic traffic delays on a route and re-optimize on detection.

    Behaviour:
        Walk the route step by step.
        At each segment, randomly apply a delay with probability TRAFFIC_DELAY_PROB.
        When a delay occurs AND ≥ 2 stops remain:
            Re-optimize remaining stops using priority-aware nearest-neighbour
            on a local haversine sub-matrix (no API calls during simulation).
        Continue on the re-ordered route.

    Uses a seeded RNG (random.Random(42)) for reproducible demo output.

    Args:
        route:       list of global coord indices e.g. [0, 3, 7, 0]
        coords:      full list of (lon, lat)
        items:       full list of item dicts
        dist_matrix: global distance matrix

    Returns:
        dict with keys:
            'final_route'        — global indices after simulation
            'delay_events'       — list of delay info dicts
            'estimated_time_min' — total estimated travel time in minutes
            'reroutes_triggered' — number of re-optimisation events
    """
    if len(route) <= 2:
        dist = calculate_route_distance(route, dist_matrix)
        return {
            "final_route":        route,
            "delay_events":       [],
            "estimated_time_min": round(dist / AVERAGE_SPEED_KMH * 60, 1),
            "reroutes_triggered": 0,
        }

    rng            = random.Random(42)   # reproducible simulation
    current_route  = list(route)
    delay_events   = []
    elapsed_min    = 0.0
    reroutes       = 0
    step           = 0

    while step < len(current_route) - 1:
        from_idx = current_route[step]
        to_idx   = current_route[step + 1]

        seg_km  = dist_matrix[from_idx][to_idx]
        seg_min = seg_km / AVERAGE_SPEED_KMH * 60

        if rng.random() < TRAFFIC_DELAY_PROB:
            factor   = rng.uniform(TRAFFIC_DELAY_FACTOR_MIN, TRAFFIC_DELAY_FACTOR_MAX)
            seg_min *= factor
            extra    = round(seg_min * (1.0 - 1.0 / factor), 1)

            delay_events.append({
                "from_stop":    from_idx,
                "to_stop":      to_idx,
                "address":      items[to_idx]["address"] if to_idx < len(items) else "?",
                "delay_factor": round(factor, 2),
                "extra_min":    extra,
            })
            logger.info(
                "[F7] Delay step %d→%d: %.2f× (+%.1f min)", from_idx, to_idx, factor, extra
            )

            # Re-optimize remaining stops from current position
            remaining_global = current_route[step + 1 : -1]   # exclude return-to-depot
            if len(remaining_global) >= 2:
                origin          = from_idx
                sub_coord_list  = [coords[origin]] + [coords[i] for i in remaining_global]
                sub_item_list   = [items[origin]]  + [items[i]  for i in remaining_global]
                sub_mat         = build_haversine_matrix(sub_coord_list)
                re_order        = nearest_neighbor_with_priority(
                    sub_coord_list, sub_item_list, sub_mat
                )
                new_remaining   = [remaining_global[k - 1] for k in re_order[1:]]
                current_route   = (
                    current_route[: step + 1]
                    + new_remaining
                    + [current_route[-1]]
                )
                reroutes += 1
                logger.info("[F7] Re-optimized %d remaining stops", len(new_remaining))

        elapsed_min += seg_min
        step        += 1

    return {
        "final_route":        current_route,
        "delay_events":       delay_events,
        "estimated_time_min": round(elapsed_min, 1),
        "reroutes_triggered": reroutes,
    }


# ============================================================
# [F10] Visualization: Heatmap Layer
# ============================================================
def add_heatmap_layer(fmap: folium.Map, coords: list) -> None:
    """
    Add a toggleable delivery-density heatmap to the folium map.

    Only delivery locations (index > 0) are included, not the depot.
    Rendered as a separate layer so it can be toggled via LayerControl.
    """
    heat_data = [[coords[i][1], coords[i][0]] for i in range(1, len(coords))]
    if not heat_data:
        return
    heatmap_group = folium.FeatureGroup(name="📍 Delivery Density Heatmap", show=False)
    HeatMap(heat_data, radius=22, blur=16, min_opacity=0.35).add_to(heatmap_group)
    heatmap_group.add_to(fmap)
    logger.debug("[F10] Heatmap added: %d points", len(heat_data))


# ============================================================
# [F10] Visualization: Long-Segment Highlight Layer
# ============================================================
def add_inefficient_segment_layer(fmap: folium.Map, routes: list,
                                   coords: list, dist_matrix: list) -> int:
    """
    Highlight route segments that are statistically long (potential inefficiencies).

    A segment is flagged if its distance exceeds:
        mean(all_segments) + INEFFICIENT_STD_FACTOR × std(all_segments)

    Flagged segments are drawn in crimson on a separate toggleable layer
    with a tooltip showing the actual vs average distance.

    Returns:
        Number of flagged segments added to the map.
    """
    all_segs: list = []
    for route in routes:
        for i in range(len(route) - 1):
            d = dist_matrix[route[i]][route[i + 1]]
            all_segs.append((route[i], route[i + 1], d))

    if not all_segs:
        return 0

    distances = [s[2] for s in all_segs]
    mean_d    = float(np.mean(distances))
    std_d     = float(np.std(distances))
    threshold = mean_d + INEFFICIENT_STD_FACTOR * std_d

    flagged_group = folium.FeatureGroup(name="⚠️ Long Segments", show=True)
    flagged_count = 0

    for from_idx, to_idx, d in all_segs:
        if d > threshold:
            a = coords[from_idx]
            b = coords[to_idx]
            folium.PolyLine(
                [[a[1], a[0]], [b[1], b[0]]],
                color="crimson",
                weight=7,
                opacity=0.85,
                tooltip=f"⚠️ Long segment: {d:.1f} km  (avg {mean_d:.1f} km)",
            ).add_to(flagged_group)
            flagged_count += 1

    flagged_group.add_to(fmap)
    logger.info(
        "[F10] %d long segment(s) flagged (threshold: %.2f km)", flagged_count, threshold
    )
    return flagged_count


# ============================================================
# PDF Generation — unchanged from original
# ============================================================
def generate_route_pdf(route_result: dict) -> BytesIO:
    """Generate a formatted A4 PDF route sheet from the last optimised result."""
    buffer  = BytesIO()
    doc     = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Title"],
        fontSize=20, textColor=colors.HexColor("#1a1a2e"), spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleStyle", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#555555"), spaceAfter=14, alignment=1,
    )
    section_heading_style = ParagraphStyle(
        "SectionHeading", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor("#e67e22"), spaceBefore=14, spaceAfter=4,
    )
    vehicle_heading_style = ParagraphStyle(
        "VehicleHeading", parent=styles["Heading3"],
        fontSize=11, textColor=colors.HexColor("#2980b9"), spaceBefore=10, spaceAfter=4,
    )
    stop_style = ParagraphStyle(
        "StopStyle", parent=styles["Normal"],
        fontSize=9, leading=14, leftIndent=12,
    )

    TYPE_ICONS = {
        "perishable":     "🥬 Perishable",
        "non-perishable": "📦 Standard",
        "current":        "🏠 Depot",
    }

    def type_label(t):
        return TYPE_ICONS.get(t, t.capitalize())

    story                = []
    optimized_addresses  = route_result.get("optimized_addresses", [])
    route_info           = route_result.get("route_info", {})
    carbon_data          = route_result.get("carbon_data")
    generated_at         = datetime.now().strftime("%d %b %Y  %H:%M")

    story.append(Paragraph("🚚  Delivery Route Plan", title_style))
    story.append(Paragraph(f"Generated: {generated_at}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=colors.HexColor("#e67e22"), spaceAfter=10))
    story.append(Paragraph("Route Summary", section_heading_style))

    summary_data = [
        ["Metric", "Value"],
        ["Total Distance",       f"{route_info.get('total_distance', '—')} km"],
        ["Total Stops",          str(route_info.get("total_stops", "—"))],
        ["Vehicles Used",        str(route_info.get("num_vehicles", "—"))],
        ["Distance Saved",       f"{route_info.get('distance_saved', '—')} km  "
                                 f"({route_info.get('percent_saved', '—')}% improvement)"],
        ["Clustering Algorithm", route_info.get("cluster_algorithm", "N/A")],
    ]
    if carbon_data:
        summary_data += [
            ["Estimated Fuel", f"{carbon_data.get('fuel_used', '—')} L"],
            ["CO₂ Emission",   f"{carbon_data.get('co2_emitted', '—')} kg"],
            ["Eco Score",      f"{carbon_data.get('eco_score', '—')}%"],
        ]

    summary_table = Table(summary_data, colWidths=[5.5*cm, 11*cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 10),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#f4f4f4"), colors.white]),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(summary_table)

    vehicle_distances = route_info.get("vehicle_distances", [])
    if vehicle_distances:
        story.append(Spacer(1, 8))
        vd_data = [["Vehicle", "Route Distance"]] + [
            [f"Vehicle {i+1}", f"{d} km"] for i, d in enumerate(vehicle_distances)
        ]
        vd_table = Table(vd_data, colWidths=[5.5*cm, 11*cm])
        vd_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#2980b9")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 10),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#eaf4fb"), colors.white]),
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 1), (-1, -1), 9),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(vd_table)

    story.append(Paragraph("Driver Route Details", section_heading_style))
    story.append(HRFlowable(width="100%", thickness=0.8,
                             color=colors.HexColor("#dddddd"), spaceAfter=6))

    vehicle_stops: dict = {}
    for stop in optimized_addresses:
        v = stop["vehicle"]
        vehicle_stops.setdefault(v, []).append(stop)

    for vehicle_id, stops in sorted(vehicle_stops.items()):
        story.append(Paragraph(f"🚚  Vehicle {vehicle_id}", vehicle_heading_style))
        stop_rows      = []
        delivery_count = 1

        for stop in stops:
            if stop["is_current"]:
                label     = "START"
                label_col = colors.HexColor("#27ae60")
                addr_text = f"<b>{stop['address']}</b>"
            else:
                label     = str(delivery_count)
                label_col = colors.HexColor("#2c3e50")
                addr_text = (
                    f"{stop['address']}"
                    f"  <font color='#777777' size='8'>[{type_label(stop['type'])}]</font>"
                )
                delivery_count += 1

            stop_rows.append([
                Paragraph(f"<b>{label}</b>", ParagraphStyle(
                    "LabelStyle", parent=styles["Normal"],
                    fontSize=9, textColor=label_col, alignment=1)),
                Paragraph(addr_text, stop_style),
            ])

        stop_table = Table(stop_rows, colWidths=[1.2*cm, 15.3*cm])
        stop_table.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS",(0, 0), (-1, -1), [colors.HexColor("#f9f9f9"), colors.white]),
            ("LINEBELOW",    (0, 0), (-1, -1), 0.3, colors.HexColor("#e0e0e0")),
        ]))
        story.append(stop_table)
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.8,
                             color=colors.HexColor("#cccccc"), spaceAfter=6))
    story.append(Paragraph(
        "Generated by Delivery Route Optimizer · Multi-Vehicle Sustainable VRP System",
        ParagraphStyle("Footer", parent=styles["Normal"],
                       fontSize=7, textColor=colors.grey, alignment=1),
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ============================================================
# Polyline Drawing — unchanged from original
# ============================================================
def draw_route_polyline(ors_client, opt_coords, v_color, container):
    """
    Draw a road-following polyline into `container` (a FeatureGroup or Map).

    All GeoJson/PolyLine objects are added to `container`, NOT directly to
    the map — this prevents folium from registering each geometry as a separate
    unnamed layer (which was causing the macro_element_* names in LayerControl).

    4-tier fallback:
      1. ORS full route
      2. ORS segment-by-segment
      3. OSRM public API (real road curves, no key required)
      4. Straight solid PolyLine (last resort)
    """
    if len(opt_coords) < 2:
        return

    # ── Tier 1: ORS full route ─────────────────────────────────────────────
    try:
        route_geo = ors_client.directions(
            coordinates=opt_coords, profile="driving-car", format="geojson"
        )
        folium.GeoJson(
            route_geo,
            style_function=lambda x, c=v_color: {"color": c, "weight": 5},
        ).add_to(container)
        return
    except Exception as exc:
        logger.debug("[Polyline] Full ORS failed: %s", exc)

    # ── Tiers 2, 3, 4: per-segment ────────────────────────────────────────
    for seg_i in range(len(opt_coords) - 1):
        a, b  = opt_coords[seg_i], opt_coords[seg_i + 1]
        drawn = False

        # Tier 2: ORS single segment
        try:
            seg_geo = ors_client.directions(
                coordinates=[a, b], profile="driving-car", format="geojson"
            )
            folium.GeoJson(
                seg_geo,
                style_function=lambda x, c=v_color: {"color": c, "weight": 5},
            ).add_to(container)
            drawn = True
        except Exception as exc:
            logger.debug("[Polyline] ORS segment failed: %s", exc)

        if not drawn:
            # Tier 3: OSRM public API
            try:
                osrm_url = (
                    f"http://router.project-osrm.org/route/v1/driving/"
                    f"{a[0]},{a[1]};{b[0]},{b[1]}"
                    f"?overview=full&geometries=geojson"
                )
                resp = requests.get(osrm_url, timeout=6)
                data = resp.json()
                if data.get("code") == "Ok" and data["routes"]:
                    geojson_line = {
                        "type": "Feature",
                        "geometry": data["routes"][0]["geometry"],
                        "properties": {},
                    }
                    folium.GeoJson(
                        geojson_line,
                        style_function=lambda x, c=v_color: {"color": c, "weight": 5},
                    ).add_to(container)
                    drawn = True
            except Exception as exc:
                logger.debug("[Polyline] OSRM failed: %s", exc)

        if not drawn:
            # Tier 4: straight solid line
            folium.PolyLine(
                [[a[1], a[0]], [b[1], b[0]]],
                color=v_color, weight=4, opacity=0.75,
                tooltip="Segment (road data unavailable)",
            ).add_to(container)


# ============================================================
# Flask Routes
# ============================================================
@app.route("/", methods=["GET", "POST"])
def index():
    optimized_addresses  = []
    map_html             = None
    error                = None
    route_info           = None
    carbon_data          = None
    time_window_status   = None
    geocode_errors       = []
    csv_import_info      = None
    coords, items, dists = [], [], []

    if request.method != "POST":
        return render_template(
            "index.html",
            optimized_addresses=[], map_html=None, error=None,
            route_info=None, carbon_data=None, time_window_status=None,
            csv_import_info=None,
        )

    curr_addr      = request.form.get("current_address", "").strip()
    num_vehicles   = int(request.form.get("num_vehicles", 1))
    cluster_method = request.form.get("cluster_method", "auto")
    csv_file       = request.files.get("csv_file")

    # ── Address input: CSV or form fields ─────────────────────────────────
    if csv_file and csv_file.filename.endswith(".csv"):
        try:
            parsed_rows, csv_summary = parse_csv_addresses(csv_file)  # [F8]
            addrs      = [r["address"]   for r in parsed_rows]
            item_types = [r["item_type"] for r in parsed_rows]
            csv_import_info = (
                f"CSV imported: {csv_summary['total']} addresses "
                f"({csv_summary['perishable']} perishable, "
                f"{csv_summary['non_perishable']} standard). "
                f"Removed: {csv_summary['empty_removed']} empty, "
                f"{csv_summary['duplicates_removed']} duplicates."
            )
        except ValueError as ve:
            logger.warning("[CSV] Import failed: %s", ve)
            return render_template(
                "index.html",
                optimized_addresses=[], map_html=None, error=f"CSV Error: {ve}",
                route_info=None, carbon_data=None, time_window_status=None,
                csv_import_info=None,
            )
    else:
        addrs      = [a.strip() for a in request.form.getlist("address") if a.strip()]
        item_types = request.form.getlist("item_type")

    if not curr_addr or not addrs:
        error = "Please provide both a start location and at least one delivery address."
        return render_template(
            "index.html",
            optimized_addresses=[], map_html=None, error=error,
            route_info=None, carbon_data=None, time_window_status=None,
            csv_import_info=csv_import_info,
        )

    # ── Geocoding ──────────────────────────────────────────────────────────
    all_addrs = [curr_addr] + addrs
    all_types = ["current"] + item_types[: len(addrs)]

    for i, addr in enumerate(all_addrs):
        focus_point = coords[0] if (i > 0 and coords) else None
        result      = geocode_address_cached(addr, focus=focus_point)  # [F6]

        if result is None:
            label = "Start location" if i == 0 else f"Delivery #{i}"
            geocode_errors.append(
                f'Could not locate "{addr}" ({label}). '
                "Check spelling or use a more specific address."
            )
            logger.warning("[Geocode] Failed for '%s'", addr)
            continue

        coords.append(result["coordinates"])
        items.append({"address": result["label"], "type": all_types[i]})

    if len(coords) == 0:
        error = "No locations could be geocoded. " + " | ".join(geocode_errors)
        return render_template(
            "index.html",
            optimized_addresses=[], map_html=None, error=error,
            route_info=None, carbon_data=None, time_window_status=None,
            csv_import_info=csv_import_info,
        )

    if len(coords) == 1:
        error = (
            "No valid delivery locations found after geocoding. "
            + ("; ".join(geocode_errors) or "All delivery addresses failed.")
        )
        return render_template(
            "index.html",
            optimized_addresses=[], map_html=None, error=error,
            route_info=None, carbon_data=None, time_window_status=None,
            csv_import_info=csv_import_info,
        )

    # ── Distance Matrix ────────────────────────────────────────────────────
    try:
        coords, items, dists = get_distance_matrix(  # [F5] cached + haversine fallback
            client, coords, items, geocode_errors
        )
    except Exception as exc:
        logger.error("[DistMatrix] Fatal: %s", exc)
        return render_template(
            "index.html",
            optimized_addresses=[], map_html=None,
            error=f"Distance Matrix Error: {exc}",
            route_info=None, carbon_data=None, time_window_status=None,
            csv_import_info=csv_import_info,
        )

    partial_warning = (
        "Some stops skipped (unroutable or not found): " + "; ".join(geocode_errors)
    ) if geocode_errors else None

    try:
        routes              = []
        cluster_algo_used   = "N/A"
        cluster_warning     = None   # [F3] DBSCAN fallback message

        # ── Route Generation ───────────────────────────────────────────────
        if num_vehicles == 1:
            idx    = optimize_delivery_route_advanced(coords, items, dists)
            idx   += [0]
            routes.append(idx)

        else:
            clusters, cluster_algo_used, cluster_warning = smart_cluster(  # [F2][F3][F4]
                coords, num_vehicles, method=cluster_method, items=items
            )
            logger.info("[Clustering] Algorithm: %s", cluster_algo_used)

            for vehicle_id, cluster_indices in clusters.items():
                if not cluster_indices:
                    continue

                sub_coords = [coords[0]] + [coords[i] for i in cluster_indices]
                sub_items  = [items[0]]  + [items[i]  for i in cluster_indices]

                # Use haversine for sub-matrix if above threshold [F5]
                if len(sub_coords) > HAVERSINE_FALLBACK_THRESHOLD:
                    sub_matrix = build_haversine_matrix(sub_coords)
                else:
                    try:
                        sub_matrix = client.distance_matrix(
                            locations=sub_coords, profile="driving-car",
                            metrics=["distance"], units="km",
                        )["distances"]
                    except Exception as exc:
                        logger.warning("[SubMatrix] ORS failed, using haversine: %s", exc)
                        sub_matrix = build_haversine_matrix(sub_coords)

                sub_route    = optimize_delivery_route_advanced(sub_coords, sub_items, sub_matrix)
                mapped_route = (
                    [0]
                    + [cluster_indices[i - 1] for i in sub_route[1:]]
                    + [0]
                )
                routes.append(mapped_route)

            # ── [F1] Cross-Cluster Swap Optimization ───────────────────────
            if len(routes) > 1:
                pre_cross  = sum(calculate_route_distance(r, dists) for r in routes)
                routes     = improve_cross_cluster(routes, coords, dists)
                post_cross = sum(calculate_route_distance(r, dists) for r in routes)
                logger.info(
                    "[F1] Cross-cluster improved: %.2f → %.2f km (saved %.2f km)",
                    pre_cross, post_cross, pre_cross - post_cross,
                )

        # ── Distances & Savings ────────────────────────────────────────────
        vehicle_distances   = []
        total_distance      = 0.0

        for route in routes:
            rd = calculate_route_distance(route, dists)
            vehicle_distances.append(round(rd, 2))
            total_distance += rd

        # Naive baseline — uses nearest_neighbor_WITH_PRIORITY (not basic NN).
        #
        # Root cause of naive < optimized bug:
        #   nearest_neighbor_BASIC picks the shortest pure-distance route,
        #   delivering perishables last. Optimized brute-force picks a route that
        #   delivers perishables first — which can be slightly longer in raw distance
        #   but scores better. Result: naive (35.48 km) < optimized (36.38 km) → wrong.
        #
        # Fix: naive uses nearest_neighbor_WITH_PRIORITY (greedy, no brute-force,
        # no 2-opt). Optimized is always strictly better than greedy priority-NN:
        #   ≤8 stops → brute-force exhausts all permutations → always ≤ greedy priority-NN
        #   >8 stops → greedy priority-NN + 2-opt → always ≤ greedy priority-NN alone
        # This mathematically guarantees naive_distance ≥ total_distance always.
        naive_distance = 0.0
        if num_vehicles == 1:
            naive_route    = nearest_neighbor_with_priority(coords, items, dists) + [0]
            naive_distance = calculate_route_distance(naive_route, dists)
        else:
            # Re-use same clusters already computed — same clusters, ORS sub-matrix
            for vehicle_id, cluster_indices in clusters.items():
                if not cluster_indices:
                    continue
                global_indices = [0] + list(cluster_indices)
                n_sub = len(global_indices)
                sub_mat = [
                    [dists[global_indices[r]][global_indices[c]] for c in range(n_sub)]
                    for r in range(n_sub)
                ]
                sub_coords_n = [coords[g] for g in global_indices]
                sub_items_n  = [items[g]  for g in global_indices]
                sub_naive    = nearest_neighbor_with_priority(
                    sub_coords_n, sub_items_n, sub_mat) + [0]
                naive_distance += calculate_route_distance(sub_naive, sub_mat)

        distance_saved = round(naive_distance - total_distance, 2)
        percent_saved  = (
            round((distance_saved / naive_distance) * 100, 1)
            if naive_distance > 0 else 0
        )

        # ── [F7] Dynamic Re-Routing Simulation (first vehicle) ────────────
        rerouting_sim = None
        if routes:
            try:
                rerouting_sim = simulate_dynamic_rerouting(
                    routes[0], coords, items, dists
                )
                logger.info(
                    "[F7] Simulation: %d delays, %d reroutes, est. %.0f min",
                    len(rerouting_sim["delay_events"]),
                    rerouting_sim["reroutes_triggered"],
                    rerouting_sim["estimated_time_min"],
                )
            except Exception as exc:
                logger.warning("[F7] Simulation skipped: %s", exc)

        route_info = {
            "total_distance":    round(total_distance, 2),
            "total_stops":       len(coords) - 1,
            "num_vehicles":      num_vehicles,
            "naive_distance":    round(naive_distance, 2),
            "distance_saved":    distance_saved,
            "percent_saved":     percent_saved,
            "vehicle_distances": vehicle_distances,
            "cluster_algorithm": cluster_algo_used,
            "geocode_warning":   partial_warning,
            "cluster_warning":   cluster_warning,          # [F3] DBSCAN fallback msg
            "rerouting_sim":     rerouting_sim,            # [F7] simulation results
        }

        # ── Map Construction ───────────────────────────────────────────────
        fmap        = folium.Map(location=[coords[0][1], coords[0][0]], zoom_start=11)
        colors_list = ["blue", "green", "purple", "orange", "red"]
        color_names = ["Blue",  "Green", "Purple", "Orange", "Red"]

        # Each vehicle gets its own named FeatureGroup so LayerControl shows
        # "🚚 Vehicle 1 Route" etc. instead of auto-generated macro_element_* IDs.
        # All GeoJson / PolyLine / Marker objects go INTO the group, never
        # directly onto `fmap`.
        for v_idx, route in enumerate(routes):
            opt_coords  = [coords[i] for i in route]
            v_color     = colors_list[v_idx % len(colors_list)]
            v_color_name = color_names[v_idx % len(color_names)]

            vehicle_group = folium.FeatureGroup(
                name=f"🚚 Vehicle {v_idx + 1} Route ({v_color_name})",
                show=True,
            )

            # Markers (exclude return-to-depot leg)
            for pos, (ln, lt) in enumerate(opt_coords[:-1]):
                marker_color = "darkgreen" if pos == 0 else v_color
                stop_label   = "Depot" if pos == 0 else f"Stop {pos}"
                folium.Marker(
                    [lt, ln],
                    popup=f"Vehicle {v_idx + 1} — {stop_label}",
                    icon=folium.Icon(color=marker_color),
                ).add_to(vehicle_group)

            # Polyline — drawn into vehicle_group, not fmap
            draw_route_polyline(client, opt_coords, v_color, vehicle_group)

            vehicle_group.add_to(fmap)

        # Heatmap layer (off by default)
        add_heatmap_layer(fmap, coords)

        # Layer toggle — only shows clean vehicle names + heatmap
        folium.LayerControl(collapsed=False).add_to(fmap)

        map_html = fmap._repr_html_()

        # ── Build optimized_addresses list ────────────────────────────────
        # route format: [0, a, b, ..., 0]
        # route[:-1] strips the trailing 0 (return-to-depot) so the depot
        # is listed exactly once (as the START) and never again as a phantom stop.
        optimized_addresses = []
        for v_idx, route in enumerate(routes):
            for pos, i in enumerate(route[:-1]):   # ← the fix: exclude return leg
                optimized_addresses.append({
                    "address":    items[i]["address"],
                    "type":       items[i]["type"],
                    "vehicle":    v_idx + 1,
                    "is_current": pos == 0,
                })

        carbon_data = calculate_carbon_metrics(route_info["total_distance"])

        _last_route_result.clear()
        _last_route_result.update({
            "optimized_addresses": optimized_addresses,
            "route_info":          route_info,
            "carbon_data":         carbon_data,
        })

    except Exception as exc:
        logger.exception("[Route] Unhandled error during optimisation")
        error = f"Routing Error: {exc}"

    return render_template(
        "index.html",
        optimized_addresses=optimized_addresses,
        map_html=map_html,
        error=error,
        route_info=route_info,
        carbon_data=carbon_data,
        time_window_status=time_window_status,
        csv_import_info=csv_import_info,
    )


# ============================================================
# PDF Export Route — unchanged logic
# ============================================================
@app.route("/export_pdf")
def export_pdf():
    if not _last_route_result:
        return (
            "No route available for export. "
            "Please optimise a route first, then click Export PDF.",
            400,
        )
    try:
        pdf_buffer = generate_route_pdf(_last_route_result)
        filename   = f"route_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        logger.exception("[PDF] Generation failed")
        return f"PDF Generation Error: {exc}", 500


if __name__ == "__main__":
    app.run(debug=True, port=8000)