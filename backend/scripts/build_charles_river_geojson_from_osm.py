#!/usr/bin/env python3
"""
Merge OSM Charles River way fragments into one LineString (Watertown → Longfellow).

Reads Overpass JSON from:
  backend/data/osm_charles_overpass.json

Refresh that file with:
  curl -sS -X POST https://overpass-api.de/api/interpreter \\
    --data-binary @scripts/overpass_charles_river.txt \\
    -o data/osm_charles_overpass.json

ODbL: © OpenStreetMap contributors.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = BACKEND_ROOT / "data" / "osm_charles_overpass.json"
OUT_PATH = BACKEND_ROOT / "data" / "charles_river_rowing.geojson"

REF_UPSTREAM = (-71.1845, 42.3678)
REF_DOWNSTREAM = (-71.0585, 42.3690)


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def way_to_coords(el: dict) -> list[list[float]]:
    geom = el.get("geometry") or []
    return [[float(p["lon"]), float(p["lat"])] for p in geom]


def dedupe_coords(coords: list[list[float]], eps: float = 1e-7) -> list[list[float]]:
    out: list[list[float]] = []
    for c in coords:
        if not out or abs(out[-1][0] - c[0]) > eps or abs(out[-1][1] - c[1]) > eps:
            out.append(c)
    return out


def orient_toward_upstream(seg: list[list[float]]) -> list[list[float]]:
    d0 = haversine_m(seg[0][0], seg[0][1], REF_UPSTREAM[0], REF_UPSTREAM[1])
    d1 = haversine_m(seg[-1][0], seg[-1][1], REF_UPSTREAM[0], REF_UPSTREAM[1])
    return seg if d0 <= d1 else seg[::-1]


def chain_segments(segments: list[list[list[float]]], max_join_m: float = 120.0) -> list[list[float]]:
    """Starting near Watertown, repeatedly append the best-matching remaining segment."""
    if not segments:
        return []
    segs = [dedupe_coords(s) for s in segments if len(s) >= 2]
    if not segs:
        return []

    # Start with segment whose start OR end is closest to upstream ref (then orient so near end is first)
    best_i = 0
    best_d = 1e18
    for i, s in enumerate(segs):
        d = min(
            haversine_m(s[0][0], s[0][1], REF_UPSTREAM[0], REF_UPSTREAM[1]),
            haversine_m(s[-1][0], s[-1][1], REF_UPSTREAM[0], REF_UPSTREAM[1]),
        )
        if d < best_d:
            best_d, best_i = d, i

    chain = orient_toward_upstream(segs.pop(best_i))
    # Ensure first vertex is the one closer to upstream
    chain = orient_toward_upstream(chain)

    while segs:
        best_j = -1
        best_orient: list[list[float]] | None = None
        best_d = max_join_m + 1
        for j, s in enumerate(segs):
            for cand in (s, s[::-1]):
                d = haversine_m(chain[-1][0], chain[-1][1], cand[0][0], cand[0][1])
                if d < best_d:
                    best_d = d
                    best_j = j
                    best_orient = cand
        if best_j < 0 or best_orient is None or best_d > max_join_m:
            break
        chain.extend(best_orient[1:])
        segs.pop(best_j)

    if segs:
        # Second pass: prepend segments that connect to chain[0]
        while segs:
            best_j = -1
            best_orient = None
            best_d = max_join_m + 1
            for j, s in enumerate(segs):
                for cand in (s, s[::-1]):
                    d = haversine_m(chain[0][0], chain[0][1], cand[-1][0], cand[-1][1])
                    if d < best_d:
                        best_d = d
                        best_j = j
                        best_orient = cand
            if best_j < 0 or best_orient is None or best_d > max_join_m:
                break
            chain = best_orient[:-1] + chain
            segs.pop(best_j)

    return dedupe_coords(chain)


def nearest_index(coords: list[list[float]], lon: float, lat: float) -> int:
    best_i, best_d = 0, 1e18
    for i, (lo, la) in enumerate(coords):
        d = haversine_m(lo, la, lon, lat)
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def trim_reach(coords: list[list[float]]) -> list[list[float]]:
    iu = nearest_index(coords, REF_UPSTREAM[0], REF_UPSTREAM[1])
    idn = nearest_index(coords, REF_DOWNSTREAM[0], REF_DOWNSTREAM[1])
    lo, hi = (iu, idn) if iu <= idn else (idn, iu)
    return coords[lo : hi + 1]


def orient_upstream_to_downstream(coords: list[list[float]]) -> list[list[float]]:
    if len(coords) < 2:
        return coords
    du = haversine_m(coords[0][0], coords[0][1], REF_UPSTREAM[0], REF_UPSTREAM[1])
    dd = haversine_m(coords[-1][0], coords[-1][1], REF_UPSTREAM[0], REF_UPSTREAM[1])
    if dd < du:
        return coords[::-1]
    return coords


def main() -> None:
    in_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    if not in_path.is_file():
        raise SystemExit(f"Missing {in_path}. Run curl per script docstring.")

    data = json.loads(in_path.read_text(encoding="utf-8"))
    elements = [e for e in data.get("elements", []) if e.get("type") == "way"]
    segments = [way_to_coords(e) for e in elements]
    segments = [s for s in segments if len(s) >= 2]

    if not segments:
        raise SystemExit("No ways in Overpass JSON.")

    merged = chain_segments(segments)
    merged = orient_upstream_to_downstream(merged)
    trimmed = trim_reach(merged)

    if len(trimmed) < 2:
        raise SystemExit(f"Trimmed polyline too short ({len(trimmed)} pts). merged_len={len(merged)}")

    landmarks_spec = [
        ("Watertown Dam", -71.1845, 42.3678),
        ("Eliot Bridge", -71.1256, 42.3696),
        ("Weeks Footbridge", -71.1105, 42.3668),
        ("BU Bridge", -71.0925, 42.3659),
        ("Mass Ave Bridge", -71.0745, 42.3658),
        ("Longfellow Bridge", -71.0585, 42.3690),
    ]
    landmarks = [
        {"name": name, "coord_index": nearest_index(trimmed, lon, lat)}
        for name, lon, lat in landmarks_spec
    ]

    feature = {
        "type": "Feature",
        "properties": {
            "name": "Charles River Rowing Stretch",
            "note": "Upstream (Watertown) → downstream (Longfellow), [lng, lat]. "
            "Centerline built from OpenStreetMap (waterway=river, ODbL); regenerate with "
            "scripts/build_charles_river_geojson_from_osm.py. Refine manually in geojson.io "
            "over satellite if needed. Runtime densification: RIVER_DENSIFY_STEPS.",
            "source": "OpenStreetMap contributors (ODbL)",
        },
        "geometry": {"type": "LineString", "coordinates": trimmed},
    }
    feature["properties"]["landmarks"] = landmarks

    OUT_PATH.write_text(json.dumps(feature, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH} with {len(trimmed)} vertices (from {len(segments)} OSM ways).")


if __name__ == "__main__":
    main()
