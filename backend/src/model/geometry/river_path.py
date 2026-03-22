"""Charles River centerline segments from curated GeoJSON (WGS84)."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.model.geometry.densify import densify_path, parse_densify_steps_from_env
from src.paths import BACKEND_ROOT

GEOJSON_PATH = BACKEND_ROOT / "data" / "charles_river_rowing.geojson"


def _geo_signature(path: Path) -> tuple[float, int]:
    """mtime + size so cache invalidates when the GeoJSON file is replaced or edited."""
    st = path.stat()
    return (st.st_mtime, st.st_size)


@dataclass(frozen=True)
class RiverSegment:
    index: int
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    mid_lat: float
    mid_lng: float
    length_m: float
    """Heading of downstream direction along polyline (deg from N, clockwise)."""
    heading_downstream_deg: float


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _segment_heading_geographic(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing from p1 to p2, degrees from north clockwise; longitude scaled by cos(mean lat)."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = lat2_r - lat1_r
    dlng = math.radians(lon2 - lon1)
    x = dlng * math.cos((lat1_r + lat2_r) / 2)
    y = dlat
    deg = math.degrees(math.atan2(x, y))
    return (deg + 360.0) % 360.0


def parse_heading_smooth_window_from_env() -> int:
    """Vertices on each side to include when smoothing segment axis (default 4). 0 = per-leg heading only."""
    raw = os.environ.get("RIVER_HEADING_SMOOTH_WINDOW", "10").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 4


def _smoothed_heading_for_segment(
    coords: list[list[float]],
    seg_index: int,
    window: int,
) -> float:
    """Heading along polyline at segment seg_index, using a chord from vertex i-window to i+window."""
    n = len(coords)
    if n < 2:
        return 0.0
    lon1, lat1 = coords[seg_index][0], coords[seg_index][1]
    lon2, lat2 = coords[seg_index + 1][0], coords[seg_index + 1][1]
    if window <= 0:
        return _segment_heading_geographic(lat1, lon1, lat2, lon2)
    a = max(0, seg_index - window)
    b = min(n - 1, seg_index + window)
    la, loa = coords[a][1], coords[a][0]
    lb, lob = coords[b][1], coords[b][0]
    return _segment_heading_geographic(la, loa, lb, lob)


def _boat_axis_heading(segment: RiverSegment, direction: str) -> float:
    if direction == "downstream":
        return segment.heading_downstream_deg
    return (segment.heading_downstream_deg + 180.0) % 360.0


@lru_cache(maxsize=64)
def _load_river_segments_cached(
    signature: tuple[float, int], steps: int, smooth_window: int
) -> tuple[RiverSegment, ...]:
    path = GEOJSON_PATH
    if not path.is_file():
        raise FileNotFoundError(f"River GeoJSON not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    geom = raw.get("geometry") or raw
    raw_coords: list[Any] = geom.get("coordinates") or []
    if len(raw_coords) < 2:
        raise ValueError("LineString needs at least 2 coordinates")

    # lng, lat pairs as floats
    sparse: list[list[float]] = [
        [float(raw_coords[i][0]), float(raw_coords[i][1])] for i in range(len(raw_coords))
    ]
    coords = densify_path(sparse, steps)
    if len(coords) < 2:
        raise ValueError("Densified path needs at least 2 coordinates")

    segments: list[RiverSegment] = []
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i][0], coords[i][1]
        lon2, lat2 = coords[i + 1][0], coords[i + 1][1]
        h = _smoothed_heading_for_segment(coords, i, smooth_window)
        length_m = _haversine_m(lat1, lon1, lat2, lon2)
        segments.append(
            RiverSegment(
                index=i,
                start_lat=lat1,
                start_lng=lon1,
                end_lat=lat2,
                end_lng=lon2,
                mid_lat=(lat1 + lat2) / 2,
                mid_lng=(lon1 + lon2) / 2,
                length_m=max(length_m, 1.0),
                heading_downstream_deg=h,
            )
        )
    return tuple(segments)


def load_river_segments() -> tuple[RiverSegment, ...]:
    path = GEOJSON_PATH
    if not path.is_file():
        raise FileNotFoundError(f"River GeoJSON not found: {path}")
    steps = parse_densify_steps_from_env()
    smooth = parse_heading_smooth_window_from_env()
    return _load_river_segments_cached(_geo_signature(path), steps, smooth)


def boat_axis_heading_for_segment(segment: RiverSegment, direction: str) -> float:
    return _boat_axis_heading(segment, direction)
