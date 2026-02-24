"""Patch FYP.ipynb for netlist/DEF/LEF pipeline consistency."""
import json

NOTEBOOK = "FYP.ipynb"

def main():
    with open(NOTEBOOK, "r", encoding="utf-8") as f:
        nb = json.load(f)
    cells = nb["cells"]

    # 1) Find "Use G or load JSON" cell and add extract_netlist
    for i, c in enumerate(cells):
        if c["cell_type"] != "code":
            continue
        src = "".join(c.get("source", []))
        if "G_src = G" in src and "instances = [n for n,d in G_src.nodes" in src and "Nets     :" in src:
            new_src = src.replace(
                'instances = [n for n,d in G_src.nodes(data=True) if d.get("type")=="instance"]\n'
                'nets      = [n for n,d in G_src.nodes(data=True) if d.get("type")=="net"]\n'
                'print("Instances:", instances)\n'
                'print("Nets     :", nets)',
                'from netlist_parser import extract_netlist\n'
                '_top = "chip_top"\n'
                'instances_list, nets_dict = extract_netlist(G_src, _top)\n'
                'if instances_list is None or nets_dict is None:\n'
                '    raise ValueError("extract_netlist returned None; run netlist build cell first.")\n'
                'instances = [x["name"] for x in instances_list]\n'
                'nets      = list(nets_dict.keys())\n'
                'print("Instances:", instances)\n'
                'print("Nets     :", nets)\n'
                'print("Multi-pin nets (>=2 instance pins):", [n for n, p in nets_dict.items() if len(p) >= 2])'
            )
            lines = new_src.rstrip("\n").split("\n")
            c["source"] = [line + "\n" for line in lines]
            print("Patched cell (Use G / extract_netlist) at index", i)
            break
    else:
        print("Could not find 'Use G' cell")

    # 2) Find first save placement_results.json and add instances + nets
    for i, c in enumerate(cells):
        if c["cell_type"] != "code":
            continue
        src = "".join(c.get("source", []))
        if '"placements_random"' in src and '"placements_greedy"' in src and "placement_results.json" in src and "json.dump(out," in src:
            if '"instances":' in src and '"nets":' in src:
                continue  # already has it
            # Add instances and nets to out (require instances_list, nets_dict from previous cell)
            src = src.replace(
                '"grid": {"H": H, "W": W},',
                '"grid": {"H": H, "W": W},\n    "instances": instances_list,\n    "nets": nets_dict,'
            )
            c["source"] = [line + "\n" for line in src.rstrip("\n").split("\n")]
            print("Patched save placement_results cell at index", i)
            break
    else:
        print("Could not find save placement_results cell")

    # 3) Replace DEF export cell with write_lef + write_def + summary
    def_export_src = '''# =========================
# EXPORT PLACEMENT TO DEF + LEF (OpenROAD visualization)
# =========================
# Uses placements_ppo from placement_results.json (or placements_greedy).
# Scale: 1 grid cell = 50 um => scale = 5000 DBU. LEF defines simple_rom, simple_alu with pins.

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
scale = 5000  # 1 grid cell = 50 microns; UNITS MICRONS 100
instances = data.get("instances")
nets = data.get("nets")
if not instances or not nets:
    raise ValueError("placement_results.json must contain 'instances' and 'nets'. Run netlist + placement cells first.")

os.makedirs("out", exist_ok=True)
lef_path = "out/macros.lef"
write_lef(lef_path, dbu_per_micron=100)
def_path = f"out/placement_{label}.def"
write_def(def_path, "chip_top", H, W, scale, instances, placements, nets)

die_w, die_h = W * scale, H * scale
n_comp = len(placements)
n_nets = len([n for n, p in nets.items() if len([x for x in p if isinstance(x, dict) and x.get("inst") in placements]) >= 2])
print("Export summary:")
print("  DEF:", def_path)
print("  LEF:", lef_path)
print("  Die area (DBU):", die_w, "x", die_h)
print("  Components:", n_comp)
print("  Nets written:", n_nets)
'''
    for i, c in enumerate(cells):
        if c["cell_type"] != "code":
            continue
        src = "".join(c.get("source", []))
        if "EXPORT PLACEMENT TO DEF" in src and "placement_results.json" in src and "COMPONENTS" in src:
            c["source"] = [line + "\n" for line in def_export_src.rstrip("\n").split("\n")]
            if c["source"] and not c["source"][-1].endswith("\n"):
                c["source"][-1] += "\n"
            print("Replaced DEF export cell at index", i)
            break
    else:
        print("Could not find DEF export cell")

    with open(NOTEBOOK, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)
    print("Saved", NOTEBOOK)

if __name__ == "__main__":
    main()
