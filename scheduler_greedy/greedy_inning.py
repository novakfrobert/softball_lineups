import random
from typing import Dict, List
from softball_models.inning import Inning
from softball_models.player import Player
from collections import defaultdict
from scipy.optimize import linear_sum_assignment
from data.softball_data import sort_players
from softball_models.positions import Position
import numpy as np

class GreedyInning(Inning):

    def move_to_field(self, player: Player, position: Position):
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
    
    def try_finding_any_player(self, position: Position):
        if not self.bench: return False
        bench = self.get_least_played_players()
        random.shuffle(bench)
        self.move_to_field(bench[0], position)
        return True
    
    def try_finding_optimal_player(self, position: Position):
        bench = [p for p in self.bench.values() if position in p.positions]
        if not bench: return False
        sort_players(position, bench)
        self.move_to_field(bench[0], position)
        return True
    
    def try_finding_female_player(self, position: Position):
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
    
    def optimize_lineup(self, positions: List[Position]):
        n = len(self.positions)

        positions = list(self.positions.keys())
        fielders = list(self.positions.values())

        max_score = sum(10 * pos.weight for pos in positions)

        # Build score matrix: rows = players, cols = positions
        score_matrix = np.full((n, n), -1e9)  # Large negative default for invalid positions

        for i, player in enumerate(fielders):
            for j, pos in enumerate(positions):
                if pos in player.positions:
                    strength = player.positions_stengths.get(pos, 0)
                    weight = pos.weight
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