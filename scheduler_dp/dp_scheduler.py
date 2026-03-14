

from math import sqrt
import time
from typing import Dict, List

from services.inning_service import get_all_possible_innings
from services.player_service import get_early_players, get_late_players
from softball_models.inning import Inning
from softball_models.player import Player
from softball_models.schedule import Schedule
from softball_models.schedule_config import ScheduleConfig
from utils.timing import add_time, print_times


class DPScheduler:

    def __init__(self, players: List[Player], config: ScheduleConfig):

        self.config: ScheduleConfig = config
        self.players: List[Player] = players
        self.fairness: int = config.fair_factor
        self.sigma_weight: float = config.sigma_weight

        self.late_players: List[Player] = get_late_players(players)
        self.early_players: List[Player] = get_early_players(players)
        self.all_players = self.early_players + self.late_players

        self.late_lineups: List[Inning] = get_all_possible_innings(self.all_players, config.females_required)
        self.early_lineups: List[Inning] = get_all_possible_innings(self.early_players, config.females_required)[:1000]

        self.early_index = {p.id: i for i, p in enumerate(self.early_players)}
        self.late_index = {p.id: i for i, p in enumerate(self.all_players)}

        self.early_lineup_vectors = self._get_lineup_vectors(len(self.early_players), self.early_index, self.early_lineups)
        self.late_lineup_vectors = self._get_lineup_vectors(len(self.all_players), self.late_index, self.late_lineups)

        self.min_lineup: Inning = self.late_lineups[-1]
        self.max_lineup: Inning = self.late_lineups[0]

        self.best_score: float = 0

    def _get_lineup_vectors(self, 
                            num_players: int, 
                            player_index: Dict[int, int], 
                            lineups: List[Inning]):
        
        lineup_vectors = []
        for lineup in lineups:
            vec = [0] * num_players
            for p in lineup.playing_ids:
                idx = player_index[p]   # map player -> index
                vec[idx] = 1

            lineup_vectors.append(vec)

        return lineup_vectors

    @staticmethod
    def create(players: List[Player], config: ScheduleConfig):
        scheduler = DPScheduler(players, config)
        res = scheduler.schedule()
        print_times()
        return res

    def schedule(self) -> Schedule:

         # ------------------------------------------------
        # DP state:
        #
        # exposure_tuple -> (sum_strength, sum_strength2, prev_state, lineup)
        # ------------------------------------------------

        dp = {}

        num_players = len(self.early_players)
        num_lineups = len(self.early_lineups)
        fairness = self.config.fair_factor
        innings = self.config.number_innings

        zero_exposure = tuple([0] * num_players)

        dp[zero_exposure] = (0.0, 0.0, None, None)

        # ------------------------------------------------
        # Build schedule inning by inning
        # ------------------------------------------------

        count = 0
        for depth in range(innings):

            start = time.time()
            next_dp = {}

            for exposure, state in dp.items():

                sum_strength, sum_strength2, prev_exp, prev_lineup = state


                batchsize = 100
                start = 0 - batchsize
                end = 0

                while end < num_lineups:

                    start += batchsize
                    end = min(start + batchsize, num_lineups)

                    for lineup, vec in zip(self.early_lineups[start:end], self.early_lineup_vectors[start:end]):
                        count += 1
                        # copy exposure
                        new_exp = list(exposure)

                        # update exposure counts
                        for i in range(num_players):
                            if vec[i]:
                                new_exp[i] += 1

                        # fairness constraint
                        if max(new_exp) - min(new_exp) > fairness:
                            break

                        # print(depth, new_exp, count)

                        new_exp = tuple(new_exp)

                        new_sum = sum_strength + lineup.strength
                        new_sum2 = sum_strength2 + lineup.strength ** 2

                        # keep only the best score for this exposure
                        if new_exp in next_dp:

                            old_sum, _, _, _ = next_dp[new_exp]

                            if new_sum <= old_sum:
                                continue

                        next_dp[new_exp] = (
                            new_sum,
                            new_sum2,
                            exposure,
                            lineup
                        )
                    

            print("number of unique exposures", len(next_dp))
            dp = next_dp
            add_time("schedule_depth_loop", start)

        # ------------------------------------------------
        # Find best final schedule
        # ------------------------------------------------

        best_score = float("-inf")
        best_state = None

        for exposure, (sum_strength, sum_strength2, prev, lineup) in dp.items():

            mean = sum_strength / innings
            variance = sum_strength2 / innings - mean ** 2
            stddev = sqrt(max(variance, 0))

            score = mean - stddev * self.sigma_weight

            if score > best_score:
                best_score = score
                best_state = exposure

        # ------------------------------------------------
        # Reconstruct schedule
        # ------------------------------------------------

        schedule = []
        cur = best_state

        while cur is not None:

            sum_strength, sum_strength2, prev_exp, lineup = dp[cur]

            if lineup is None:
                break

            schedule.append(lineup)
            cur = prev_exp

        schedule.reverse()

        return schedule