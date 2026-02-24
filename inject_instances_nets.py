import json
instances = [{"name": "u_rom", "type": "simple_rom"}, {"name": "u_rom2", "type": "simple_rom"}, {"name": "u_add", "type": "simple_alu"}, {"name": "u_xor", "type": "simple_alu"}]
nets = {
    "A": [{"inst": "u_rom", "pin": "data"}, {"inst": "u_add", "pin": "a"}, {"inst": "u_xor", "pin": "a"}],
    "B": [{"inst": "u_rom2", "pin": "data"}, {"inst": "u_add", "pin": "b"}, {"inst": "u_xor", "pin": "b"}],
    "Y_add": [{"inst": "u_add", "pin": "y"}],
    "Y_xor": [{"inst": "u_xor", "pin": "y"}],
}
with open("placement_results.json", "r") as f:
    data = json.load(f)
data["instances"] = instances
data["nets"] = nets
with open("placement_results.json", "w") as f:
    json.dump(data, f, indent=2)
print("Injected instances and nets into placement_results.json")
