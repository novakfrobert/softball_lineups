import math
import csv
import numpy as np
import pandas as pd
from softball_models.player import Player
from services.position_service import _1B, _2B, _3B, _C, _LCF, _LF, _P, _RCF, _RF, _SS, get_position
from typing import List

def get_default_players():
    return [
        Player("Frank", True, False, False, [_LF, _LCF, _RCF], [9, 8, 8]),
        Player("Joe", True, False, False, [_LF, _LCF, _RF], [8, 9, 8]),
        Player("Janelle", True, True, False, [_2B, _3B, _RF, _P], [9, 5, 4, 5]),
        Player("Kristy", True, True, False, [_SS, _3B, _RF, _P, _C], [6, 7, 4, 5, 3]),
        Player("Frido", True, False, False, [_LF, _LCF, _RCF, _SS, _3B], [6, 6, 6, 6, 6]),
        Player("Dude", True, False, False, [_1B, _LF, _3B], [8, 10, 10]),
        Player("Guy", True, False, False, [_C, _RF, _RCF, _2B, _3B, _1B], [5, 5, 5, 3, 2, 3]),
        Player("Jackie", True, True, False, [_C, _LCF, _RCF], [6, 6, 6]),
        Player("Daniella", True, True, False, [_2B, _RCF, _RF], [6, 6, 6]),
        Player("Nick", True, False, False, [_SS, _1B, _RCF, _LCF, _3B], [7, 8, 7, 7, 7]),
        Player("Rob", True, False, False, [_2B, _1B, _RCF, _LCF, _3B], [3, 5, 6, 6, 7]),
        Player("Jacob", True, False, False, [_2B, _1B], [9, 6]),
        Player("Hubie", True, False, False, [_3B, _1B], [4, 6]),
        Player("Ruby", True, True, False, [_3B, _RF, _C, _2B], [6, 7, 7, 4]),
        # Player("Gary", True, False, False, [_SS, _LF, _LCF], [7, 7, 7]),
        # Player("George", True, False, False, [_SS, _LF, _LCF], [7, 7, 7]),
        # Player("Freddy", True, False, False, [_SS, _LF, _LCF], [7, 7, 7]),
        # Player("Hal", True, False, False, [_3B, _RF, _LCF], [7, 7, 7]),
        # Player("Louis", True, True, False, [_SS, _2B, _1B], [7, 7, 7]),
        # Player("Dewey", True, False, False, [_RCF, _P, _C], [7, 7, 7])
    ]


def load_players_from_csv(csv_file: str) -> List[Player]:

    players = []
    reader = csv.reader(csv_file.read().decode("utf-8-sig").splitlines())
    header = next(reader)  # skip header

    # sometimes a downloaded csv will have blank column 1 or a column with just row numbers. If so, offset everything by 1
    offset = 1 if header[0] == "" else 0
    col = lambda i: i + offset
    
    # The first 4 columns need to be in a specific order
    player_info_header = ["name", "female", "available", "late"]
    assert [col.lower() for col in header[col(0):col(4)]] == player_info_header, \
           f"The first 4 columns must be {player_info_header} but was given {header[:4]}"

    # Position columns must contain all the following positions
    position_header = ["P", "SS", "LF", "LCF", "3B", "2B", "1B", "RCF", "RF", "C"]
    assert [col.upper() for col in sorted(header[col(4):])] == sorted(position_header), \
        f"The position columns must contain all the following positions {position_header} but was given {header[4:]}"
    
    for row_num, row in enumerate(reader, 2):

        # Skip empty rows
        if all([col.strip() == "" for col in row]):
            continue

        # Error on partially filled rows in the first 4 columns
        assert all([col.strip() != "" for col in row[:4]]), \
               f"Empty value on line {row_num}"

        # Extract info from first 4 rows
        name = row[col(0)]
        female = row[col(1)].strip().lower() == "true"
        available = row[col(2)].strip().lower() == "true"
        late = row[col(3)].strip().lower() == "true"

        # Extract position data
        positions = []
        strengths = []
        for i, str in enumerate(row[col(4):], col(4)):
            if str:
                positions.append(get_position(header[i]))
                strengths.append(int(str))

        players.append(Player(name, available, female, late, positions, strengths))

    return players

def players_to_df(players: List[Player]) -> pd.DataFrame:
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
            ppos = get_position(pos)
            row[pos] = p.positions_stengths.get(ppos, float("NaN"))
        data.append(row)

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
def dataframe_to_players(df: pd.DataFrame) -> List[Player]:
    players: List[Player] = []

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
            player_positions.append(get_position(pos))
            strengths.append(float(strength))

        # Skip rows with no valid position strengths
        # if not player_positions or not strengths:
            # continue

        # Create and collect Player object
        players.append(Player(name, available, female, late, player_positions, strengths))

    #
    # Updating positions so that if a player can play one outfield position
    # then they can play the equivalent position for a understaffed team.
    #
    lcf = get_position("LCF")
    cf = get_position("CF")
    rcf = get_position("RCF")
    rf = get_position("RCF")

    def update_player_positions(old, new):
        if old in player.positions:
            player.positions.add(new)
            player.positions_stengths[new] = player.positions_stengths[old]

    for player in players:
        update_player_positions(lcf, cf)
        update_player_positions(rcf, rf)


    return players

     
def get_late_players(players: List[Player]):
    return [p for p in players if p.available and p.late]

def get_early_players(players: List[Player]):
    return [p for p in players if p.available and not p.late]