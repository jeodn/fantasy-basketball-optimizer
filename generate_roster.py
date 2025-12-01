import pandas as pd
import numpy as np
import json

from util import get_players_dataframe, export_player_df_as_json


MYTEAM_FILENAME="data_myteam.json"



my_team = [
    1628973,
    1631097,
    1631170,
    1630530,
    1631096,
    203897,
    203999,
    1629675,
    1641717,
    1641750,
    1630559,
    203468,
    1630200,
    202331, # pg
    203932 # ag
] 


def write_myteam_stats():
    with open("data_zscores.json") as f:
        player_z_json = json.load(f)   # data is a dict: { "203999": {...}, "1629027": {...}, ... }

    filtered = {pid: stats for pid, stats in player_z_json.items() if int(pid) in my_team}

    with open("data_myteam.json", "w") as f:
        json.dump(filtered, f, indent=4)


def write_myteam_stats_categorywise():
    with open("data_myteam.json") as g:
        myteam_z_json = json.load(g)   # data is a dict: { "203999": {...}, "1629027": {...}, ... }

    categorywise_stats = {"TEAM_CATEGORY_STATS" : {
        "name": "TEAM",
        "FG%_Impact": 0.0,
        "FT%_Impact": 0.0,
        "zFG%": 0.0,
        "zFT%": 0.0,
        "z3PTM": 0.0,
        "zPTS": 0.0,
        "zREB": 0.0,
        "zAST": 0.0,
        "zST": 0.0,
        "zBLK": 0.0,
        "zTO": 0.0,
        "Total_Value": 0.0
        }
    }


    for pid, stats in myteam_z_json.items():
        for statname, statval in stats.items():
            if statname == "name":
                continue

            categorywise_stats["TEAM_CATEGORY_STATS"][statname] += statval
            categorywise_stats["TEAM_CATEGORY_STATS"][statname] = round(categorywise_stats["TEAM_CATEGORY_STATS"][statname], 3)


    with open("data_myteam_cumulative.json", "w") as f:
        json.dump(categorywise_stats, f, indent=4)


if __name__ == "__main__":
     write_myteam_stats()
     write_myteam_stats_categorywise()


