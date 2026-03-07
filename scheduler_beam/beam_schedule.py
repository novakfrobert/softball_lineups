import traceback
from types import TracebackType
from typing import Any, List, Set

from scheduler_beam.beam_inning import Inning, LineupNode
from softball_models.positions import get_positions
from softball_models.player import Player

from softball_models.schedule_config import ScheduleConfig

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


        # TODO get_all_lineups_by_score could take num players, females required, and list of players
        #      and it needs to be able to handle if not enough players are provided
        self.late_lineups: List[Inning] = get_all_lineups_by_score(self.late_players + self.early_players, config.females_required)
        self.early_lineups: List[Inning] = get_all_lineups_by_score(self.early_players, config.females_required)

        self.best_score: float = 0
        self.paths: Set[Any] = set()


    @staticmethod
    def create(sigma_weight: float, fairness_index: int, players: List[Player], config: ScheduleConfig):

        start = time.time()

        scheduler = BeamScheduler(sigma_weight, fairness_index, players, config)
        scheduler.schedule()

    def schedule(self):

        start = time.time()
        print("create", self.players)

        root = self._root()
      

        print("creating tree....")
        print("number lineups", len(self.late_lineups))


        leaf_nodes: List[LineupNode] = []
        self._depth_first(root, leaf_nodes)
        
        #
        # A leaf node represents the final lineup
        # Sort the leaf nodes by their strength, weighted by sigma (standard deviation between innings)
        # This should favor strong lineups that have low inning to inning deviation
        #
        leaf_nodes.sort(key=lambda node : -1*node.cumulative_strength/(node.sigma/2))
        print("number of lineups created:", len(leaf_nodes))


        #
        # Get the top lineup
        # This should be a strong lineup that has low standard deviation
        #
        node = leaf_nodes[0]
        end_node = node

        print(node.cumulative_strength/6)
        print(node.sigma)
        print(node.cumulative_counts)

        i = 0
        while node and node.lineup:
            print()
            i += 1
            print(i)
            print(node.lineup.strength)
            print(node.lineup.field)
            node = node.prev

        end = time.time()
        print("Beam Schedule took: ", end - start, " seconds.")
        print_times()

        print(end_node.cumulative_strength/self.config.number_innings)
        print(end_node.sigma)
        print(end_node.cumulative_counts)

    def _root(self):
        root = LineupNode(None, None)
        root.hash = 0
        root.depth = 0
        root.sigma = 0
        root.ssd = 0
        root.mean = 0
        root.cumulative_strength = 0

        root.cumulative_counts = {}
        players = self.early_players + self.late_players
        for player in players:
            if player.id not in root.cumulative_counts:
                root.cumulative_counts[player.id] = 0
        return root
    
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


        max_depth = self.config.number_innings

        if current_depth > max_depth:
            # we have a leaf node
            results.append(node)
            score = self._score(node)
            if self.best_score <= node.score:
                self.best_score = node.score
            return
        
        minimum_viable_score = 0
        if current_depth > 1 and self.best_score != 0:
            
            ideal_mean = node.projected_ideal_mean(lineups[-1].strength, lineups[0].strength, 2.0)
            minimum_viable_score = node.minimum_viable_score(max_depth, current_depth, ideal_mean, self.best_score)

        # print("best score", self.best_score, "current_score", node.lineup.strength, "lineups:", lineups[-1].strength, lineups[0].strength, "  minimum:", minimum_viable_score, "  depths:", max_depth, current_depth)


        fair_lineups = self._get_fair_lineups(node, lineups, minimum_viable_score)

        if not fair_lineups:
            # print("No fair lineups")
            return

        percentiles = [0, 0.05, 0.03, 0.01]
        for percentile in percentiles:
            try:
                lineup = get_percentile_item(fair_lineups, percentile)
                next = LineupNode(lineup, node)

                if current_depth == self.config.inning_of_late_arrivals:
                    next.rebase_counts()

                if next.hash not in self.paths:
                    self._depth_first(next, results, current_depth+1)
                    node.next.append(next)
                    self.paths.add(next.hash)


            except Exception as e:
                # continue
                # print(e)
                # traceback.print_exc()
                # print("ERRROROR")
                break

        add_time("depth_first", start)

    def _get_fair_lineups(self, node: LineupNode,  lineups: List[Inning], minimum: float = 0.0):
        start = time.time()
        fair_lineups = []

        #
        # Determine which lineups are 'fair' for this inning
        # and add them to the list. 
        #
        for lineup in lineups:

            if lineup.strength < minimum:
                # print("Weak, breaking")
                break

            fair = True
            it = iter(node.cumulative_counts.items())
            first_key, first_val = next(it)

            first_it_inc = 0
            if first_key in lineup.playing_ids:
                first_it_inc = 1

            min = first_val + first_it_inc
            max = first_val + first_it_inc

            for id, count in it:
                if id in lineup.playing_ids:
                    count += 1

                if count < min:
                    min = count
                elif count > max:
                    max = count

                if max - min > self.fairness:
                    fair = False
                    break

            if fair:
                fair_lineups.append(lineup)

        # print("Fair lineups found", len(fair_lineups), print(node.cumulative_counts))

        add_time("get_fair_lineups", start)

        return fair_lineups

#
# TODO: Funcs below here could likely be moved to a utils/common space
#

def solve_quadratic(a, b, c):
    if a == 0:
        raise ValueError("Not a quadratic equation")

    d = b*b - 4*a*c

    # print("d", d)

    if d < 0:
        sqrt_d = math.sqrt(-d) * 1j
    else:
        sqrt_d = math.sqrt(d)

    q = -0.5 * (b + math.copysign(sqrt_d, b))
    x1 = q / a
    x2 = c / q

    return x1, x2

def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))
     
def get_late_players(players: List[Player]):
    return [p for p in players if p.available and p.late]

def get_early_players(players: List[Player]):
    return [p for p in players if p.available and not p.late]


def get_percentile_item(lst, percentile: float):
    """
    Selects the item at the given percentile from a descending-sorted list.

    Args:
        lst: A list of items sorted in descending order (best item first).
        percentile: A float between 0.0 (top) and 1.0 (bottom), e.g., 0.2 for top 20%.

    Returns:
        The item at the given percentile index.
    """
    start = time.time()
    if not lst:
        raise ValueError("List is empty")
    

    percentile = max(0.0, min(1.0, percentile))  # Clamp between 0 and 1

    index = int(percentile * (len(lst) - 1))

    add_time("get_percentile_item", start)
    return lst[index]