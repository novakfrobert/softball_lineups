from collections import defaultdict
import random
from typing import List

import numpy as np
from scipy.optimize import linear_sum_assignment

from data.softball_data import sort_players
from softball_models.inning import Inning
from softball_models.player import Player
from softball_models.positions import Position, get_positions

from softball_models.schedule import Schedule
from softball_models.schedule_config import ScheduleConfig


class GreedyScheduler: 

    def __init__(self, players: List[Player], config: ScheduleConfig):
        self.players: List[Player] = players
        self.config: ScheduleConfig = config

    @staticmethod
    def create(players: List[Player], config: ScheduleConfig):
        scheduler = GreedyScheduler(players, config)
        return scheduler.schedule()
    
    def schedule(self):
        schedule = Schedule()
        schedule.players = self.players
        schedule.config = self.config

        schedule.positions = get_positions(self.config.players_required)

        # create schedule
        for i in range(self.config.number_innings):

            inning: Inning = self.start_inning(i)
            
            for position in schedule.positions:

                if self.must_be_female(inning):
                    if self.try_finding_female_player(inning, position):
                        continue
                
                if self.try_finding_optimal_player(inning, position):
                    continue

                if self.try_finding_any_player(inning, position):
                    continue

            self.optimize_lineup(inning, schedule.positions)
            schedule.innings.append(inning)

        return schedule
    
    def start_inning(self, n):
        number = n + 1

        bench: List[Player] = []
        late: List[Player] = []

        for player in self.players:

            if not player.available:
                continue

            if player.late and number < self.config.inning_of_late_arrivals:
                late.append(player)
                continue

            bench.append(player)

        inning = Inning()
        inning.id = number
        inning.bench = { p.name: p for p in bench }
        inning.late = late
        return inning
    
    def move_to_field(self, inning: Inning, player: Player, position: Position):
        inning.bench.pop(player.name)
        inning.field[position] = player
        inning.playing_count += 1
        player.innings_played += 1
        if player.female:
            inning.females_playing += 1

    def get_least_played_players(self, inning: Inning):
        players_by_play_count = defaultdict(list)
        for player in inning.bench.values():
            players_by_play_count[player.innings_played].append(player)
        fewest = min(players_by_play_count.keys())

        return players_by_play_count[fewest]
    
    def try_finding_any_player(self, inning: Inning, position: Position):
        if not inning.bench: return False
        bench = self.get_least_played_players(inning)
        random.shuffle(bench)
        self.move_to_field(inning, bench[0], position)
        return True
    
    def try_finding_optimal_player(self, inning: Inning, position: Position):
        bench = [p for p in inning.bench.values() if position in p.positions]
        if not bench: return False
        sort_players(position, bench)
        self.move_to_field(inning, bench[0], position)
        return True
    
    def try_finding_female_player(self, inning: Inning, position: Position):
        # try getting female at this position
        bench = [p for p in inning.bench.values() if position in p.positions and p.female]
        sort_players(position, bench)
        if not bench: 
            # try getting any female
            bench = [p for p in self.bench.values() if p.female]
            random.shuffle(bench)
        if not bench:
            return False
        self.move_to_field(inning, bench[0], position)
        return True

    def must_be_female(self, inning: Inning):
        slots_remaining = self.config.players_required - inning.playing_count
        females_remaining = self.config.females_required - inning.females_playing
        return slots_remaining == females_remaining
    
    def optimize_lineup(self, inning: Inning, positions: List[Position]):
        n = len(inning.field)

        positions = list(inning.field.keys())
        fielders = list(inning.field.values())

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
            inning.strength = round(100*valid_scores.sum() / max_score, 1)

        for i, j in zip(row_ind, col_ind):
            player = fielders[i]
            pos = positions[j]
            inning.field[pos] = player
    