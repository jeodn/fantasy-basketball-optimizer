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


if __name__ == "__main__":
    with open("data_zscores.json") as f:
        player_z_json = json.load(f)   # data is a dict: { "203999": {...}, "1629027": {...}, ... }

    filtered = {pid: stats for pid, stats in player_z_json.items() if int(pid) in my_team}

    with open("data_myteam.json", "w") as f:
        json.dump(filtered, f, indent=4)

    #player_df = get_players_dataframe()
    #my_team_df = player_df[player_df["player_id"].isin(my_team)]

    #export_player_df_as_json(MYTEAM_FILENAME, my_team_df)

    #print(my_team_df)
