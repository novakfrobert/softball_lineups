import random
from typing import Dict, List
from softball_player import Player
from collections import defaultdict
from scipy.optimize import linear_sum_assignment
from softball_data import sort_players
import numpy as np

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

        if max_score:
            self.score = round(100*valid_scores.sum() / max_score, 1)

        for i, j in zip(row_ind, col_ind):
            player = fielders[i]
            pos = positions[j]
            self.positions[pos] = player