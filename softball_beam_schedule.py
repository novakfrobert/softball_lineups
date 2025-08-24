from typing import Dict, List, Self, Tuple

from softball_positions import Position, get_positions
from softball_player import Player
import statistics

from softball_schedule import ScheduleConfig

class Lineup:
    field: Dict[str, Player]
    sitting: List[Player]
    playing: List[Player]
    late: List[Player]
    strength: float

    def __init__(self):
        self.field = {}
        self.sitting = []
        self.playing = []
        self.late = []
        self.strength = 0

class LineupNode:
    lineup: Lineup | None
    sigma: float
    cumulative_strength: float
    cumulative_counts: Dict[str, int] # key is player name
    prev: Self
    next: List[Self]
    beam_width: int
    depth: int

    def __repr__(self):
        return f"Depth:{self.depth}  Strength:{self.cumulative_strength}  Counts:{self.cumulative_counts},  Sigma{self.sigma}"

    @staticmethod
    def root(beam_width):
        root = LineupNode(beam_width, None, None)
        root.depth = 0
        root.sigma = 0
        root.cumulative_strength = 0
        root.cumulative_counts = {}
        return root

    def __init__(self, beam_width, lineup: Lineup, prev: Self):
        self.beam_width = beam_width
        self.lineup = lineup
        self.prev = prev
        self.next = []

        if prev:
            self.depth = prev.depth + 1
            self.sigma = self._compute_sigma()
            self.cumulative_counts = self._compute_counts()
            self.cumulative_strength = prev.cumulative_strength + lineup.strength

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
    
    def choose_next(self, lineups: List[Lineup], fair_factor: int):

        fair_lineups = []

        for lineup in lineups:

            update_counts(self.cumulative_counts, lineup, 1)
            fair = is_fair(self.cumulative_counts, fair_factor)
            update_counts(self.cumulative_counts, lineup, -1)

            if fair:
                fair_lineups.append(lineup)

        sort_lineups(fair_lineups)

        # percentiles = [0, 0.05, 0.1, 0.15, 0.2, 0.3]
        percentiles = [0, 0.05, 0.03, 0.01]
        for percentile in percentiles:
            lineup = get_percentile_item(fair_lineups, percentile)
            self.next.append(LineupNode(self.beam_width, lineup, self))

class BeamSchedule:
    fairness: int
    beam_width: int

    @staticmethod
    def create(beam_width, fair_factor, players: List[Player], config: ScheduleConfig):
        print("create", players)
        root = LineupNode.root(beam_width)
        late_players = get_late_players(players)
        available_players = get_available_players(players)
        all_lineups = get_all_lineups_by_score(late_players + available_players, get_positions(config.players_required), config.females_required)
        early_lineups = get_all_lineups_by_score(available_players, get_positions(config.players_required), config.females_required)

        node: LineupNode | None = None
        next_nodes: List[LineupNode] = [root]
        leaf_nodes: List[LineupNode] = []
        while next_nodes:
            node = next_nodes.pop()

            if node.depth >= config.number_innings:
                leaf_nodes.append(node)
                print(len(leaf_nodes))
                continue

            node.choose_next(all_lineups, fair_factor)

            next_nodes += node.next

        leaf_nodes.sort(key=lambda node : -1*node.cumulative_strength/(node.sigma/2))

        # step = len(leaf_nodes)/20.0
        # for n in range(20):
        #     node = leaf_nodes[int(n*step)]
        #     print(n)
        #     print(node.cumulative_strength/6)
        #     print(node.sigma)
        #     print()
        #     print()
        #     print()

        print("leaf nodes", len(leaf_nodes))

        # best_lineups = sorted(leaf_nodes[:3], key=lambda node : -1*node.cumulative_strength)

        i = 0
        node = leaf_nodes[0]
        print(node.cumulative_strength/6)
        print(node.sigma)
        print(node.cumulative_counts)
        while node and node.lineup:
            print()
            i += 1
            print(i)
            print(node.lineup.strength)
            print(node.lineup.field)
            node = node.prev
     



def get_late_players(players: List[Player]):
    return [p for p in players if p.late]

def get_available_players(players: List[Player]):
    return [p for p in players if p.available and not p.late]

def update_counts(counts: Dict[str, int], lineup: Lineup, inc: int):
    for player in lineup.playing:
        if player.name not in counts:
            counts[player.name] = 0
        counts[player.name] += inc

def is_fair(counts: Dict[str, int], fair_factor: int):
    max_count = max(counts.values())
    min_count = min(counts.values())
    return (max_count - min_count) <= fair_factor

def get_percentile_item(lst, percentile: float):
    """
    Selects the item at the given percentile from a descending-sorted list.

    Args:
        lst: A list of items sorted in descending order (best item first).
        percentile: A float between 0.0 (top) and 1.0 (bottom), e.g., 0.2 for top 20%.

    Returns:
        The item at the given percentile index.
    """
    if not lst:
        raise ValueError("List is empty")

    percentile = max(0.0, min(1.0, percentile))  # Clamp between 0 and 1
    index = int(percentile * (len(lst) - 1))
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

        lineup = Lineup()
        lineup.strength = score
        for i, j in zip(row_ind, col_ind):
            player = subset[i]
            position = positions[j]
            lineup.playing.append(player)
            lineup.field[position] = player

        for p in available_players:
            if p not in lineup.playing:
                lineup.sitting.append(p)

        lineups.append(lineup)

    sort_lineups(lineups)
    return lineups
