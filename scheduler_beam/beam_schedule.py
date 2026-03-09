from scipy.optimize import minimize_scalar
import statistics
import traceback
from typing import Any, List, Set

from scheduler_beam.beam_inning import Inning, LineupNode
from services.inning_service import get_all_possible_innings
from services.player_service import get_early_players, get_late_players
from services.position_service import get_positions
from softball_models.player import Player

from softball_models.schedule import Schedule
from softball_models.schedule_config import ScheduleConfig

from utils.math import clamp, get_percentile_item
from utils.timing import add_time, print_times

import time
import math

def frange(start, stop, step):
    x = start
    while x < stop:
        yield x
        x += step


########################################
# Schedule - Our tree of possible linups
########################################
    
class BeamScheduler:

    def __init__(self, sigma_weight: float, fairness_index: int, players: List[Player], config: ScheduleConfig):
        self.config: ScheduleConfig = config
        self.players: List[Player] = players
        self.fairness: int = fairness_index
        self.sigma_weight: float = sigma_weight

        self.late_players: List[Player] = get_late_players(players)
        self.early_players: List[Player] = get_early_players(players)
        self.all_players = self.late_players + self.early_players

        self.late_lineups: List[Inning] = get_all_possible_innings(self.all_players, config.females_required)
        self.early_lineups: List[Inning] = get_all_possible_innings(self.early_players, config.females_required)

        self.min_lineup: Inning = self.late_lineups[-1]
        self.max_lineup: Inning = self.late_lineups[0]

        self.best_score: float = 0
        self.paths: Set[Any] = set()


    @staticmethod
    def create(sigma_weight: float, fairness_index: int, players: List[Player], config: ScheduleConfig):

        start = time.time()

        scheduler = BeamScheduler(sigma_weight, fairness_index, players, config)
        return scheduler.schedule()

    def schedule(self):

        start = time.time()
        print("create", self.players)

        root = LineupNode.root(self.all_players)
      
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
        print(node.cumulative_strength/6)

        end_node = node
        print(end_node.cumulative_strength/self.config.number_innings)
        print(end_node.sigma)

        print(node.sigma)
        i = self.config.number_innings
        while node and node.lineup:
            # print()
            # print(i)
            # print(node.lineup.strength)
            # print(node.lineup.field)

            schedule.innings.append(node.lineup)

            if i < self.config.inning_of_late_arrivals:
                node.lineup.late = self.late_players

            node = node.prev
            i -= 1

        schedule.innings.reverse()

        end = time.time()
        print("Beam Schedule took: ", end - start, " seconds.")
        print_times()

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

        lineups = self._get_lineups(current_depth)

        if current_depth > self.config.number_innings:
            # we have a leaf node
            results.append(node)
            score = self._score(node)
            if self.best_score <= score:
                self.best_score = score
            return
        
        minimum_viable_score = 0
        if current_depth > 1 and self.best_score != 0:
            minimum_viable_score = self._minimum_viable_score(node, current_depth)

        # print("Calling fair lineups, depth", current_depth)
        fair_lineups = self._get_fair_lineups(node, lineups, minimum_viable_score)

        if not fair_lineups:
            # print("No fair lineups")
            return
        
        # TODO store in variable in class, take as param
        percentiles = [0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8]
        
        for percentile in percentiles:
            try:
                lineup = get_percentile_item(fair_lineups, percentile)
                next = LineupNode(lineup, node)

                if current_depth == self.config.inning_of_late_arrivals:
                    next.cumulative_counts.rebase()

                if next.hash not in self.paths:
                    self._depth_first(next, results, current_depth+1)
                    node.next.append(next)
                    self.paths.add(next.hash)


            except Exception as e:
                # continue
                print(e)
                traceback.print_exc()
                print("ERRROROR")
                break

        add_time("depth_first", start)

    def _get_fair_lineups(self, node: LineupNode, lineups: List[Inning], minimum: float = 0.0):
        start = time.time()
        fair_lineups = []

        counts_items = list(node.cumulative_counts.counter.items())
        first_key, first_val = counts_items[0]
        rest_items = counts_items[1:]

        fairness = self.fairness

        #
        # Determine which lineups are 'fair' for this inning
        # and add them to the list. 
        #
        for lineup in lineups:

            if lineup.strength < minimum:
                # print("Weak, breaking")
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

        # print("Fair lineups found", len(fair_lineups), node.cumulative_counts.counter)

        add_time("get_fair_lineups", start)

        return fair_lineups
    
    def _minimum_viable_score(self, node: LineupNode, current_depth):
  
        start = time.time()

        goal = self.best_score
        lower_bound = self.min_lineup.strength
        upper_bound = self.max_lineup.strength
        max_depth = self.config.number_innings

        remaining = max_depth - current_depth

        strengths = [node.lineup.strength]
        prev = node.prev
        while prev and prev.lineup:
            strengths.append(prev.lineup.strength)
            prev = prev.prev


        for ideal_value in frange(lower_bound, upper_bound, 0.5):
            new_strengths: List[float] = strengths + [ideal_value]*remaining

            mean = statistics.mean(new_strengths)
            stddev = statistics.pstdev(new_strengths)

            score = mean - stddev*self.sigma_weight

            if score > goal: 
                return ideal_value

        add_time("minimum_viable_score", start)
        return float('inf')

            


