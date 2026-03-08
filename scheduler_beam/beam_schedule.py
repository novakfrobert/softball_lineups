import traceback
from types import TracebackType
from typing import Any, List, Set

from scheduler.play_counter import PlayCounter
from scheduler_beam.beam_inning import Inning, LineupNode
from services.position_service import get_positions
from softball_models.player import Player

from softball_models.schedule import Schedule
from softball_models.schedule_config import ScheduleConfig

from utils.math import get_percentile_item
from utils.timing import add_time, print_times

import time
import math

########################################
# Lineup
########################################


def sort_lineups(lineups: List[Inning]):
    lineups.sort(key = lambda l: -1*l.strength)


def get_all_lineups_by_score(
    available_players: List["Player"],
    min_females: int):

    from itertools import combinations
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    positions = get_positions(len(available_players), allow_not_enough=True)

    num_positions = len(positions)
    num_players = len(available_players)

    print("Number positions, number players", num_positions, num_players)

    lineups = []

    max_score = sum(10 * pos.weight for pos in positions)

    # Try only valid player subsets of correct size and enough females
    for subset in combinations(available_players, r=num_positions):

        if sum(p.female for p in subset) < min_females:
            continue

        default_strength = -1e9
        score_matrix = np.full((num_players, num_positions), default_strength) 

        for i, player in enumerate(subset):
            for j, pos in enumerate(positions):
                if pos in player.positions:
                    strength = player.positions_stengths.get(pos, 0)
                    weight = pos.weight
                    score_matrix[i][j] = strength * weight

        row_ind, col_ind = linear_sum_assignment(-score_matrix)

        matched_scores = score_matrix[row_ind, col_ind]
        valid_scores = matched_scores[matched_scores >= 0]

        if max_score:
            score = round(100*valid_scores.sum() / max_score, 1)

        inning = Inning()
        inning.id = len(lineups)
        inning.strength = score

        for i, j in zip(row_ind, col_ind):
            player = subset[i]
            position = positions[j]
            inning.playing_ids.add(player.id)
            inning.field[position] = player

        for p in available_players:
            if p.id not in inning.playing_ids:
                inning.bench[p.id] = p

        lineups.append(inning)

    sort_lineups(lineups)
    return lineups

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

        self.late_lineups: List[Inning] = get_all_lineups_by_score(self.all_players, config.females_required)
        self.early_lineups: List[Inning] = get_all_lineups_by_score(self.early_players, config.females_required)

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
        print("number lineups", len(self.late_lineups))

        leaf_nodes: List[LineupNode] = []
        self._depth_first(root, leaf_nodes)
        print("number of lineups created:", len(leaf_nodes))
        
        #
        # A leaf node represents the final lineup
        # Sort the leaf nodes by their strength, weighted by sigma (standard deviation between innings)
        # This should favor strong lineups that have low inning to inning deviation
        #
        leaf_nodes.sort(key=lambda node : -1*node.cumulative_strength/(node.sigma/2))

        schedule = Schedule()
        schedule.players = self.all_players
        schedule.config = self.config
        schedule.positions = get_positions(len(self.all_players), allow_not_enough=True)


        #
        # Get the top lineup
        # This should be a strong lineup that has low standard deviation
        #
        node = leaf_nodes[0]
        end_node = node

        print(node.cumulative_strength/6)

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

        print(end_node.cumulative_strength/self.config.number_innings)
        print(end_node.sigma)

        return schedule
    
    def _get_lineups(self, inning):
        if self.config.inning_of_late_arrivals <= inning:
            return self.late_lineups
        else:
            return self.early_lineups
        
    def _score(self, node: LineupNode):
        return node.mean - node.sigma*self.sigma_weight
 
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
            ideal_mean = node.projected_ideal_mean(lineups[-1].strength, lineups[0].strength, self.sigma_weight)
            minimum_viable_score = node.minimum_viable_score(self.config.number_innings, current_depth, ideal_mean, self.best_score)
            # minimum_viable_score = self._minimum_viable_score(node, current_depth)

        # print("best score", self.best_score, "current_score", node.lineup.strength, "lineups:", lineups[-1].strength, lineups[0].strength, "  minimum:", minimum_viable_score, "  depths:", max_depth, current_depth)

        fair_lineups = self._get_fair_lineups(node, lineups, minimum_viable_score)

        if not fair_lineups:
            # print("No fair lineups")
            return

        percentiles = [0, 0.05, 0.02, 0.01, 0.005, 0.001, 0.0005, 0.00001] 
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

        # print("Fair lineups found", len(fair_lineups), print(node.cumulative_counts))

        add_time("get_fair_lineups", start)

        return fair_lineups
    
    # def _projected_ideal_mean(self, node: LineupNode):
    #     start = time.time()

    #     ideal_mean = (self.max_lineup.strength + node.mean*self.sigma_weight) / (self.sigma_weight + 1)
    #     ideal_mean = clamp(ideal_mean, self.min_lineup.strength, self.max_lineup.strength)

    #     add_time("projected_ideal_mean", start)

    #     # print(self.min_lineup.strength, self.max_lineup.strength)

    #     return ideal_mean

    # def _minimum_viable_score(self, node: LineupNode, current_depth):
    #     ##
    #     # Create a minimum strength needed from the next lineup for this traversal to be viable
    #     #
    #     #  Given we've likely identified a best score thus far, a max depth, and a sigma weight:
    #     #  y             = best_score 
    #     #  n             = max_depth
    #     #  w             = sigma_weight
    #     #
    #     #  And our scoring function looks like:
    #     #  y             = mean - sigma_weight * updated_sigma
    #     #
    #     #  We can calculate our best case score at depth (max_depth - 1)
    #     #  and then decide what value, x, to add so we don't fall below our best score
    #     #  mean = (total(n-1) + x) / n
    #     #
    #     #  Sigma can be updated following the formula:
    #     #  Where SSD is the sum of squares SUM((xi - old_mean)^2)
    #     #  updated_sigma = sqrt(1/n * (ssd + (x - old_mean)*(x - new_mean))
    #     #  
    #     # Therefore:
    #     #  y  = (total(n-1) + x) / n - w * sqrt(1/n * (ssd + (x-p/(n-1)) * (x-(p+x)/n)))
    #     #
    #     #  When solving for x, this simplifies to a form of the quadratic formula, for which
    #     #  we will take the lower of the two numbers.
    #     #  
    #     ##
    #     start = time.time()

    #     goal = self.best_score
    #     ideal_mean = self._projected_ideal_mean(node)
    #     max_depth = self.config.number_innings

    #     # print("ideal", ideal_mean)
    #     # print("max depth", max_depth, "current_depth", current_depth)
    #     remaining = max_depth - current_depth
    #     # print("remaining", remaining)

    #     strengths: List[float] = [node.lineup.strength] + [ideal_mean]*remaining
    #     # print("stregnths1", strengths)

    #     prev = node.prev
    #     while prev and prev.lineup:
    #         strengths.append(prev.lineup.strength)
    #         prev = prev.prev

    #     # print("stregnths2", strengths)
        
    #     cumulative = node.cumulative_strength + remaining*ideal_mean
    #     # print("cumulative", cumulative)

    #     mean_0 = cumulative/(max_depth-1)
    #     # print("mean_0", mean_0)

    #     s = 0
    #     for i in range(max_depth - 1):
    #         s += (strengths[i] - mean_0)**2

    #     w = self.sigma_weight
    #     n = max_depth
    #     p = cumulative
    #     y = goal

    #     w2 = w**2
    #     nw2 = n * w2
    #     a = nw2 - w2 - 1

    #     b = 2*n*y - 2*p*w2 - 2*p
    #     c = -n**2*y**2 - (p**2*w2)/(1 - n) + 2*n*p*y + n*s*w2 - p**2

    #     discriminant = b**2 - 4 * a * c

    #     # print(discriminant, max_depth, current_depth, cumulative, goal, ideal_mean)
        
    #     res = (-math.sqrt(discriminant) - b) / (2 * a)
    #     add_time("minimum_viable_score", start)

    #     return res


#
# TODO: Funcs below here could likely be moved to a utils/common space
#


def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))
     
def get_late_players(players: List[Player]):
    return [p for p in players if p.available and p.late]

def get_early_players(players: List[Player]):
    return [p for p in players if p.available and not p.late]


