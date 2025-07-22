import math
import csv
import numpy as np
import pandas as pd
from softball_player import Player
from typing import List

def get_default_players():
    return [
        Player("Frank", True, False, False, ["LF","LCF","RCF"], [9, 8, 8]),
        Player("Joe", True, False, False, ["LF","LCF","RF"], [8, 9, 8]),
        Player("Janelle", True, True, False, ["2B", "3B", "RF", "P"], [9, 5, 4, 5]),
        Player("Frido", True, False, False, ["LF","LCF","RCF", "SS", "3B"], [6, 6, 6, 6, 6]),
        Player("Dude", True, False, False, ["1B","LF", "3B"], [8, 10, 10]),
        Player("Guy", True, False, False, ["C","RF","RCF", "2B", "3B", "1B"], [5, 5, 5, 3, 2, 3]),
        Player("Jackie", True, True, False, ["C","LCF","RCF"], [6, 6, 6]),
        Player("Daniella", True, True, False, ["2B","RCF","RF"], [6, 6, 6]),
        Player("Nick", True, False, False, ["SS","1B","RCF", "LCF", "3B"], [7, 8, 7, 7, 7]),
        Player("Jacob", True, False, False, ["2B", "1B"], [9, 6]),
        Player("Ruby", True, True, False, ["3B","RF","C", "2B"], [6, 7, 7, 4]),
        Player("Gary", True, False, False, ["SS","LF","LCF"], [7, 7, 7])
    ]

def sort_players(position: str, players: List[Player]):
    players.sort(key=lambda p: (p.innings_played, -1*p.positions_stengths[position]))


def load_players_from_csv(csv_file: str):
    players = []
    reader = csv.reader(csv_file.read().decode("utf-8-sig").splitlines())
    header = next(reader)  # skip header
    
    # The first 4 columns need to be in a specific order
    player_info_header = ["name", "female", "available", "late"]
    assert [col.lower() for col in header[:4]] == player_info_header, \
           f"The first 4 columns must be {player_info_header} but was given {header[:4]}"

    # Position columns must contain all the following positions
    position_header = ["P", "SS", "LF", "LCF", "3B", "2B", "1B", "RCF", "RF", "C"]
    assert [col.upper() for col in sorted(header[4:])] == sorted(position_header), \
        f"The position columns must contain all the following positions {position_header} but was given {header[4:]}"
    
    # The 
    for row_num, row in enumerate(reader, 2):

        # Skip empty rows
        if all([col.strip() == "" for col in row]):
            continue

        # Error on partially filled rows in the first 4 columns
        assert all([col.strip() != "" for col in row[:4]]), \
               f"Empty value on line {row_num}"

        # Extract info from first 4 rows
        name = row[0]
        female = row[1].strip().lower() == "true"
        available = row[2].strip().lower() == "true"
        late = row[3].strip().lower() == "true"

        # Extract position data
        positions = []
        strengths = []
        for i, str in enumerate(row[4:], 4):
            if str:
                positions.append(header[i])
                strengths.append(int(str))

        players.append(Player(name, available, female, late, positions, strengths))

    return players

def players_to_df(players: List["Player"]) -> pd.DataFrame:
    # Define all possible positions
    positions = ["P", "SS", "LF", "LCF", "3B", "2B", "1B", "RCF", "RF", "C"]

    # Collect data from players
    data = []
    for p in players:
        row = {
            "Name": p.name,
            "Female": p.female,
            "Available": p.available,
            "Late": p.late,
        }
        for pos in positions:
            row[pos] = p.positions_stengths.get(pos, float("NaN"))
        data.append(row)

    # If no data, insert one default row
    # if not data:
    #     data.append({
    #         "Name": None,
    #         "Female": False,
    #         "Available": True,
    #         "Late": False,
    #         **{pos: float("NaN") for pos in positions}
    #     })

    # Create the dataframe
    df = pd.DataFrame(data)

    # Define expected column types
    expected_types = {
        "Name": "string",
        "Female": "bool",
        "Available": "bool",
        "Late": "bool",
    }
    expected_types.update({pos: "float" for pos in positions})

    # Ensure all columns exist and are typed correctly
    for col, dtype in expected_types.items():
        if col not in df.columns:
            if dtype == "bool":
                df[col] = False
            elif dtype == "float":
                df[col] = float("NaN")
            elif dtype == "string":
                df[col] = None
        df[col] = df[col].astype(dtype)

    return df

# Convert edited dicts back to Player list
def dataframe_to_players(df: pd.DataFrame) -> List["Player"]:
    players = []

    positions = ["P", "SS", "LF", "LCF", "3B", "2B", "1B", "RCF", "RF", "C"]

    defaults = {
        "Name": "",
        "Female": False,
        "Available": True,
        "Late": False,
        **{pos: float("NaN") for pos in positions}
    }
    df = df.replace({None: np.nan})
    df = df.fillna(defaults)

    for idx, row in df.iterrows():
        name = row.get("Name")
        female = row.get("Female")
        available = row.get("Available")
        late = row.get("Late")

        # Skip if name is missing or blank
        if not isinstance(name, str) or not name.strip():
            continue

        # Collect valid position strengths
        player_positions = []
        strengths = []

        for pos in positions:
            strength = row.get(pos)
            if strength is None or (isinstance(strength, float) and math.isnan(strength)):
                continue
            player_positions.append(pos)
            strengths.append(float(strength))

        # Skip rows with no valid position strengths
        # if not player_positions or not strengths:
            # continue

        # Create and collect Player object
        players.append(Player(name, available, female, late, player_positions, strengths))

    return players