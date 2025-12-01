import json

with open("COOL_data.json") as f:
    d = json.load(f)
    print(d.get("203999"))