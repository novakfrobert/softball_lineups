import traceback
from types import TracebackType
from typing import Any, Dict, List, Self, Set, Tuple

from softball_positions import Position, get_positions
from softball_player import Player
import statistics

from softball_schedule import ScheduleConfig

import time
import hashlib
import math


###########################
# Timing helper
###########################

times = {}
calls = {}

existing_paths = set()

def add_time(key, start):
    if key not in times:
        times[key] = 0
        calls[key] = 0
    times[key] += time.time() - start
    calls[key] += 1

###########################
# Beam Schedule
###########################

best_score: int = 0
g_players = []

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

class LineupNode:
    lineup: Lineup | None
    sigma: float
    ssd: float
    mean: float
    cumulative_strength: float
    cumulative_counts: Dict[str, int] # key is player name
    prev: Self
    next: List[Self]
    beam_width: int
    depth: int
    hash: str

    def __repr__(self):
        return f"Depth:{self.depth}  Strength:{self.cumulative_strength}  Counts:{self.cumulative_counts},  Sigma{self.sigma}"

    @staticmethod
    def root(beam_width):
        root = LineupNode(beam_width, None, None)
        root.hash = 0
        root.depth = 0
        root.sigma = 0
        root.ssd = 0
        root.mean = 0
        root.cumulative_strength = 0

        root.cumulative_counts = {}
        global g_players
        for player in g_players:
            if player.id not in root.cumulative_counts:
                root.cumulative_counts[player.id] = 0

        return root

    def __init__(self, beam_width, lineup: Lineup, prev: Self):
        start = time.time()
        self.beam_width = beam_width
        self.lineup = lineup
        self.prev = prev
        self.next = []

        if prev:
            self.depth = prev.depth + 1
            self.sigma = self._compute_sigma()
            self.cumulative_counts = self._compute_counts()
            self.cumulative_strength = prev.cumulative_strength + lineup.strength
            self.mean = self.cumulative_strength / self.depth
            self.ssd = (lineup.strength - self.mean)*(lineup.strength - prev.mean) + prev.ssd
            self.score = self._score(self.depth, 2.0)
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

    def _compute_counts(self):
        counts = self.prev.cumulative_counts.copy()
        update_counts(counts, self.lineup, 1)
        return counts

    def _compute_sigma(self):
        node: LineupNode = self.prev
        strengths = [self.lineup.strength]
        while node and node.lineup:
            strengths.append(node.lineup.strength)
            node = node.prev
        return statistics.pstdev(strengths)
    
    def _score(self, depth: int, sigma_weight: float):
        return self.mean - self.sigma*sigma_weight
    
    def projected_ideal_mean(self, min_lineup: float, max_lineup: float, sigma_weight: float):
        start = time.time()

        ideal_mean = (max_lineup + self.mean*sigma_weight) / (sigma_weight + 1)
        ideal_mean = clamp(ideal_mean, min_lineup, max_lineup)

        add_time("projected_ideal_mean", start)

        return ideal_mean

    def projected_ideal_score(self, max_depth: int, depth: int, min_lineup: float, max_lineup: float, sigma_weight: float):
        start = time.time()

        ideal_mean = self.projected_ideal_mean(min_lineup, max_lineup, sigma_weight)

        remaining = max_depth - depth

        # TODO deduplicate with _compute_sigma
        strengths = [self.lineup.strength] + [ideal_mean]*remaining
        node = self.prev
        while node and node.lineup:
            strengths.append(node.lineup.strength)
            node = node.prev

        proj_sigma = statistics.pstdev(strengths)
        proj_cumulative = self.cumulative_strength + remaining*ideal_mean

        res = (proj_cumulative/max_depth) - sigma_weight*proj_sigma

        add_time("projected_ideal_score", start)
        return res


    def depth_first(self, results: List[Any], lineups: List[Lineup], fair_factor: int, max_depth: int, current_depth: int = 0):
        global best_score
        start = time.time()

        if current_depth == max_depth:
            # we have a leaf node
            results.append(self)
            if best_score <= self.score:
                best_score = self.score
            return
        
        # if current_depth != 0 and self.projected_ideal_score(max_depth, current_depth, lineups[-1].strength, lineups[0].strength, 2.0) <= best_score:
        #     # if projected score is not better than current best, dont continue this path
        #     return
        
        result = 0
        if current_depth != 0 and best_score != 0:
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
            #
            #  
            ##
            
            ideal_mean = self.projected_ideal_mean(lineups[-1].strength, lineups[0].strength, 2.0)

            remaining = max_depth - current_depth - 1

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
            y = best_score

            w2 = w**2
            nw2 = n * w2
            a = nw2 - w2 - 1

            b = 2*n*y - 2*p*w2 - 2*p
            c = -n**2*y**2 - (p**2*w2)/(1 - n) + 2*n*p*y + n*s*w2 - p**2

            discriminant = b**2 - 4 * a * c
            
            result = (-math.sqrt(discriminant) - b) / (2 * a)

        fair_lineups = get_fair_lineups(self.cumulative_counts, lineups, fair_factor, result)

        percentiles = [0, 0.05, 0.03, 0.01]
        for percentile in percentiles:
            try:
                lineup = get_percentile_item(fair_lineups, percentile)
                next = LineupNode(self.beam_width, lineup, self)
                if next.hash not in existing_paths:
                    next.depth_first(results, lineups, fair_factor, max_depth, current_depth+1)
                    self.next.append(next)
                    existing_paths.add(next.hash)


            except Exception as e:
                break
                # continue
                #traceback.print_exc()
                #print("No fair lineups found.")

        add_time("depth_first", start)


    
    def choose_next(self, lineups: List[Lineup], fair_factor: int):

        start = time.time()
        fair_lineups = get_fair_lineups(self.cumulative_counts, lineups, fair_factor)

        add_time("choose_next_create_fair_list", start)
        
        # print(len(fair_lineups))

        # TODO: Do we really need to sort here?
        # sort_lineups(fair_lineups)

        # 
        # Get the items at specific percentiles
        # this limits the growth of our lineup tree.
        # The goal is to get the best, and near best lineups
        # because a greedy approach might not result in the best overall game plan.
        # 

        # percentiles = [0, 0.05, 0.1, 0.15, 0.2, 0.3]
        percentiles = [0, 0.05, 0.03, 0.01]
        for percentile in percentiles:
            try:
                lineup = get_percentile_item(fair_lineups, percentile)
                next = LineupNode(self.beam_width, lineup, self)
                if next.hash not in existing_paths:
                    self.next.append(next)
                    existing_paths.add(next.hash)
            except Exception as e:
                print(e.with_traceback())
                print("No fair lineups found.")

        add_time("choose_next_total", start)

class BeamSchedule:
    fairness: int
    beam_width: int

    @staticmethod
    def create(beam_width, fair_factor, players: List[Player], config: ScheduleConfig):
        global existing_paths
        global g_players
        global times
        global calls
        global best_score
        best_score = 0

        times = {}
        calls = {}

        g_players = players

        existing_paths = set()

        start = time.time()
        print("create", players)

        root = LineupNode.root(beam_width)
        late_players = get_late_players(players)
        available_players = get_available_players(players)
        all_lineups = get_all_lineups_by_score(late_players + available_players, get_positions(config.players_required), config.females_required)
        early_lineups = get_all_lineups_by_score(available_players, get_positions(config.players_required), config.females_required)

        print("creating tree....")
        print("number lineups", len(all_lineups))

        #
        # Should create n_percentiles ^ n_innings number of leaf nodes
        #
        # node: LineupNode | None = None
        # next_nodes: List[LineupNode] = [root]
        # leaf_nodes: List[LineupNode] = []
        # while next_nodes:
        #     node = next_nodes.pop()

        #     if node.depth >= config.number_innings:
        #         leaf_nodes.append(node)
        #         continue

        #     node.choose_next(all_lineups, fair_factor)

        #     next_nodes += node.next

        leaf_nodes: List[LineupNode] = []
        root.depth_first(leaf_nodes, all_lineups, fair_factor, config.number_innings)
        
        #
        # A leaf node represents the final lineup
        # Sort the leaf nodes by their strength, weighted by sigma (standard deviation between innings)
        # This should favor strong lineups that have low inning to inning deviation
        #
        leaf_nodes.sort(key=lambda node : -1*node.cumulative_strength/(node.sigma/2))
        print("number of lineups created:", len(leaf_nodes))

        # best_lineups = sorted(leaf_nodes[:3], key=lambda node : -1*node.cumulative_strength)

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
        print(times)
        print(calls)

        print(end_node.cumulative_strength/config.number_innings)
        print(end_node.sigma)
        print(end_node.cumulative_counts)

def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))
     
def get_late_players(players: List[Player]):
    return [p for p in players if p.late]

def get_available_players(players: List[Player]):
    return [p for p in players if p.available and not p.late]

def update_counts(counts: Dict[str, int], lineup: Lineup, inc: int):
    start = time.time()
    for player in lineup.playing:
        if player.id not in counts:
            counts[player.id] = 0
        counts[player.id] += inc
    add_time("update_counts", start)

def is_fair(counts: Dict[str, int], fair_factor: int):
    """
    A lineup is fair if the least played player and most played player disparity is less or equal to fair factor
    """
    start = time.time()
    max_count = max(counts.values())
    min_count = min(counts.values())
    res = (max_count - min_count) <= fair_factor
    add_time("is_fair", start)

    return res

def get_fair_lineups(counts: Dict[str, int],  lineups: List[Lineup], fair_factor: int, minimum: float = 0.0):
    start = time.time()
    fair_lineups = []

    #
    # Determine which lineups are 'fair' for this inning
    # and add them to the list. 
    #
    for lineup in lineups:

        if lineup.strength < minimum:
            # print("too weak, breaking", minimum, " on i ", i, " of ", len(lineups))
            break


        fair = True
        it = iter(counts.items())
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

            if max - min > fair_factor:
                # print("unfair!")
                fair = False
                break

        

        # pre = time.time()



        # Update all the innings played counts by 1 for each player in the linup
        # determine if it is fair
        # and reset the state for the next check.

        #
        # TODO: This is slowing down a lot as n_innings or n_players scales or n_percentiles
        # Contents of this for loop are (called n_percentiles ^ n_innings) * n_lineups
        # and n_linups scales with n_players.
        #

        # if lineup.strength < minimum:
        #     # print("too weak, breaking", minimum, " on i ", i, " of ", len(lineups))
        #     break

        
        # for player in lineup.playing:
        #     counts[player.id] += 1

        # # update_counts(counts, lineup, 1)

        # # max_count = 
        # # min_count = 
        # add_time("get_fair_lineups_pre", pre)

        # it = iter(counts.values())
        # first = next(it)

        # min = first
        # max = first
        # fair = True

        # for count in it:

        #     if 

        #     if count < min:
        #         min = count

        #     elif count > max:
        #         max = count

        #     if max - min > fair_factor:
        #         fair = False
        #         break
        
        # # fair = (max(counts.values()) - min(counts.values())) <= fair_factor
        # # fair = is_fair(counts, fair_factor)
        # # update_counts(counts, lineup, -1)

        # for player in lineup.playing:
        #     counts[player.id] -= 1

        if fair:
            fair_lineups.append(lineup)

    add_time("get_fair_lineups", start)

    return fair_lineups

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


def sort_lineups(lineups: List[Lineup]):
    lineups.sort(key = lambda l: -1*l.strength)


def get_all_lineups_by_score(
    available_players: List["Player"],
    positions: List[Position],
    min_females: int):

    from itertools import combinations
    import numpy as np
    from scipy.optimize import linear_sum_assignment

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


def solve_quadratic(a, b, c):
    if a == 0:
        raise ValueError("Not a quadratic equation")

    d = b*b - 4*a*c

    print("d", d)

    if d < 0:
        sqrt_d = math.sqrt(-d) * 1j
    else:
        sqrt_d = math.sqrt(d)

    q = -0.5 * (b + math.copysign(sqrt_d, b))
    x1 = q / a
    x2 = c / q

    return x1, x2
