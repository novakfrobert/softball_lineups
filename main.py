import numbers
import math
import csv
import time
from typing import Dict, Set, List, Callable
from dataclasses import dataclass
from collections import defaultdict
from scipy.optimize import linear_sum_assignment

import random
import numpy as np
import streamlit as st


class Player:
    name: str
    positions: Set[str]
    positions_stengths: Dict[str, int]
    available: bool
    innings_played: int
    late: bool
    female: bool

    def __init__(self, name, available, female, late, positions, strengths):
        
        assert len(positions) == len(strengths), f"{name} has mismatched number of positions and strengths"
        assert len(positions) > 0, f"{name} cannot play 0 positions"

        self.name = name
        self.available = available
        self.late = late
        self.innings_played = 0 # start at 0 for now
        self.female = female

        self.positions = set(positions)
        self.positions_stengths = {}
        for i in range(len(positions)):
            self.positions_stengths[positions[i]] = strengths[i]

    def try_update_positions(self, from_pos, to_pos):
        if from_pos in self.positions:
            self.positions.remove(from_pos)
            str = self.positions_stengths.pop(from_pos)
            self.positions.add(to_pos)
            self.positions_stengths[to_pos] = str

    def __repr__(self):
        return f"{self.name} {self.positions_stengths}\n"

class Inning:
    number: int

    bench: Dict[str, Player] # key is name
    positions: Dict[str, Player] # key is position

    late: List[Player] # key is name


    females_playing: int
    playing_count: int

    def __init__(self, n: int, bench: List[Player], late: List[Player]):
        self.number = n
        self.bench = {p.name: p for p in bench}
        self.late = late
        self.positions = {}
        self.females_playing = 0
        self.playing_count = 0
        self.score = 0

    def __str__(self):
        res = f"{self.number}\n"

        res += f"\tPlaying:\n"
        for k,v in self.positions.items():
            res += f"\t\t{k} {v.name}\n"

        res += f"\tSitting:\n"
        for k,v in self.bench.items():
            res += f"\t\t{k}\n"
        return res
    
    def move_to_field(self, player: Player, position: str):
        self.bench.pop(player.name)
        self.positions[position] = player
        self.playing_count += 1
        player.innings_played += 1
        if player.female:
            self.females_playing += 1

    def get_least_played_players(self):
        players_by_play_count = defaultdict(list)
        for player in self.bench.values():
            players_by_play_count[player.innings_played].append(player)
        fewest = min(players_by_play_count.keys())

        return players_by_play_count[fewest]
    
    def try_finding_any_player(self, position: str):
        if not self.bench: return False
        bench = self.get_least_played_players()
        random.shuffle(bench)
        self.move_to_field(bench[0], position)
        return True
    
    def try_finding_optimal_player(self, position: str):
        bench = [p for p in self.bench.values() if position in p.positions]
        if not bench: return False
        sort_players(position, bench)
        self.move_to_field(bench[0], position)
        return True
    
    def try_finding_female_player(self, position: str):
        # try getting female at this position
        bench = [p for p in self.bench.values() if position in p.positions and p.female]
        sort_players(position, bench)
        if not bench: 
            # try getting any female
            bench = [p for p in self.bench.values() if p.female]
            random.shuffle(bench)
        if not bench:
            return False
        self.move_to_field(bench[0], position)
        return True

    def must_be_female(self, players_required: int, females_required: int):
        slots_remaining = players_required - self.playing_count
        females_remaining = females_required - self.females_playing
        return slots_remaining == females_remaining
    
    def optimize_lineup(self, positions: List[str]):
        n = len(self.positions)

        positions = list(self.positions.keys())
        fielders = list(self.positions.values())

        weights = {"SS": 100, "P": 100, "C": 5, "LF": 90, "LCF": 90, "3B": 95, "2B": 60, "1B": 70, "CF": 80, "RF": 15, "RCF": 25}
        weights = {pos: weights[pos] for pos in positions}
        max_score = sum(10 * w for w in weights.values())

        # Build score matrix: rows = players, cols = positions
        score_matrix = np.full((n, n), -1e9)  # Large negative default for invalid positions

        for i, player in enumerate(fielders):
            for j, pos in enumerate(positions):
                if pos in player.positions:
                    strength = player.positions_stengths.get(pos, 0)
                    weight = weights.get(pos, 1.0)
                    score_matrix[i][j] = strength * weight

        # Solve using the Hungarian algorithm (maximize by minimizing the negative scores)
        row_ind, col_ind = linear_sum_assignment(-score_matrix)

        # Only compute score using the positive values, prevents
        # the large negative defaults from influencing the score.
        # A person playing out of position essentially counts as 0.
        matched_scores = score_matrix[row_ind, col_ind]
        valid_scores = matched_scores[matched_scores >= 0]
        self.score = round(100*valid_scores.sum() / max_score, 1)

        for i, j in zip(row_ind, col_ind):
            player = fielders[i]
            pos = positions[j]
            self.positions[pos] = player

class Schedule: 
    players: List[Player]
    innings: List[Inning] = []

    females_required: int
    players_required: int
    inning_of_late_arrivals: int
    positions: List[str]

    max_players: int = 10
    min_players: int = 8

    warnings: List[str] = []

    def __init__(self, players: List[Player], females_required: int = 3, players_required: int = 10, inning_of_late_arrivals: int = 3):
        self.players = players
        self.females_required = females_required
        self.players_required = players_required
        self.inning_of_late_arrivals = inning_of_late_arrivals

    def get_positions(self):
        if self.players_required == 10:
            return ["P", "SS", "LF", "LCF", "3B", "1B", "2B", "RCF", "RF", "C"] # ordered by most important
        elif self.players_required == 9:
            return ["P", "SS", "LF", "CF", "3B", "1B", "2B", "RF", "C"] # ordered by most important
        elif self.players_required == 8:
            return ["P", "SS", "LF", "CF", "3B", "1B", "2B", "RF"] # ordered by most important
        else:
            raise Exception(f"Invalid number of players {self.players_required}")

    def add_inning(self):
        number = len(self.innings) + 1

        bench: List[Player] = []
        late: List[Player] = []
        for player in self.players:

            if not player.available:
                continue

            if player.late and number < self.inning_of_late_arrivals:
                late.append(player)
                continue

            bench.append(player)

        inning = Inning(number, bench, late)
        self.innings.append(inning)
        return inning
    
    def validate(self):

        not_enough_females = []
        not_enough_players = []

        for inning in self.innings:
            for pos, player in inning.positions.items():
                if pos not in player.positions:
                    self.warnings.append(f"{player.name} is playing {pos} at random in inning {inning.number}.")
            
            if inning.playing_count < self.players_required:
                not_enough_players.append(inning.number)

            if inning.females_playing < self.females_required:
                not_enough_females.append(inning.number)

        if not_enough_females:
            self.warnings.append(f"Not enough females in the following innings: {not_enough_females}")

        if not_enough_players:
            self.warnings.append(f"Not enough players in the following innings: {not_enough_players}")
    
    @staticmethod
    def create(num_innings: int, players: List[Player], females_required: int, players_required: int, inning_of_late_arrivals: int):

        if players_required < 10:
            # remove lcf and rcf in favor of cf
            for player in players:
                player.try_update_positions("RCF", "RF")
                player.try_update_positions("LCF", "CF")
        
        schedule = Schedule(players, females_required, players_required, inning_of_late_arrivals)

        # create schedule
        for i in range(num_innings):

            inning: Inning = schedule.add_inning()
            
            positions = schedule.get_positions()
            for position in positions:

                if inning.must_be_female(players_required, females_required):
                    if inning.try_finding_female_player(position):
                        continue
                
                if inning.try_finding_optimal_player(position):
                    continue

                if inning.try_finding_any_player(position):
                    continue

            inning.optimize_lineup(positions)
            if players_required == 8:
                inning.positions["C"] = Player("⚠ COURTESY ⚠", True, False, False, ["C"], [0])

        schedule.validate()

        return schedule
    


# TODO add to team class
def sort_players(position: str, players: List[Player]):
    players.sort(key=lambda p: (p.innings_played, -1*p.positions_stengths[position]))


players = [
    Player("Frank", True, False, False, ["LF","LCF","RCF"], [9, 8, 8]),
    Player("Joe", True, False, False, ["LF","LCF","RF"], [8, 9, 8]),
    Player("Ethan", True, False, False, ["RCF", "LCF", "RF", "2B", "3B"], [4, 3, 5, 5, 4]),
    Player("Janelle", True, True, False, ["2B", "3B", "RF", "P"], [9, 5, 4, 5]),
    Player("Frido", True, False, False, ["LF","LCF","RCF", "SS", "3B"], [6, 6, 6, 6, 6]),
    Player("Dude", True, False, False, ["1B","LF", "3B"], [8, 10, 10]),
    Player("Girl", True, True, False, ["C","1B","SS", "2B"], [5, 5, 5, 3]),
    Player("Abel", True, True, False, ["C","RF","RCF", "2B"], [5, 5, 5, 3]),
    Player("Guy", True, False, False, ["C","RF","RCF", "2B", "3B", "1B"], [5, 5, 5, 3, 2, 3]),
    Player("Jackie", True, True, False, ["C","LCF","RCF"], [6, 6, 6]),
    Player("Mary", True, True, False, ["LCF","RF","RCF", "3B"], [5, 3, 3, 1]),
    Player("Daniella", True, True, False, ["2B","RCF","RF"], [6, 6, 6]),
    Player("Nick", True, False, False, ["SS","1B","RCF", "LCF", "3B"], [7, 8, 7, 7, 7]),
    Player("Jacob", True, False, False, ["2B", "1B"], [9, 6]),
    Player("Ruby", True, True, False, ["3B","RF","C", "2B"], [6, 7, 7, 4]),
    Player("Gary", True, False, False, ["SS","LF","LCF"], [7, 7, 7])
]

def load_players(csv_file: str):
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

def players_to_dicts(players: List[Player]):
    data = []
    for p in players:
        row = {
            "Name": p.name,
            "Female": p.female,
            "Available": p.available,
            "Late": p.late,
        }
        for pos, str in p.positions_stengths.items():
            row[pos] = str
        data.append(row)
    return data

# Convert edited dicts back to Player list
def dicts_to_players(dicts):
    players = []
    for d in dicts:
        name = d.pop("Name")
        female = d.pop("Female")
        available = d.pop("Available")
        late = d.pop("Late")
        positions = []
        strengths = []
        for pos, strength in d.items():
            if math.isnan(strength):
                continue
            positions.append(pos)
            strengths.append(float(strength))
        players.append(Player(name, available, female, late, positions, strengths))
    return players

st.set_page_config(
    page_title="Softball Lineup",     # 📝 Tab title
    page_icon="🥎",                   # 🖼️ Emoji or path to image
    layout="wide"                     # Full-width layout
)

with st.container():
    col_main_padding_left, col_main, col_main_padding_right = st.columns([2, 10, 2])  # middle column wider

    with col_main:
        file = st.file_uploader("Upload CSV", type="csv")
        if file:
            players = load_players(file)
        st.divider()

        st.subheader("🔧 Edit Players")
        
        player_dicts = players_to_dicts(players)
        edited_df = st.data_editor(player_dicts, num_rows="dynamic", use_container_width=True, disabled=["Female"])
        players = dicts_to_players(edited_df)
        number_players = len([p for p in players if p.available])

    # Using "with" notation
    with st.sidebar:
        number_innings = st.number_input("Number of Innings", min_value=1, max_value=10, value=6, key="num_innings")

        number_fielders = st.number_input("Number Fielders", min_value=Schedule.min_players, max_value=Schedule.max_players, value=max(8, min(10, number_players)), key="num_fielders")

        default_min_females = 2 if number_fielders < 10 else 3 
        minimum_females = st.number_input("Minnimum Females", min_value=0, max_value=Schedule.max_players, value=default_min_females, key="min_females")

        current_value = min(st.session_state.get("late_inning", 3), number_innings)
        inning_of_late_arrivals = st.number_input("Inning of Late Arrivals", min_value=1, max_value=number_innings, value=current_value, key="late_inning")

    schedule: Schedule = Schedule.create(
        number_innings,
        players, 
        minimum_females, 
        number_fielders, 
        inning_of_late_arrivals)

    with col_main:
        for warning in schedule.warnings:
            st.write(f"⚠️{warning}")


col_padding_left, col_count, col_padding_mid, col_lineup, col_padding_right = st.columns([3, 2, 1, 8, 2])
with col_lineup:
    st.subheader("📋 Lineups by Inning")

    for inning in schedule.innings:
        st.header(f"Inning {inning.number}", divider=True)
        playing = '\n'.join([f"{pos} {player.name}" for pos, player in inning.positions.items()])
        sitting = '\n'.join([f"{name}" for name in inning.bench])
        late = '\n'.join([f"{player.name}" for player in inning.late])

        if not sitting: sitting = "None"
        if not late: late = "None"

        col_stats, col_playing, col_sitting, col_late = st.columns([2,3,3,3])
        with col_playing:
            st.markdown("##### 🟢 Playing:")
            st.code(playing, line_numbers=False)
        with col_sitting:
            st.markdown("##### 🔴 Sitting:")
            st.code(sitting, line_numbers=False)
        with col_late:
            st.markdown("##### 🟡 Late:")
            st.code(late, line_numbers=False)
        with col_stats:
            st.markdown(f"<b>Score:</b> <small>{inning.score}</small>", unsafe_allow_html=True)
            st.markdown(f"<b>Females:</b> <small>{inning.females_playing}</small>", unsafe_allow_html=True)
            st.markdown(f"<b>Players:</b> <small>{inning.playing_count}</small>", unsafe_allow_html=True)

with col_count:
    available_players: List[Player] = [p for p in players if p.available]
    available_players.sort(key=lambda p: p.innings_played)
    st.subheader("📋 Innings Played")
    st.code('\n'.join([f"{p.innings_played} {p.name}" for p in available_players]), line_numbers=False)


