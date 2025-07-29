from typing import Dict, List, Tuple

from softball_player import Player

class Lineup:
    field: Dict[str, Player]
    sitting: List[Player]
    playing: List[Player]
    late: List[Player]
    score: float
    strength: float

    def __init__(self):
        self.field = {}
        self.sitting = []
        self.playing = []
        self.late = []
        self.score = 0
        self.strength = 0

class Game:
    lineups: List[Lineup]

    def __init__(self):
        self.lineups = []

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
    lineups.sort(key = lambda l: -1*l.score)

def expected_innings(num_innings: int, num_positions: int, num_players: int):
    return num_innings * num_positions / num_players

def beam_schedule(        
        num_innings: int, 
        positions: List[str], 
        players: List[Player],
        # weights: Dict[str, float],
        min_females: int):
    
    score, game_linup =  _beam_schedule(num_innings, positions, players, min_females, 0)
    print(game_linup)

    for i, l in enumerate(game_linup):
        for pos, p in l.field.items():
            p.innings_played += 1
        print(i + 1, "score", l.score, "strength", l.strength, l.field)
        
    
def _beam_schedule(
        num_innings: int, 
        positions: List[str], 
        players: List[Player],
        # weights: Dict[str, float],
        min_females: int,
        current_inning: int):
    
    if current_inning == num_innings:
        return 0, []
    
    weights = {"SS": 100, "P": 100, "C": 5, "LF": 90, "LCF": 90, "3B": 95, "2B": 60, "1B": 70, "CF": 80, "RF": 15, "RCF": 25}
    percentiles = [0, 1]

    available_players = [p for p in players if p.available]

    target_innings_played = expected_innings(current_inning, len(positions), len(available_players))

    available_this_inning = [p for p in available_players if not p.late or current_inning > 2]

    lineups: List[Lineup] = get_all_lineups_by_score(available_this_inning, positions, weights, min_females, target_innings_played)

    new_lineups = []
    best_score = 0
    best_lineup = None

    print("FOR PERCENTILE")
    for percentile in percentiles:
        print("Percentile", percentile)
        lineup: Lineup = get_percentile_item(lineups, percentile)

        print(current_inning, lineup.score, lineup.field)

        for pos, player in lineup.field.items():
            player.innings_played += 1

        score, ret_lineups = _beam_schedule(num_innings, positions, players, min_females, current_inning+1)

        if score >= best_score:
            best_score = score
            new_lineups = [lineup] + ret_lineups
            best_lineup = lineup

        for pos, player in lineup.field.items():
            player.innings_played -= 1

    
    return sum([l.strength for l in new_lineups]), new_lineups
    # print(current_inning, "score", lineups[0].score, "strength", lineups[0].strength, lineups[0].field)


def get_all_lineups_by_score(
    available_players: List["Player"],
    positions: List[str],
    weights: Dict[str, float],
    min_females: int,
    target_innings: float):

    from itertools import combinations
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    num_positions = len(positions)
    num_players = len(available_players)

    # Not enough players or females → fail early
    # if len(available_players) < num_positions:
    #     return [], float('-inf')
    # if sum(p.female for p in available_players) < min_females:
    #     return [], float('-inf')

    lineups = []

    weights = {"SS": 100, "P": 100, "C": 5, "LF": 90, "LCF": 90, "3B": 95, "2B": 60, "1B": 70, "CF": 80, "RF": 15, "RCF": 25}
    weights = {pos: weights[pos] for pos in positions}
    max_score = sum(10 * w for w in weights.values())
    print("MAX SCORE", max_score)

    # weights = {"SS": 100, "P": 100, "C": 5, "LF": 90, "LCF": 90, "3B": 95, "2B": 60, "1B": 70, "CF": 80, "RF": 15, "RCF": 25}

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
                    weight = weights.get(pos, 1.0)
                    penalty = 1000 * (player.innings_played - target_innings)
                    score_matrix[i][j] = strength * weight - penalty

        row_ind, col_ind = linear_sum_assignment(-score_matrix)
        total_score = sum(score_matrix[i, j] for i, j in zip(row_ind, col_ind))

        matched_scores = score_matrix[row_ind, col_ind]
        valid_scores = matched_scores[matched_scores >= 0]

        lineup = Lineup()
        lineup.score = round(100*valid_scores.sum() / max_score, 1)
        lineup.field = {positions[j]: subset[i] for i, j in zip(row_ind, col_ind)}
        lineups.append(lineup)
        
        for i, j in zip(row_ind, col_ind):
            player = subset[i]
            position = positions[j]

            strength = player.positions_stengths.get(position, 0)
            weight = weights.get(position, 1.0)
            lineup.strength += (strength*weight)

        lineup.strength = round(100*lineup.strength / max_score, 1)
        # lineup.overall_score = round(100*valid_scores.sum() / max_score, 1)

    sort_lineups(lineups)
    return lineups

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

def optimize_lineup(
    players: List["Player"],
    positions: List[str],
    weights: Dict[str, float],
    min_females: int = 0,
    innings_weight: float = 0.1
) -> Tuple[List[Tuple["Player", str]], float]:
    
    from itertools import combinations
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    available_players = [p for p in players if p.available]
    num_positions = len(positions)

    # Not enough players or females → fail early
    if len(available_players) < num_positions:
        return [], float('-inf')
    if sum(p.female for p in available_players) < min_females:
        return [], float('-inf')

    best_assignment = []
    best_score = float('-inf')

    # Try only valid player subsets of correct size and enough females
    for subset in combinations(available_players, r=num_positions):
        if sum(p.female for p in subset) < min_females:
            continue

        score_matrix = np.full((num_positions, num_positions), -1e9)

        for i, player in enumerate(subset):
            for j, pos in enumerate(positions):
                if pos in player.positions:
                    strength = player.positions_stengths.get(pos, 0)
                    weight = weights.get(pos, 1.0)
                    penalty = innings_weight * player.innings_played
                    score_matrix[i][j] = strength * weight - penalty

        row_ind, col_ind = linear_sum_assignment(-score_matrix)
        total_score = sum(score_matrix[i, j] for i, j in zip(row_ind, col_ind))

        if total_score > best_score:
            best_score = total_score
            best_assignment = [(subset[i], positions[j]) for i, j in zip(row_ind, col_ind)]

    return best_assignment, best_score
