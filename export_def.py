"""
Standalone DEF/LEF export from placement_results.json.
Requires: placement_results.json with grid, placements_ppo (or placements_greedy),
          instances (list of {name, type}), nets (dict net_name -> [{inst, pin}]).
Run inject_instances_nets.py first if instances/nets are missing.
"""
import json
import os
from netlist_parser import write_lef, write_def

with open("placement_results.json", "r") as f:
    data = json.load(f)

if "placements_ppo" in data:
    placements = data["placements_ppo"]
    label = "ppo"
else:
    placements = data["placements_greedy"]
    label = "greedy"

H, W = data["grid"]["H"], data["grid"]["W"]
scale = 5000
instances = data.get("instances")
nets = data.get("nets")
if not instances or not nets:
    raise SystemExit(
        "placement_results.json must contain 'instances' and 'nets'. "
        "Run inject_instances_nets.py or run the notebook save cell first."
    )

os.makedirs("out", exist_ok=True)
lef_path = "out/macros.lef"
write_lef(lef_path, dbu_per_micron=100)
def_path = f"out/placement_{label}.def"
write_def(def_path, "chip_top", H, W, scale, instances, placements, nets)
print("DEF:", def_path)
print("LEF:", lef_path)
