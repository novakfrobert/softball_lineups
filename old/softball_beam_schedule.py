import traceback
from types import TracebackType
from typing import Any, Dict, List, Self, Set, Tuple

from softball_models.positions import Position, get_positions
from softball_models.player import Player
import statistics

from softball_models.schedule_config import ScheduleConfig

from utils.timing import add_time, print_times

import time
import hashlib
import math

########################################
# Lineup
########################################

class Lineup:
    field: Dict[str, Player]
    sitting: List[Player]
    playing: List[Player]
    playing_ids: Set[Player]
    late: List[Player]
    strength: float
    id: int

    def __init__(self, id):
        self.field = {}
        self.sitting = []
        self.playing = []
        self.playing_ids = set()
        self.late = []
        self.strength = 0
        self.id = id


def sort_lineups(lineups: List[Lineup]):
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

        lineup = Lineup(len(lineups))
        lineup.strength = score
        for i, j in zip(row_ind, col_ind):
            player = subset[i]
            position = positions[j]
            lineup.playing.append(player)
            lineup.playing_ids.add(player.id)
            lineup.field[position] = player

        for p in available_players:
            if p not in lineup.playing:
                lineup.sitting.append(p)

        lineups.append(lineup)

    sort_lineups(lineups)
    return lineups

########################################
# LineupNode
########################################

class LineupNode:
    lineup: Lineup | None
    sigma: float
    ssd: float
    mean: float
    cumulative_strength: float
    cumulative_counts: Dict[str, int] # key is player name
    prev: Self
    next: List[Self]
    depth: int
    hash: str

    def __repr__(self):
        return f"Depth:{self.depth}  Strength:{self.cumulative_strength}  Counts:{self.cumulative_counts},  Sigma{self.sigma}"

    def __init__(self, lineup: Lineup, prev: Self):
        start = time.time()
        self.lineup = lineup
        self.prev = prev
        self.next = []

        if prev:
            self.depth = prev.depth + 1
            self.sigma = self._compute_sigma()
            self.cumulative_counts = self._increment_counts()
            self.cumulative_strength = prev.cumulative_strength + lineup.strength
            self.mean = self.cumulative_strength / self.depth
            self.ssd = (lineup.strength - self.mean)*(lineup.strength - prev.mean) + prev.ssd
            self.hash = self._hash()

        add_time("lineup node ctor", start)

    def _hash(self):
        start = time.time()
        ids = []
        node: LineupNode | None = self
        while node.lineup is not None:
            ids.append(str(node.lineup.id))
            node = node.prev

        ids.sort()
        ids_str = " ".join(ids)
        hash = hashlib.sha256(ids_str.encode()).hexdigest()
        add_time("lineup node hash", start)
        return hash

    def _increment_counts(self):
        counts = self.prev.cumulative_counts.copy()
        for player in self.lineup.playing:
            if player.id not in counts:
                counts[player.id] = 0
            counts[player.id] += 1
        return counts

    def _compute_sigma(self):
        node: LineupNode = self.prev
        strengths = [self.lineup.strength]
        while node and node.lineup:
            strengths.append(node.lineup.strength)
            node = node.prev
        return statistics.pstdev(strengths)
    
    def rebase_counts(self):
        minimum_value = min(self.cumulative_counts.values())
        for key in self.cumulative_counts.keys():
            self.cumulative_counts[key] -= minimum_value

    
    def projected_ideal_mean(self, min_lineup: float, max_lineup: float, sigma_weight: float):
        start = time.time()

        ideal_mean = (max_lineup + self.mean*sigma_weight) / (sigma_weight + 1)
        ideal_mean = clamp(ideal_mean, min_lineup, max_lineup)

        add_time("projected_ideal_mean", start)

        return ideal_mean

    def minimum_viable_score(self, max_depth, current_depth, ideal_mean, goal):
        ##
        # Create a minimum strength needed from the next lineup for this traversal to be viable
        #
        #  Given we've likely identified a best score thus far, a max depth, and a sigma weight:
        #  y             = best_score 
        #  n             = max_depth
        #  w             = sigma_weight
        #
        #  And our scoring function looks like:
        #  y             = mean - sigma_weight * updated_sigma
        #
        #  We can calculate our best case score at depth (max_depth - 1)
        #  and then decide what value, x, to add so we don't fall below our best score
        #  mean = (total(n-1) + x) / n
        #
        #  Sigma can be updated following the formula:
        #  Where SSD is the sum of squares SUM((xi - old_mean)^2)
        #  updated_sigma = sqrt(1/n * (ssd + (x - old_mean)*(x - new_mean))
        #  
        # Therefore:
        #  y  = (total(n-1) + x) / n - w * sqrt(1/n * (ssd + (x-p/(n-1)) * (x-(p+x)/n)))
        #
        #  When solving for x, this simplifies to a form of the quadratic formula, for which
        #  we will take the lower of the two numbers.
        #  
        ##
        start = time.time()

        remaining = max_depth - current_depth

        strengths = [self.lineup.strength] + [ideal_mean]*remaining
        node = self.prev
        while node and node.lineup:
            strengths.append(node.lineup.strength)
            node = node.prev

        cumulative = self.cumulative_strength + remaining*ideal_mean
        mean_0 = cumulative/(max_depth-1)
        s = 0
        for i in range(max_depth - 1):
            s += (strengths[i] - mean_0)**2

        w = 2.0
        n = max_depth
        p = cumulative
        y = goal

        w2 = w**2
        nw2 = n * w2
        a = nw2 - w2 - 1

        b = 2*n*y - 2*p*w2 - 2*p
        c = -n**2*y**2 - (p**2*w2)/(1 - n) + 2*n*p*y + n*s*w2 - p**2

        discriminant = b**2 - 4 * a * c
        
        res = (-math.sqrt(discriminant) - b) / (2 * a)
        add_time("minimum_viable_score", start)

        return res


########################################
# Schedule - Our tree of possible linups
########################################
    
class BeamSchedule:

    fairness: int
    players: List[Player]
    late_players: List[Player]
    early_players: List[Player]
    best_score: float

    late_lineups: List[Lineup]
    early_lineups: List[Lineup]

    config: ScheduleConfig

    paths: Set[Any]

    sigma_weight: float

    @staticmethod
    def create(sigma_weight: float, fairness_index: int, players: List[Player], config: ScheduleConfig):

        start = time.time()

        schedule = BeamSchedule()
        schedule.config = config
        schedule.players = players
        schedule.fairness = fairness_index

        schedule.late_players = get_late_players(players)
        schedule.early_players = get_early_players(players)

        # TODO get_all_lineups_by_score could take num players, females required, and list of players
        #      and it needs to be able to handle if not enough players are provided
        schedule.late_lineups = get_all_lineups_by_score(schedule.late_players + schedule.early_players, config.females_required)
        schedule.early_lineups = get_all_lineups_by_score(schedule.early_players, config.females_required)

        schedule.best_score = 0
        schedule.paths = set()

        schedule.sigma_weight = sigma_weight


        start = time.time()
        print("create", players)

        root = schedule._root()
      

        print("creating tree....")
        print("number lineups", len(schedule.late_lineups))


        leaf_nodes: List[LineupNode] = []
        schedule._depth_first(root, leaf_nodes)
        
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

        print(end_node.cumulative_strength/config.number_innings)
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

        # print("lineups", len(lineups), "inning", current_depth)

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

            # print("best score", self.best_score, "current_score", node.score, "lineups:", lineups[-1].strength, lineups[0].strength, "  idealmean:", ideal_mean, "  minimum:", minimum_viable_score, "  depths:", max_depth, current_depth)


        fair_lineups = self._get_fair_lineups(node, lineups, current_depth, minimum_viable_score)

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

    def _get_fair_lineups(self, node: LineupNode,  lineups: List[Lineup], inning, minimum: float = 0.0):
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