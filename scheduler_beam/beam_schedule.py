from functools import cache
import statistics
import traceback
from typing import Any, List, Set

from scheduler_beam.WIP_eta_predictor import ETAPredictor
from scheduler.progress_callback import ProgressCallback
from scheduler_beam.beam_eta_predictor import BeamEtaPredictor
from scheduler_beam.beam_inning import Inning, LineupNode
from services.inning_service import get_all_possible_innings
from services.player_service import get_early_players, get_late_players
from services.position_service import get_positions
from softball_models.player import Player

from softball_models.schedule import Schedule
from softball_models.schedule_config import QualityLevel, ScheduleConfig

from utils.math import clamp, get_percentile_item
from utils.timing import add_time, print_times

import time
import math


########################################
# Schedule - Our tree of possible linups
########################################
    
class BeamScheduler:

    def __init__(self, players: List[Player], config: ScheduleConfig, progress_callback: ProgressCallback):
        self.config: ScheduleConfig = config
        self.players: List[Player] = players
        self.fairness: int = config.fair_factor
        self.sigma_weight: float = config.sigma_weight

        self.late_players: List[Player] = get_late_players(players)
        self.early_players: List[Player] = get_early_players(players)
        self.all_players = self.late_players + self.early_players

        self.late_lineups: List[Inning] = get_all_possible_innings(self.all_players, config.females_required)
        self.early_lineups: List[Inning] = get_all_possible_innings(self.early_players, config.females_required)

        self.min_lineup: Inning = self.late_lineups[-1]
        self.max_lineup: Inning = self.late_lineups[0]

        self.best_score: float = 0
        self.paths: Set[Any] = set()

        self.percentiles = { 
            QualityLevel.HIGH: [0, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7, 1],
            QualityLevel.MEDIUM: [0, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 0.7],
            QualityLevel.LOW: [0, 0.02, 0.05, 0.15]
            }[config.quality_level]
        
        self.reporter = BeamEtaPredictor(progress_callback, 
                                         len(self.percentiles),
                                         config.number_innings)
    @staticmethod
    def create(players: List[Player], config: ScheduleConfig, progress_callback: ProgressCallback):

        scheduler = BeamScheduler(players, config, progress_callback)
        return scheduler.schedule()

    def schedule(self):

        start = time.time()
        print("create", self.players)

        root = LineupNode.root(self.early_players)
      
        print("creating tree....")
        print("number lineups late", len(self.late_lineups))
        print("number lineups early", len(self.early_lineups))
        print("Num players", len(self.all_players))

        leaf_nodes: List[LineupNode] = []
        self._depth_first(root, leaf_nodes)
        print("number of lineups created:", len(leaf_nodes))
        
        #
        # A leaf node represents the final lineup
        # Sort the leaf nodes by their strength, weighted by sigma (standard deviation between innings)
        # This should favor strong lineups that have low inning to inning deviation
        #
        leaf_nodes.sort(key=lambda node : -1*self._score(node))

        schedule = Schedule()
        schedule.players = self.all_players
        schedule.config = self.config
        schedule.positions = get_positions(len(self.all_players), allow_not_enough=True)

        #
        # Get the top lineup
        # This should be a strong lineup that has low standard deviation
        #
        node = leaf_nodes[0]
        print("final score", self._score(node))
        # print(node.cumulative_strength/6)

        end_node = node
        # print(end_node.cumulative_strength/self.config.number_innings)
        # print(end_node.sigma)

        i = self.config.number_innings
        while node and node.lineup:
            # TODO clean this up, could do a node_to_schedule function
            schedule.innings.append(node.lineup)

            if i < self.config.inning_of_late_arrivals:
                node.lineup.late = self.late_players

            node = node.prev
            i -= 1

        schedule.innings.reverse()

        end = time.time()
        print("Beam Schedule took: ", end - start, " seconds.")
        print_times()
        print("fair lineups", self._get_fair_lineups.cache_info())
        print("min viable", self._minimum_viable_score.cache_info())
        print(self._minimum_viable_score.cache_clear())
        print(self._get_fair_lineups.cache_clear())
        return schedule
    
    
    def _get_lineups(self, inning):
        if self.config.inning_of_late_arrivals <= inning:
            return self.late_lineups
        else:
            return self.early_lineups
        
    def _score(self, node: LineupNode):
        strengths = []
        prev = node
        while prev and prev.lineup:
            strengths.append(prev.lineup.strength)
            prev = prev.prev

        mean = statistics.mean(strengths)
        stddev = statistics.pstdev(strengths)

        return mean - stddev*self.sigma_weight
 
    def _depth_first(self, node: LineupNode, results: List[Any], current_depth: int = 1):
        start = time.time()

        if node.hash in self.paths:
            self.reporter.report(current_depth)
            return
        self.paths.add(node.hash)

        if current_depth > self.config.number_innings:
            # we have a leaf node
            results.append(node)
            score = self._score(node)
            if self.best_score <= score:
                self.best_score = score
            self.reporter.report(current_depth)
            return
        
        lineups = self._get_potential_lineups(node, current_depth)
      
        if not lineups:
            self.reporter.report(current_depth)
            return
        
        for percentile in self.percentiles:
            try:
                lineup = get_percentile_item(lineups, percentile)
                next = LineupNode(lineup, node)

                self._depth_first(next, results, current_depth+1)

            except Exception as e:
                traceback.print_exc()
                break

        add_time("depth_first", start)

    def _get_potential_lineups(self, node: LineupNode, depth: int):
        if depth == self.config.inning_of_late_arrivals:
            node.cumulative_counts.add_players(self.late_players)

        minimum_viable_score = 0
        if depth > 1 and self.best_score != 0:
            minimum_viable_score = self._minimum_viable_score(frozenset(node.get_stregnths()), depth)

        node.cumulative_counts.rebase()
        return self._get_fair_lineups(frozenset(node.cumulative_counts.counter.items()), depth, int(minimum_viable_score))


    @cache
    def _get_fair_lineups(self, counts: frozenset, current_depth: int, minimum: int = 0):
        start = time.time()
        fair_lineups = []

        lineups = self._get_lineups(current_depth)

        counts_items = list(counts)
        first_key, first_val = counts_items[0]
        rest_items = counts_items[1:]

        fairness = self.fairness

        #
        # Determine which lineups are 'fair' for this inning
        # and add them to the list. 
        #
        for lineup in lineups:

            if lineup.strength < minimum:
                break

            fair = True

            first_it_inc = 0
            if first_key in lineup.playing_ids:
                first_it_inc = 1

            min = first_val + first_it_inc
            max = min

            for id, count in rest_items:
                if id in lineup.playing_ids:
                    count += 1

                if count < min:
                    min = count
                elif count > max:
                    max = count

                if max - min > fairness:
                    fair = False
                    break

            if fair:
                fair_lineups.append(lineup)

        add_time("get_fair_lineups", start)

        return fair_lineups
    
    @cache
    def _minimum_viable_score(self, strengths: frozenset, current_depth):
  
        start_time = time.time()

        goal = self.best_score
        lower_bound = self.min_lineup.strength
        upper_bound = self.max_lineup.strength
        max_depth = self.config.number_innings

        remaining = max_depth - current_depth

        strengths = list(strengths)
        mean = statistics.mean(strengths)
        maximize_strengths: List[float] = strengths + [upper_bound]*(remaining-1)
        minimize_stddev: List[float] = strengths + [mean]*(remaining - 1)

        sum_strength = sum(maximize_strengths)
        sum_std = sum(minimize_stddev)
        sum_std2 = sum(x*x for x in minimize_stddev)

        n_strength = len(maximize_strengths)
        n_std = len(minimize_stddev)

        weight = self.sigma_weight

        start = int(lower_bound * 2)
        end = int(upper_bound * 2)

        ideal = upper_bound + 1

        for i in range(start, end + 1):
            v = i * 0.5

            mean = (sum_strength + v) / (n_strength + 1)

            new_sum = sum_std + v
            new_sum2 = sum_std2 + v*v
            n = n_std + 1
            inv_n = 1/n

            variance = new_sum2*inv_n - (new_sum*inv_n)**2
            stddev = math.sqrt(variance)

            if mean - stddev*weight > goal:
                ideal = v
                break

        add_time("minimum_viable_score", start_time)
        return ideal

            


