#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bio_containers import load_bio_schedule
from streets import all_streets, mistni_casti


STREET_ALIASES = {
    "Gemerská - rodinné domy": "Gemerská",
    "Gemerská - sídliště": "Gemerská",
    "Karla Sedláka - sídliště": "Karla Sedláka",
    "Nám. Př. Otakara": "náměstí Přemysla Otakara",
    "Novosady - rodinné domy": "Novosady",
    "Novosady - sídliště": "Novosady",
    "Severní - rodinné domy": "Severní",
    "Uničovská - sídliště": "Uničovská",
    "Vítězná - sídliště": "Vítězná",
    "nám. Svobody": "náměstí Svobody",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build geographically grounded provisional proximity coordinates from an Overpass JSON export."
    )
    parser.add_argument("input", type=Path, help="Overpass JSON file")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/proximity_coordinates.json",
    )
    args = parser.parse_args()

    elements = json.loads(args.input.read_text(encoding="utf-8"))["elements"]
    road_points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    place_points: dict[str, list[tuple[float, float]]] = defaultdict(list)

    for element in elements:
        tags = element.get("tags", {})
        name = tags.get("name")
        point = element_point(element)
        if not name or point is None:
            continue
        if tags.get("highway"):
            road_points[name].append(point)
        if tags.get("place"):
            place_points[name].append(point)

    streets = all_streets["Litovel"] + mistni_casti
    street_coordinates = {}
    unresolved_streets = []
    for street in streets:
        source_name = STREET_ALIASES.get(street, street)
        candidates = place_points.get(source_name) if street in mistni_casti else road_points.get(source_name)
        if not candidates:
            unresolved_streets.append(street)
            continue
        street_coordinates[street] = coordinate_record(average_point(candidates))

    schedule = load_bio_schedule()
    site_coordinates = {}
    unresolved_sites = []
    for site in schedule.sites:
        candidates = None
        if site.locality == "Litovel":
            source_name = site.name.removeprefix("ul. ")
            candidates = road_points.get(source_name)
        elif site.name == site.locality:
            candidates = place_points.get(site.locality)
        if not candidates:
            unresolved_sites.append(site.id)
            continue
        site_coordinates[site.id] = coordinate_record(average_point(candidates))

    output = {
        "version": 1,
        "source": {
            "name": "OpenStreetMap",
            "url": "https://www.openstreetmap.org/copyright",
            "license": "ODbL",
            "imported": date.today().isoformat(),
        },
        "street_coordinates": street_coordinates,
        "site_coordinates": site_coordinates,
    }
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(street_coordinates)} street and {len(site_coordinates)} site coordinates")
    if unresolved_streets:
        print("Unresolved streets: " + ", ".join(unresolved_streets))
    if unresolved_sites:
        print("Unresolved sites: " + ", ".join(unresolved_sites))
    return 0


def element_point(element) -> tuple[float, float] | None:
    latitude = element.get("lat", element.get("center", {}).get("lat"))
    longitude = element.get("lon", element.get("center", {}).get("lon"))
    if latitude is None or longitude is None:
        return None
    return float(latitude), float(longitude)


def average_point(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def coordinate_record(point: tuple[float, float]) -> dict:
    return {
        "latitude": round(point[0], 7),
        "longitude": round(point[1], 7),
        "accuracy": "provisional",
    }


if __name__ == "__main__":
    raise SystemExit(main())
