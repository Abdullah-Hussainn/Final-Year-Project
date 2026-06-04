"""
Backend demo pipeline for the ACFRL AI-driven chip floorplanning FYP.

This is the FIRST working milestone of a headless pipeline that reproduces the
core flow currently living in FYP.ipynb, without needing to open Jupyter:

    1. Parse the Verilog netlist        -> reuses netlist_parser.build_netlist_graph
                                           + netlist_parser.extract_netlist
    2. Obtain a macro placement         -> see _load_placement() below
    3. Compute metrics (HPWL / congestion / thermal) -> backend/pipeline/metrics.py
    4. Export DEF + LEF                 -> reuses netlist_parser.write_def / write_lef
    5. Render a placement image (PNG)   -> backend/pipeline/visualizer.py

------------------------------------------------------------------------------
PPO INTEGRATION NOTE (milestone scope):
    For this first version we DO NOT run live PPO inference. Instead we load the
    placement that the notebook already produced and saved into
    `placement_results.json` (the thermal-PPO / PPO / greedy result).

    TODO (next milestone): replace `_load_placement()` with live inference using
    sb3_contrib.MaskablePPO + the PlacementEnv defined in FYP.ipynb, e.g.:

        from sb3_contrib import MaskablePPO
        model = MaskablePPO.load("models/thermal_ppo_placement.zip")
        env = PlacementEnv(instances, nets, sizes, G, H, W)
        obs, info = env.reset()
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True,
                                      action_masks=info["action_mask"])
            obs, _, term, trunc, info = env.step(action)
            done = term or trunc
        placements = env.unwrapped.placements

    The structure below (instances/nets/sizes/grid already wired through) is
    ready to drop that in.
------------------------------------------------------------------------------
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# --- Make repo-root imports work regardless of where this is launched from ----
# backend/pipeline/full_pipeline.py -> parents[2] == repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Reuse the existing, already-working parser / DEF / LEF writers.
from netlist_parser import (  # noqa: E402
    build_netlist_graph,
    extract_netlist,
    write_def,
    write_lef,
)

from . import metrics as metrics_mod  # noqa: E402
from .visualizer import render_placement  # noqa: E402

# --- Defaults (match the notebook sample design) ------------------------------
DEFAULT_VERILOG = ["chip_top.v", "blocks.v"]
DEFAULT_TOP = "chip_top"
DEFAULT_PLACEMENT_RESULTS = "placement_results.json"

# DEF/LEF scale: notebook uses UNITS MICRONS 100 with 50 microns per grid cell.
DBU_PER_MICRON = 100
GRID_CELL_MICRONS = 50
DEF_SCALE = DBU_PER_MICRON * GRID_CELL_MICRONS  # 5000 DBU per grid cell

# Preferred placement keys in placement_results.json, best -> fallback.
# (Live PPO inference will eventually supersede all of these.)
PLACEMENT_PRIORITY = [
    ("placements_thermal_ppo", "thermal_ppo"),
    ("placements_ppo", "ppo"),
    ("placements_greedy", "greedy"),
    ("placements_greedy_spaced", "greedy"),
    ("placements_random", "random"),
]


def _resolve(path: str | Path) -> Path:
    """Resolve a path relative to the repo root unless already absolute."""
    p = Path(path)
    return p if p.is_absolute() else (REPO_ROOT / p)


def _parse_netlist(verilog_files: List[str], top_module: str):
    """
    Parse the Verilog netlist using the existing parser. Returns
    (instances_list, nets_dict). instances_list is [{"name","type"}, ...] and
    nets_dict is {net_name: [{"inst","pin"}, ...]}.
    """
    abs_files = [str(_resolve(f)) for f in verilog_files]
    # PyVerilog writes temp files into CWD; build_netlist_graph already cleans
    # them up. Running from the repo root keeps that behavior unchanged.
    G, top = build_netlist_graph(abs_files, top=top_module)
    instances_list, nets_dict = extract_netlist(G, top)
    return instances_list, nets_dict


def _load_placement(results: dict) -> tuple[Dict[str, list], str]:
    """
    Select the best available saved placement from placement_results.json.

    MILESTONE BEHAVIOR: returns a precomputed placement (thermal-PPO preferred).
    TODO: swap for live PPO inference (see module docstring).
    """
    for key, label in PLACEMENT_PRIORITY:
        plc = results.get(key)
        if plc:
            # Normalize coords to plain ints.
            return {name: [int(v) for v in box] for name, box in plc.items()}, label
    raise ValueError(
        "No usable placement found in placement_results.json "
        f"(looked for keys: {[k for k, _ in PLACEMENT_PRIORITY]})."
    )


def run_pipeline(
    verilog_files: Optional[List[str]] = None,
    top_module: str = DEFAULT_TOP,
    placement_results_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    design_name: str = "chip_top",
) -> dict:
    """
    Run the full demo pipeline and write placement.png, placement.def, and
    metrics.json into output_dir.

    Returns a summary dict with the chosen placement label, metrics, and the
    absolute paths of the generated artifacts.
    """
    verilog_files = verilog_files or DEFAULT_VERILOG
    placement_results_path = _resolve(placement_results_path or DEFAULT_PLACEMENT_RESULTS)
    output_dir = Path(output_dir) if output_dir else (Path(__file__).resolve().parents[1] / "outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1) Parse the netlist (reuse existing parser). Fall back to the netlist
    #    saved in placement_results.json if parsing is unavailable.
    if not placement_results_path.exists():
        raise FileNotFoundError(
            f"placement_results.json not found at {placement_results_path}. "
            "Run the notebook's save cell (or PPO eval) first to produce it."
        )
    with open(placement_results_path, "r") as f:
        results = json.load(f)

    try:
        instances_list, nets_dict = _parse_netlist(verilog_files, top_module)
        netlist_source = "verilog_parse"
    except Exception as exc:  # noqa: BLE001 - first milestone: degrade gracefully
        print(f"[pipeline] WARNING: Verilog parse failed ({exc}); "
              f"falling back to netlist in placement_results.json")
        instances_list = results["instances"]
        nets_dict = results["nets"]
        netlist_source = "placement_results_json"

    instance_type_map = {i["name"]: i["type"] for i in instances_list}

    # 2) Obtain placement (saved PPO output for this milestone).
    placements, method_label = _load_placement(results)

    # Grid + power table come from the saved results.
    H = int(results["grid"]["H"])
    W = int(results["grid"]["W"])
    power_table = results.get("power_table") or metrics_mod.DEFAULT_POWER_TABLE

    # 3) Compute metrics.
    metric_bundle = metrics_mod.evaluate_placement(
        placements, nets_dict, instance_type_map, H, W, power_table
    )

    # 4) Export DEF + LEF (reuse existing writers).
    lef_path = output_dir / "macros.lef"
    def_path = output_dir / "placement.def"
    write_lef(str(lef_path), dbu_per_micron=DBU_PER_MICRON)
    write_def(str(def_path), design_name, H, W, DEF_SCALE, instances_list, placements, nets_dict)

    # 5) Render placement image.
    png_path = output_dir / "placement.png"
    render_placement(
        placements, instance_type_map, H, W, png_path,
        title=f"Placement ({method_label})", metrics=metric_bundle,
    )

    # Write metrics.json (self-describing for the future API layer).
    metrics_path = output_dir / "metrics.json"
    metrics_payload = {
        "design": design_name,
        "top_module": top_module,
        "netlist_source": netlist_source,
        "placement_method": method_label,
        "live_ppo_inference": False,  # TODO: flip to True once PPO is wired in
        "grid": {"H": H, "W": W},
        "metrics": metric_bundle,
        "placements": placements,
    }
    with open(metrics_path, "w") as f:
        json.dump(metrics_payload, f, indent=2)

    return {
        "design": design_name,
        "top_module": top_module,
        "placement_method": method_label,
        "netlist_source": netlist_source,
        "live_ppo_inference": False,  # TODO: flip to True once PPO is wired in
        "netlist": {
            "instances": len(instances_list),
            "nets": len(nets_dict),
        },
        "metrics": metric_bundle,
        "outputs": {
            "png": str(png_path),
            "def": str(def_path),
            "lef": str(lef_path),
            "metrics_json": str(metrics_path),
        },
    }


if __name__ == "__main__":
    summary = run_pipeline()
    print(json.dumps(summary, indent=2))
