"""
Placement metrics for the backend demo pipeline.

These functions are a minimal, self-contained port of the metric logic in
FYP.ipynb (HPWL, congestion proxy, and a simplified thermal score). They work
directly off the netlist representation produced by netlist_parser.extract_netlist:

    placements : dict  inst_name -> [y, x, h, w]   (grid coordinates)
    nets       : dict  net_name  -> [ {"inst": str, "pin": str}, ... ]
    instances  : dict  inst_name -> macro_type     (e.g. "simple_rom")

Unlike the notebook versions they do NOT require a live NetworkX graph, so the
pipeline can run from saved JSON without rebuilding the graph object.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np

# Default power table (Watts-ish, relative) mirrored from FYP.ipynb.
DEFAULT_POWER_TABLE = {
    "simple_rom": 1.2,
    "simple_alu": 1.8,
}

# Thermal model constants (kept in sync with the notebook defaults).
WIRE_HEAT_WEIGHT = 0.5
PROXIMITY_WEIGHT = 3.0
HOTSPOT_WEIGHT = 1.5
FALLOFF_EXP = 1.5
THERMAL_SAFE_DISTANCE = 8.0


def rect_center(y: float, x: float, h: float, w: float) -> Tuple[float, float]:
    """Return (center_y, center_x) for a [y, x, h, w] box."""
    return (y + h / 2.0, x + w / 2.0)


def _net_points(plc: Dict[str, list], pins: List[dict]) -> List[Tuple[float, float]]:
    """Collect placed pin centers for a single net."""
    pts = []
    for p in pins:
        if isinstance(p, dict) and p.get("inst") in plc:
            y, x, h, w = plc[p["inst"]]
            pts.append(rect_center(y, x, h, w))
    return pts


def hpwl_from_placements_and_nets(plc: Dict[str, list], nets: Dict[str, list]) -> float:
    """
    Half-Perimeter Wire Length summed over all multi-pin nets.
    Direct port of hpwl_from_placements_and_nets() in FYP.ipynb.
    """
    total = 0.0
    for pins in nets.values():
        pts = _net_points(plc, pins)
        if len(pts) >= 2:
            ys = [p[0] for p in pts]
            xs = [p[1] for p in pts]
            total += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return total


def compute_congestion(plc: Dict[str, list], H: int, W: int, nets: Dict[str, list]) -> np.ndarray:
    """
    Simple L-route congestion proxy: for each multi-pin net, lay an L-shaped wire
    between the first pin and every other pin and accumulate per-cell crossings.
    Adapted from compute_congestion() in FYP.ipynb (graph replaced by nets dict).
    """
    cong = np.zeros((H, W), dtype=np.int32)
    for pins in nets.values():
        pts = []
        for p in pins:
            if isinstance(p, dict) and p.get("inst") in plc:
                y, x, h, w = plc[p["inst"]]
                pts.append((int(round(y + h / 2.0)), int(round(x + w / 2.0))))
        if len(pts) < 2:
            continue
        y0, x0 = pts[0]
        for (y1, x1) in pts[1:]:
            xlo, xhi = sorted((x0, x1))
            ylo, yhi = sorted((y0, y1))
            cong[y0, xlo:xhi + 1] += 1
            cong[ylo:yhi + 1, x1] += 1
    return cong.astype(float)


def congestion_score(cong_map: np.ndarray) -> float:
    """Mean of the top 10% most congested cells (port of congestion_score())."""
    flat = np.asarray(cong_map, dtype=float).flatten()
    if flat.size == 0:
        return 0.0
    k = max(1, int(0.10 * flat.size))
    return float(np.mean(np.sort(flat)[-k:]))


def compute_thermal_score(
    placements: Dict[str, list],
    instance_type_map: Dict[str, str],
    H: int,
    W: int,
    congestion_map: np.ndarray | None = None,
    power_table: Dict[str, float] | None = None,
) -> Tuple[float, np.ndarray]:
    """
    Simplified thermal score + heat map, ported from compute_thermal_score() in
    FYP.ipynb. Combines a hotspot term (top-10% of a power falloff field) with a
    pairwise proximity penalty between high-power macros.
    """
    power_table = power_table or DEFAULT_POWER_TABLE
    thermal_map = np.zeros((H, W), dtype=float)
    yy, xx = np.indices((H, W))

    for inst_name, box in placements.items():
        y, x, h, w = box
        cy, cx = y + h / 2.0, x + w / 2.0
        power = float(power_table.get(instance_type_map.get(inst_name, ""), 1.0))
        dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
        thermal_map += power / ((dist + 1.0) ** FALLOFF_EXP)

    if congestion_map is not None:
        thermal_map += WIRE_HEAT_WEIGHT * np.asarray(congestion_map, dtype=float)

    flat = thermal_map.flatten()
    k = max(1, int(np.ceil(0.10 * flat.size)))
    thermal_hotspot = float(np.mean(np.sort(flat)[-k:]))

    proximity_penalty = 0.0
    rows = list(placements.items())
    for i, (name_a, box_a) in enumerate(rows):
        y_a, x_a, h_a, w_a = box_a
        cy_a, cx_a = y_a + h_a / 2.0, x_a + w_a / 2.0
        power_a = float(power_table.get(instance_type_map.get(name_a, ""), 1.0))
        for name_b, box_b in rows[i + 1:]:
            y_b, x_b, h_b, w_b = box_b
            cy_b, cx_b = y_b + h_b / 2.0, x_b + w_b / 2.0
            power_b = float(power_table.get(instance_type_map.get(name_b, ""), 1.0))
            dist = math.sqrt((cy_a - cy_b) ** 2 + (cx_a - cx_b) ** 2)
            pair_penalty = (power_a * power_b) / (dist + 1.0)
            if dist < THERMAL_SAFE_DISTANCE:
                pair_penalty += ((THERMAL_SAFE_DISTANCE - dist) / THERMAL_SAFE_DISTANCE) * power_a * power_b
            proximity_penalty += pair_penalty

    thermal_score = float(HOTSPOT_WEIGHT * thermal_hotspot + PROXIMITY_WEIGHT * proximity_penalty)
    return thermal_score, thermal_map


def evaluate_placement(
    placements: Dict[str, list],
    nets: Dict[str, list],
    instance_type_map: Dict[str, str],
    H: int,
    W: int,
    power_table: Dict[str, float] | None = None,
) -> dict:
    """
    Compute the full metric bundle for a placement. Returns a JSON-serializable
    dict (no numpy arrays) suitable for writing to metrics.json.
    """
    hpwl = hpwl_from_placements_and_nets(placements, nets)
    cong_map = compute_congestion(placements, H, W, nets)
    cong_value = congestion_score(cong_map)
    thermal_value, _thermal_map = compute_thermal_score(
        placements, instance_type_map, H, W, cong_map, power_table
    )
    multi_pin_nets = sum(
        1 for pins in nets.values() if len(_net_points(placements, pins)) >= 2
    )
    return {
        "hpwl": round(float(hpwl), 4),
        "congestion_top10": round(float(cong_value), 6),
        "thermal_score": round(float(thermal_value), 6),
        "num_components": len(placements),
        "num_multi_pin_nets": int(multi_pin_nets),
    }
