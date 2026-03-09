

from typing import List

from services.position_service import get_positions
from softball_models.inning import Inning
from softball_models.player import Player


def get_all_possible_innings(available_players: List[Player], min_females: int):

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

        inning = Inning()
        inning.id = len(lineups)
        inning.strength = score

        for i, j in zip(row_ind, col_ind):
            player = subset[i]
            position = positions[j]
            inning.playing_ids.add(player.id)
            inning.field[position] = player
            # TODO add playing count, add female count
            #      not sure what to do about late 

        for p in available_players:
            if p.id not in inning.playing_ids:
                inning.bench[p.id] = p

        lineups.append(inning)

    lineups.sort(key = lambda l: -1*l.strength)
    return lineups