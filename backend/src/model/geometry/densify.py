"""Linear densification of GeoJSON LineString coordinates for smoother headings and map display."""

from __future__ import annotations


def interpolate_points(
    p1: list[float] | tuple[float, ...],
    p2: list[float] | tuple[float, ...],
    steps: int,
) -> list[list[float]]:
    """Points along the segment from p1 to p2 (exclusive of p2), `steps` samples per spec."""
    points: list[list[float]] = []
    for i in range(steps):
        t = i / steps
        lng = p1[0] + (p2[0] - p1[0]) * t
        lat = p1[1] + (p2[1] - p1[1]) * t
        points.append([lng, lat])
    return points


def densify_path(coords: list[list[float]], steps: int) -> list[list[float]]:
    """
    Insert intermediate vertices along each leg. `steps` subdivisions per leg (spec).
    If steps <= 1, return a shallow copy of `coords` (no densification).
    """
    if len(coords) < 2:
        return [list(c) for c in coords]
    if steps <= 1:
        return [list(c) for c in coords]

    new_coords: list[list[float]] = []
    for i in range(len(coords) - 1):
        new_coords.extend(interpolate_points(coords[i], coords[i + 1], steps))
    new_coords.append(coords[-1])
    return new_coords


def parse_densify_steps_from_env() -> int:
    """Default 5; 0 or 1 disables densification (use raw coords)."""
    import os

    raw = os.environ.get("RIVER_DENSIFY_STEPS", "5").strip()
    try:
        n = int(raw)
    except ValueError:
        return 5
    return max(0, n)
