"""Write densified river GeoJSON for visual QA (QGIS, geojson.io).

Run from the backend package root::

    cd backend && python -m src.model.geometry.export_densified_geojson
"""

from __future__ import annotations

import json
import os
import sys

from src.model.geometry.densify import densify_path, parse_densify_steps_from_env
from src.model.geometry.river_path import GEOJSON_PATH


def main() -> None:
    path = GEOJSON_PATH
    if not path.is_file():
        raise SystemExit(f"Missing {path}")

    steps = parse_densify_steps_from_env()
    raw = json.loads(path.read_text(encoding="utf-8"))
    geom = raw.get("geometry") or raw
    coords = geom.get("coordinates") or []
    sparse = [[float(c[0]), float(c[1])] for c in coords]
    dense = densify_path(sparse, steps)

    out = {
        "type": "Feature",
        "properties": {
            **(raw.get("properties") or {}),
            "densify_steps": steps,
            "source": str(path.name),
            "vertex_count": len(dense),
        },
        "geometry": {"type": "LineString", "coordinates": dense},
    }
    out_path = path.with_name(path.stem + "_densified.geojson")
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(dense)} vertices, RIVER_DENSIFY_STEPS={steps})")


if __name__ == "__main__":
    # Allow override for one-off export without changing shell env
    if len(sys.argv) > 1:
        os.environ["RIVER_DENSIFY_STEPS"] = sys.argv[1]
    main()
